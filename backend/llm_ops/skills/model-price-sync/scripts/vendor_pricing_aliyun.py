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
        for row in _expand_rows(table, max_columns=5):
            if len(row) < 4 or _is_header_row(row):
                continue
            model_id = _extract_model_id(row[0])
            if not model_id or _is_international_variant(model_id):
                continue
            input_price = _parse_price(row[2])
            output_price = _parse_price(row[3])
            if input_price is None or output_price is None:
                continue
            _upsert_model(
                models,
                {
                    "model_id": model_id,
                    "model_name": model_id,
                    "display_name": _display_name(model_id),
                    "aliases": [model_id],
                    "input_price_per_million": input_price,
                    "output_price_per_million": output_price,
                    "currency": DEFAULT_CURRENCY,
                    "notes": (
                        "Extracted from Aliyun Bailian official pricing "
                        f"table; deployment_scope={row[1] or '-'}."
                    ),
                    "_scope_score": _scope_score(row[1]),
                },
            )

    return [
        {key: value for key, value in item.items() if not key.startswith("_")}
        for item in sorted(
            models.values(),
            key=lambda candidate: candidate["model_name"].lower(),
        )
    ]


def _expand_rows(table_html: str, *, max_columns: int) -> list[list[str]]:
    rows_html = re.findall(
        r"<tr.*?>.*?</tr>",
        table_html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    expanded_rows = []
    active_spans: list[dict[str, Any] | None] = [None] * max_columns
    for row_html in rows_html:
        cells = _parse_cells(row_html)
        if not cells:
            continue
        row = []
        cell_index = 0
        for column in range(max_columns):
            span = active_spans[column]
            if span and span["remaining"] > 0:
                row.append(span["value"])
                span["remaining"] -= 1
                continue
            if cell_index >= len(cells):
                row.append("")
                active_spans[column] = None
                continue
            value, rowspan, _colspan = cells[cell_index]
            cell_index += 1
            row.append(value)
            active_spans[column] = (
                {"value": value, "remaining": rowspan - 1}
                if rowspan > 1
                else None
            )
        expanded_rows.append(row)
    return expanded_rows


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


def _extract_model_id(text: str) -> str:
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        match = re.search(r"[A-Za-z0-9][A-Za-z0-9._:+-]*[A-Za-z0-9]", candidate)
        if match:
            return match.group(0)
    return ""


def _is_international_variant(model_id: str) -> bool:
    normalized = model_id.lower()
    return normalized.endswith("-us") or "-intl" in normalized


def _parse_price(text: str) -> str | None:
    cleaned = text.replace(",", "").strip()
    if not cleaned or cleaned in {"-", "免费"}:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", cleaned)
    return match.group(1) if match else None


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


def _candidate_score(item: dict[str, Any]) -> tuple[int, int]:
    priced_fields = int(item["input_price_per_million"] is not None)
    priced_fields += int(item["output_price_per_million"] is not None)
    return int(item.get("_scope_score", 0)), priced_fields


def _display_name(model_id: str) -> str:
    return model_id.replace("-", " ").replace("_", " ").title()
