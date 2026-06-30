from __future__ import annotations

import re
from html import unescape
from typing import Any

import requests

from common import (
    build_text_token_standard_catalog,
    filter_models_by_codes,
    sync_official_vendor_catalog,
)


PRICING_URL = "https://help.aliyun.com/zh/model-studio/model-pricing"
DEFAULT_CURRENCY = "CNY"
IGNORED_SUPPLIER_PREFIXES = {"siliconflow", "vanchin"}


def sync_vendor_catalog(
    vendor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return Aliyun official prices as the standard catalog JSON."""
    vendor = dict(vendor or {})
    source_url = str(vendor.get("source_url") or PRICING_URL).strip()
    html = str(vendor.get("raw_html") or "")
    if not html and vendor.get("verify_source") is False:
        return sync_official_vendor_catalog("aliyun", vendor)
    if not html:
        html = _fetch_text(source_url)

    models = _extract_models(html)
    models = filter_models_by_codes(models, vendor.get("model_codes"))
    if not models:
        return sync_official_vendor_catalog("aliyun", vendor)

    provider_name = str(vendor.get("provider_name") or "阿里云").strip()
    currency = str(vendor.get("currency") or DEFAULT_CURRENCY).strip()
    return build_text_token_standard_catalog(
        provider_code="aliyun",
        provider_name=provider_name,
        currency=currency or DEFAULT_CURRENCY,
        source_url=source_url,
        models=models,
        notes=(
            "Extracted Aliyun Bailian text model prices from the official "
            "pricing table."
        ),
        raw_payload={
            "provider_code": "aliyun",
            "collector": "llm_ops.vendor_skill.aliyun",
            "source_url": source_url,
            "model_codes": list(vendor.get("model_codes") or []),
            "raw_html_supplied": bool(vendor.get("raw_html")),
        },
    )


def _fetch_text(url: str) -> str:
    response = requests.get(
        url,
        headers={
            "Accept": "text/html,application/json,text/plain,*/*",
            "User-Agent": "DevMind-LLMOpsPriceCollector/1.0",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.text or ""


def _extract_models(html: str) -> list[dict[str, Any]]:
    tables = re.findall(
        r"<table.*?>.*?</table>",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    models: dict[str, dict[str, Any]] = {}
    for table in tables:
        header_map: dict[str, int] = {}
        for row in _expand_rows(table):
            if len(row) < 4:
                continue
            if _is_header_row(row):
                header_map = _pricing_header_map(row)
                continue
            if not header_map:
                header_map = _default_header_map(row)
            if not _has_required_price_columns(header_map, row):
                continue

            model_id = _extract_model_id(row[header_map["model"]])
            if not model_id or _is_international_variant(model_id):
                continue
            input_price = _parse_price(row[header_map["input_price"]])
            output_price = _parse_price(row[header_map["output_price"]])
            if input_price is None or output_price is None:
                continue
            token_range = _normalize_token_range(
                _value_at(row, header_map.get("input_range")),
            )
            scope = _value_at(row, header_map.get("scope"))
            _upsert_model(
                models,
                {
                    "model_id": model_id,
                    "model_name": model_id,
                    "display_name": _display_name(model_id),
                    "aliases": [model_id],
                    "input_price_per_million": input_price,
                    "output_price_per_million": output_price,
                    "price_rows": [
                        _price_row(
                            input_price=input_price,
                            output_price=output_price,
                            token_range=token_range,
                        )
                    ],
                    "currency": DEFAULT_CURRENCY,
                    "notes": (
                        "Extracted from Aliyun Bailian official pricing "
                        f"table; deployment_scope={scope or '-'}."
                    ),
                    "_scope_score": _scope_score(scope),
                },
            )

    return [
        {key: value for key, value in item.items() if not key.startswith("_")}
        for item in sorted(
            models.values(),
            key=lambda candidate: candidate["model_name"].lower(),
        )
    ]


def _expand_rows(table_html: str) -> list[list[str]]:
    rows_html = re.findall(
        r"<tr.*?>.*?</tr>",
        table_html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    expanded_rows = []
    active_spans: dict[int, dict[str, Any]] = {}
    for row_html in rows_html:
        cells = _parse_cells(row_html)
        if not cells:
            continue
        row = []
        column = 0
        cell_index = 0
        while cell_index < len(cells) or _has_active_span_at_or_after(
            active_spans,
            column,
        ):
            span = active_spans.get(column)
            if span is not None:
                row.append(span["value"])
                span["remaining"] -= 1
                if span["remaining"] <= 0:
                    del active_spans[column]
                column += 1
                continue
            value, rowspan, _colspan = cells[cell_index]
            cell_index += 1
            colspan = max(int(_colspan or 1), 1)
            for offset in range(colspan):
                row.append(value)
                if rowspan > 1:
                    active_spans[column + offset] = {
                        "value": value,
                        "remaining": rowspan - 1,
                    }
            column += colspan
        expanded_rows.append(row)
    return expanded_rows


def _has_active_span_at_or_after(
    active_spans: dict[int, dict[str, Any]],
    column: int,
) -> bool:
    return any(index >= column for index in active_spans)


def _parse_cells(row_html: str) -> list[tuple[str, int, int]]:
    results = []
    pattern = re.compile(
        r"<(td|th)([^>]*)>(.*?)</\1>",
        flags=re.DOTALL | re.IGNORECASE,
    )
    for _, attrs, inner_html in pattern.findall(row_html):
        rowspan = _span_value(attrs, "rowspan")
        colspan = _span_value(attrs, "colspan")
        results.append((_clean_cell_text(inner_html), rowspan, colspan))
    return results


def _span_value(attrs: str, name: str) -> int:
    match = re.search(
        rf"{name}=[\"'](\d+)[\"']",
        attrs,
        flags=re.IGNORECASE,
    )
    return int(match.group(1)) if match else 1


def _clean_cell_text(inner_html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", inner_html, flags=re.IGNORECASE)
    text = re.sub(r"</(?:p|blockquote|div)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text).replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _is_header_row(row: list[str]) -> bool:
    joined = " ".join(row).lower()
    return "model id" in joined or "模型 id" in joined


def _pricing_header_map(row: list[str]) -> dict[str, int]:
    result = {}
    for index, cell in enumerate(row):
        normalized = _normalize_header(cell)
        if "modelid" in normalized or "模型id" in normalized:
            result.setdefault("model", index)
        elif "服务部署范围" in normalized:
            result.setdefault("scope", index)
        elif "单次请求" in normalized and "token" in normalized:
            result.setdefault("input_range", index)
        elif "输入单价" in normalized:
            result.setdefault("input_price", index)
        elif "输出单价" in normalized:
            result.setdefault("output_price", index)
    return result


def _normalize_header(value: str) -> str:
    return re.sub(r"[\s（）()]+", "", value).lower()


def _default_header_map(row: list[str]) -> dict[str, int]:
    if len(row) >= 6:
        return {
            "model": 0,
            "scope": 1,
            "input_range": 3,
            "input_price": 4,
            "output_price": 5,
        }
    return {
        "model": 0,
        "scope": 1,
        "input_price": 2,
        "output_price": 3,
    }


def _has_required_price_columns(
    header_map: dict[str, int],
    row: list[str],
) -> bool:
    for key in ("model", "input_price", "output_price"):
        index = header_map.get(key)
        if index is None or index >= len(row):
            return False
    return True


def _value_at(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return row[index]


def _extract_model_id(text: str) -> str:
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        candidate = _model_id_candidate(candidate)
        if not candidate:
            continue
        match = re.search(
            r"[A-Za-z0-9][A-Za-z0-9._:+-]*[A-Za-z0-9]",
            candidate,
        )
        if match and _is_valid_model_id(match.group(0)):
            return match.group(0)
    return ""


def _model_id_candidate(value: str) -> str:
    candidate = str(value or "").strip()
    match = re.search(
        r"[A-Za-z0-9][A-Za-z0-9._:+/-]*[A-Za-z0-9]",
        candidate,
    )
    if not match:
        return ""
    token = match.group(0)
    if "/" not in token:
        return token
    prefix, model_id = token.rsplit("/", 1)
    if prefix.strip().lower() in IGNORED_SUPPLIER_PREFIXES:
        return ""
    return model_id.strip()


def _is_valid_model_id(model_id: str) -> bool:
    normalized = str(model_id or "").strip().lower()
    if not normalized:
        return False
    if re.fullmatch(r"\d+(?:\.\d+)?[km]?", normalized):
        return False
    if normalized in {"token", "tokens"}:
        return False
    return bool(re.search(r"[a-z]", normalized))


def _is_international_variant(model_id: str) -> bool:
    normalized = model_id.lower()
    return normalized.endswith("-us") or "-intl" in normalized


def _parse_price(text: str) -> str | None:
    cleaned = text.replace(",", "").strip()
    if not cleaned or cleaned in {"-", "免费"}:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", cleaned)
    return match.group(1) if match else None


def _price_row(
    *,
    input_price: str,
    output_price: str,
    token_range: str,
) -> dict[str, str]:
    row = {
        "input_price_per_million": input_price,
        "output_price_per_million": output_price,
    }
    if token_range:
        row["input_token_range"] = token_range
        row["output_token_range"] = token_range
    return row


def _normalize_token_range(text: str) -> str:
    cleaned = re.sub(r"\s+", "", str(text or ""))
    if not cleaned or cleaned in {"-", "不限"}:
        return ""
    bounds = [
        _parse_token_bound(match.group(0))
        for match in re.finditer(r"\d+(?:\.\d+)?\s*(?:[KkMm]|万)?", cleaned)
    ]
    bounds = [bound for bound in bounds if bound is not None]
    if len(bounds) < 2:
        return ""
    return f"{bounds[0]}-{bounds[-1]}"


def _parse_token_bound(value: str) -> str | None:
    match = re.match(
        r"^(\d+(?:\.\d+)?)\s*([KkMm]|万)?$",
        str(value or "").strip(),
    )
    if not match:
        return None
    amount = float(match.group(1))
    unit = (match.group(2) or "").lower()
    scale = 1
    if unit == "k":
        scale = 1000
    elif unit == "m":
        scale = 1000000
    elif unit == "万":
        scale = 10000
    result = amount * scale
    if result.is_integer():
        return str(int(result))
    return str(result).rstrip("0").rstrip(".")


def _scope_score(scope: str) -> int:
    normalized = scope.replace(" ", "")
    if "中国内地" in normalized:
        return 4
    if "全球" in normalized:
        return 3
    if "国际" in normalized:
        return 1
    return 2


def _upsert_model(
    models: dict[str, dict[str, Any]],
    item: dict[str, Any],
) -> None:
    key = item["model_id"].strip().lower()
    existing = models.get(key)
    if existing is None or _candidate_score(item) > _candidate_score(existing):
        models[key] = item
        return
    if _candidate_score(item) == _candidate_score(existing):
        for row in item.get("price_rows") or []:
            _append_price_row(existing, row)


def _append_price_row(item: dict[str, Any], row: dict[str, str]) -> None:
    rows = item.setdefault("price_rows", [])
    fingerprint = tuple(sorted(row.items()))
    existing_fingerprints = {tuple(sorted(value.items())) for value in rows}
    if fingerprint not in existing_fingerprints:
        rows.append(row)


def _candidate_score(item: dict[str, Any]) -> tuple[int, int]:
    priced_fields = int(item["input_price_per_million"] is not None)
    priced_fields += int(item["output_price_per_million"] is not None)
    return int(item.get("_scope_score", 0)), priced_fields


def _display_name(model_id: str) -> str:
    return model_id.replace("-", " ").replace("_", " ").title()
