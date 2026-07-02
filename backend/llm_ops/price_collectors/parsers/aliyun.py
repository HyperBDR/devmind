from __future__ import annotations

from decimal import Decimal, InvalidOperation
from html import unescape
from typing import Any
import re

import requests

from .common import (
    build_text_token_standard_catalog,
    filter_models_by_codes,
    sync_official_vendor_catalog,
)


PRICING_URL = "https://help.aliyun.com/zh/model-studio/model-pricing"
DEFAULT_CURRENCY = "CNY"
IGNORED_SUPPLIER_PREFIXES = {"siliconflow", "vanchin"}


class AliyunPriceCatalogCollector:
    """Collect Aliyun official prices into the standard catalog JSON."""

    provider_code = "aliyun"

    def collect_catalog(
        self,
        vendor_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return Aliyun official prices as standard catalog JSON."""
        vendor = dict(vendor_config or {})
        source_url = str(vendor.get("source_url") or PRICING_URL).strip()
        page_html = str(vendor.get("raw_html") or "")
        if not page_html and vendor.get("verify_source") is False:
            return sync_official_vendor_catalog("aliyun", vendor)
        if not page_html:
            page_html = fetch_text(source_url)

        models = extract_models(page_html)
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
                "Extracted Aliyun Bailian text model prices from the "
                "official pricing table."
            ),
            raw_payload={
                "provider_code": "aliyun",
                "collector": "llm_ops.price_collectors.aliyun",
                "source_url": source_url,
                "model_codes": list(vendor.get("model_codes") or []),
                "raw_html_supplied": bool(vendor.get("raw_html")),
            },
        )


def fetch_text(url: str) -> str:
    """Fetch one text-like source document."""
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


def extract_models(page_html: str) -> list[dict[str, Any]]:
    """Extract Aliyun text model price rows from HTML tables."""
    tables = re.findall(
        r"<table.*?>.*?</table>",
        page_html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    models: dict[str, dict[str, Any]] = {}
    for table in tables:
        header_map: dict[str, int] = {}
        for row in expand_rows(table):
            if len(row) < 4:
                continue
            if is_header_row(row):
                header_map = pricing_header_map(row)
                continue
            if not header_map:
                header_map = default_header_map(row)
            if not has_required_price_columns(header_map, row):
                continue

            model_id = extract_model_id(row[header_map["model"]])
            if not model_id:
                continue
            input_cell = row[header_map["input_price"]]
            output_cell = row[header_map["output_price"]]
            input_price = parse_price(input_cell)
            output_price = parse_price(output_cell)
            if input_price is None or output_price is None:
                continue
            token_range = normalize_token_range(
                value_at(row, header_map.get("input_range")),
            )
            scope = value_at(row, header_map.get("scope"))
            currency = detect_currency(
                input_cell,
                output_cell,
                scope,
                model_id,
            )
            upsert_model(
                models,
                {
                    "model_id": model_id,
                    "model_name": model_id,
                    "display_name": display_name(model_id),
                    "aliases": [model_id],
                    "input_price_per_million": input_price,
                    "output_price_per_million": output_price,
                    "price_rows": [
                        price_row(
                            input_price=input_price,
                            output_price=output_price,
                            token_range=token_range,
                            currency=currency,
                            deployment_scope=scope,
                        )
                    ],
                    "currency": currency,
                    "notes": (
                        "Extracted from Aliyun Bailian official pricing "
                        f"table; deployment_scope={scope or '-'}."
                    ),
                },
            )

    return [
        {key: value for key, value in item.items() if not key.startswith("_")}
        for item in sorted(
            models.values(),
            key=lambda candidate: candidate["model_name"].lower(),
        )
    ]


def expand_rows(table_html: str) -> list[list[str]]:
    """Expand HTML table rows, preserving simple row and column spans."""
    rows_html = re.findall(
        r"<tr.*?>.*?</tr>",
        table_html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    expanded_rows = []
    active_spans: dict[int, dict[str, Any]] = {}
    for row_html in rows_html:
        cells = parse_cells(row_html)
        if not cells:
            continue
        row = []
        column = 0
        cell_index = 0
        while cell_index < len(cells) or has_active_span_at_or_after(
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
            value, rowspan, colspan = cells[cell_index]
            cell_index += 1
            colspan = max(int(colspan or 1), 1)
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


def has_active_span_at_or_after(
    active_spans: dict[int, dict[str, Any]],
    column: int,
) -> bool:
    """Return whether a pending row span exists at or after column."""
    return any(index >= column for index in active_spans)


def parse_cells(row_html: str) -> list[tuple[str, int, int]]:
    """Parse one HTML row into cell text plus row and column spans."""
    results = []
    pattern = re.compile(
        r"<(td|th)([^>]*)>(.*?)</\1>",
        flags=re.DOTALL | re.IGNORECASE,
    )
    for _, attrs, inner_html in pattern.findall(row_html):
        rowspan = span_value(attrs, "rowspan")
        colspan = span_value(attrs, "colspan")
        results.append((clean_cell_text(inner_html), rowspan, colspan))
    return results


def span_value(attrs: str, name: str) -> int:
    """Return an integer span attribute value."""
    match = re.search(
        rf"{name}=[\"'](\d+)[\"']",
        attrs,
        flags=re.IGNORECASE,
    )
    return int(match.group(1)) if match else 1


def clean_cell_text(inner_html: str) -> str:
    """Convert one table cell body into normalized text."""
    text = re.sub(r"<br\s*/?>", "\n", inner_html, flags=re.IGNORECASE)
    text = re.sub(r"</(?:p|blockquote|div)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text).replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def is_header_row(row: list[str]) -> bool:
    """Return whether the row looks like an Aliyun pricing table header."""
    joined = " ".join(row).lower()
    return "model id" in joined or "模型 id" in joined


def pricing_header_map(row: list[str]) -> dict[str, int]:
    """Map Aliyun table headers to normalized fields."""
    result = {}
    for index, cell in enumerate(row):
        normalized = normalize_header(cell)
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


def normalize_header(value: str) -> str:
    """Normalize a table header for matching."""
    return re.sub(r"[\s（）()]+", "", value).lower()


def default_header_map(row: list[str]) -> dict[str, int]:
    """Return Aliyun's observed default table column layout."""
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


def has_required_price_columns(
    header_map: dict[str, int],
    row: list[str],
) -> bool:
    """Return whether the row includes all required pricing columns."""
    for key in ("model", "input_price", "output_price"):
        index = header_map.get(key)
        if index is None or index >= len(row):
            return False
    return True


def value_at(row: list[str], index: int | None) -> str:
    """Return a row value by optional index."""
    if index is None or index >= len(row):
        return ""
    return row[index]


def extract_model_id(text: str) -> str:
    """Extract the first valid model ID from one cell."""
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        candidate = model_id_candidate(candidate)
        if not candidate:
            continue
        match = re.search(
            r"[A-Za-z0-9][A-Za-z0-9._:+-]*[A-Za-z0-9]",
            candidate,
        )
        if match and is_valid_model_id(match.group(0)):
            return match.group(0)
    return ""


def model_id_candidate(value: str) -> str:
    """Extract a possible model ID token from a source cell."""
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


def is_valid_model_id(model_id: str) -> bool:
    """Return whether a token is plausible as a model ID."""
    normalized = str(model_id or "").strip().lower()
    if not normalized:
        return False
    if re.fullmatch(r"\d+(?:\.\d+)?[km]?", normalized):
        return False
    if normalized in {"token", "tokens"}:
        return False
    return bool(re.search(r"[a-z]", normalized))


def parse_price(text: str) -> str | None:
    """Parse a non-negative price from a table cell."""
    cleaned = text.replace(",", "").strip()
    if not cleaned or cleaned in {"-", "免费"}:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", cleaned)
    return match.group(1) if match else None


def price_row(
    *,
    input_price: str,
    output_price: str,
    token_range: str,
    currency: str,
    deployment_scope: str,
) -> dict[str, str]:
    """Build a parsed text-token price row."""
    row = {
        "input_price_per_million": input_price,
        "output_price_per_million": output_price,
        "cache_hit_price_per_million": cache_hit_price(input_price),
        "currency": currency,
    }
    if deployment_scope:
        row["deployment_scope"] = deployment_scope
        row["region"] = deployment_scope
    if token_range:
        row["input_token_range"] = token_range
        row["output_token_range"] = token_range
    return row


def detect_currency(*values: str) -> str:
    """Return the official currency indicated by one parsed row."""
    text = " ".join(str(value or "") for value in values).lower()
    if "$" in text or "usd" in text or "美元" in text:
        return "USD"
    if "¥" in text or "￥" in text or "cny" in text or "rmb" in text:
        return "CNY"
    if "元" in text or "中国" in text or "内地" in text:
        return "CNY"
    if "国际" in text or "海外" in text or "global" in text:
        return "USD"
    return DEFAULT_CURRENCY


def cache_hit_price(input_price: str) -> str:
    """Return Aliyun cache-hit price derived from input token price."""
    try:
        price = Decimal(str(input_price)) * Decimal("0.1")
    except (InvalidOperation, ValueError):
        return ""
    return format(price.normalize(), "f")


def normalize_token_range(text: str) -> str:
    """Normalize an Aliyun token range to numeric bounds."""
    cleaned = re.sub(r"\s+", "", str(text or ""))
    if not cleaned or cleaned in {"-", "不限"}:
        return ""
    bounds = [
        parse_token_bound(match.group(0))
        for match in re.finditer(r"\d+(?:\.\d+)?\s*(?:[KkMm]|万)?", cleaned)
    ]
    bounds = [bound for bound in bounds if bound is not None]
    if len(bounds) < 2:
        return ""
    return f"{bounds[0]}-{bounds[-1]}"


def parse_token_bound(value: str) -> str | None:
    """Parse one token bound with K, M, or Chinese wan suffix."""
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


def scope_score(scope: str) -> int:
    """Rank Aliyun deployment scopes for the provider-level source."""
    normalized = scope.replace(" ", "")
    if "中国内地" in normalized:
        return 4
    if "全球" in normalized:
        return 3
    if "国际" in normalized:
        return 1
    return 2


def upsert_model(
    models: dict[str, dict[str, Any]],
    item: dict[str, Any],
) -> None:
    """Merge all official price rows for one model ID."""
    key = item["model_id"].strip().lower()
    existing = models.get(key)
    if existing is None:
        models[key] = item
        return
    if candidate_score(item) > candidate_score(existing):
        existing.update(
            {
                "display_name": item["display_name"],
                "input_price_per_million": item["input_price_per_million"],
                "output_price_per_million": item["output_price_per_million"],
                "currency": item["currency"],
                "notes": item["notes"],
            }
        )
    for row in item.get("price_rows") or []:
        append_price_row(existing, row)


def append_price_row(item: dict[str, Any], row: dict[str, str]) -> None:
    """Append a unique tiered price row to an existing item."""
    rows = item.setdefault("price_rows", [])
    fingerprint = tuple(sorted(row.items()))
    existing_fingerprints = {tuple(sorted(value.items())) for value in rows}
    if fingerprint not in existing_fingerprints:
        rows.append(row)


def candidate_score(item: dict[str, Any]) -> tuple[int, int]:
    """Return ordering score for competing rows of the same model."""
    scope = ""
    rows = item.get("price_rows") or []
    if rows:
        scope = rows[0].get("deployment_scope") or ""
    priced_fields = int(item["input_price_per_million"] is not None)
    priced_fields += int(item["output_price_per_million"] is not None)
    return scope_score(scope), priced_fields


def display_name(model_id: str) -> str:
    """Return a readable fallback display name."""
    return model_id.replace("-", " ").replace("_", " ").title()
