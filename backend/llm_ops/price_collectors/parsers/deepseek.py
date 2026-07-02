from __future__ import annotations

from html import unescape
from typing import Any
import re

import requests

from .common import (
    build_text_token_standard_catalog,
    filter_models_by_codes,
    sync_official_vendor_catalog,
)


PRICING_URL = "https://api-docs.deepseek.com/zh-cn/quick_start/pricing"
DEFAULT_CURRENCY = "CNY"
DEFAULT_MODELS = [
    {
        "model_id": "deepseek-v4-flash",
        "model_name": "deepseek-v4-flash",
        "display_name": "DeepSeek V4 Flash",
        "aliases": [
            "deepseek-v4-flash",
            "deepseek-chat",
            "deepseek-v3",
            "deepseek-v3.1",
            "deepseek-v3.2",
            "deepseek-v3.2-exp",
        ],
        "input_price_per_million": "1",
        "cache_hit_price_per_million": "0.02",
        "output_price_per_million": "2",
        "currency": DEFAULT_CURRENCY,
        "notes": (
            "DeepSeek official fallback price; prices are published per "
            "1M tokens."
        ),
    },
    {
        "model_id": "deepseek-v4-pro",
        "model_name": "deepseek-v4-pro",
        "display_name": "DeepSeek V4 Pro",
        "aliases": [
            "deepseek-v4-pro",
            "deepseek-reasoner",
            "deepseek-r1",
            "deepseek-r1-0528",
        ],
        "input_price_per_million": "3",
        "cache_hit_price_per_million": "0.025",
        "output_price_per_million": "6",
        "currency": DEFAULT_CURRENCY,
        "notes": (
            "DeepSeek official fallback price; prices are published per "
            "1M tokens."
        ),
    },
]


class DeepSeekPriceCatalogCollector:
    """Collect DeepSeek official prices into the standard catalog JSON."""

    provider_code = "deepseek"

    def collect_catalog(
        self,
        vendor_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return DeepSeek official prices as standard catalog JSON."""
        vendor = dict(vendor_config or {})
        source_url = str(vendor.get("source_url") or PRICING_URL).strip()
        page_html = str(vendor.get("raw_html") or "")
        if not page_html and vendor.get("verify_source") is False:
            return build_catalog(
                vendor=vendor,
                source_url=source_url,
                models=list(DEFAULT_MODELS),
            )
        if not page_html:
            page_html = fetch_text(source_url)

        models = extract_models(page_html)
        models = filter_models_by_codes(models, vendor.get("model_codes"))
        if not models:
            return sync_official_vendor_catalog("deepseek", vendor)

        return build_catalog(
            vendor=vendor,
            source_url=source_url,
            models=models,
        )


def build_catalog(
    *,
    vendor: dict[str, Any],
    source_url: str,
    models: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the standard DeepSeek price catalog payload."""
    provider_name = str(vendor.get("provider_name") or "DeepSeek").strip()
    currency = str(vendor.get("currency") or DEFAULT_CURRENCY).strip()
    models = filter_models_by_codes(models, vendor.get("model_codes"))
    return build_text_token_standard_catalog(
        provider_code="deepseek",
        provider_name=provider_name,
        currency=currency or DEFAULT_CURRENCY,
        source_url=source_url,
        models=models,
        notes=(
            "Extracted DeepSeek text model prices from the official "
            "pricing table."
        ),
        raw_payload={
            "provider_code": "deepseek",
            "collector": "llm_ops.price_collectors.deepseek",
            "source_url": source_url,
            "model_codes": list(vendor.get("model_codes") or []),
            "raw_html_supplied": bool(vendor.get("raw_html")),
        },
    )


def fetch_text(url: str) -> str:
    """Fetch one DeepSeek pricing document as UTF-8 text."""
    response = requests.get(
        url,
        headers={
            "Accept": "text/html,application/json,text/plain,*/*",
            "User-Agent": "DevMind-LLMOpsPriceCollector/1.0",
        },
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    if str(response.encoding).lower() in {"iso-8859-1", "latin-1"}:
        response.encoding = "utf-8"
    return response.text or ""


def extract_models(page_html: str) -> list[dict[str, Any]]:
    """Extract DeepSeek prices from its horizontal pricing table."""
    for table in extract_tables(page_html):
        rows = [parse_row(row_html) for row_html in extract_rows(table)]
        rows = [row for row in rows if row]
        model_ids = model_ids_from_rows(rows)
        if not model_ids:
            continue
        price_values = price_values_from_rows(rows)
        if not price_values:
            continue
        return build_models(model_ids, price_values)
    return []


def extract_tables(page_html: str) -> list[str]:
    """Return HTML table fragments from a page."""
    return re.findall(
        r"<table.*?>.*?</table>",
        page_html,
        flags=re.DOTALL | re.IGNORECASE,
    )


def extract_rows(table_html: str) -> list[str]:
    """Return HTML row fragments from a table."""
    return re.findall(
        r"<tr.*?>.*?</tr>",
        table_html,
        flags=re.DOTALL | re.IGNORECASE,
    )


def parse_row(row_html: str) -> list[str]:
    """Parse one table row into cleaned cell text values."""
    pattern = re.compile(
        r"<(?:td|th)(?:\s[^>]*)?>(.*?)</(?:td|th)>",
        flags=re.DOTALL | re.IGNORECASE,
    )
    return [clean_cell_text(value) for value in pattern.findall(row_html)]


def clean_cell_text(inner_html: str) -> str:
    """Convert one HTML cell body into normalized text."""
    text = re.sub(r"<sup\b[^>]*>.*?</sup>", " ", inner_html, flags=re.I | re.S)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text).replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def model_ids_from_rows(rows: list[list[str]]) -> list[str]:
    """Return DeepSeek model IDs from the model header row."""
    for row in rows:
        candidates = [normalize_model_id(cell) for cell in row]
        model_ids = [
            candidate
            for candidate in candidates
            if candidate.startswith("deepseek-")
        ]
        if len(model_ids) >= 2:
            return model_ids
    return []


def normalize_model_id(value: str) -> str:
    """Normalize a model ID cell value."""
    text = str(value or "").strip().lower()
    match = re.search(r"deepseek-[a-z0-9._-]+", text)
    return match.group(0) if match else ""


def price_values_from_rows(rows: list[list[str]]) -> dict[str, list[str]]:
    """Return price dimensions keyed by normalized row type."""
    result: dict[str, list[str]] = {}
    for row in rows:
        label = price_label(row)
        if not label:
            continue
        prices = [parse_price(cell) for cell in row]
        prices = [price for price in prices if price is not None]
        if len(prices) >= 2:
            result[label] = prices[-2:]
    return result


def price_label(row: list[str]) -> str:
    """Return normalized price dimension for one table row."""
    text = "".join(row).replace(" ", "")
    if "缓存命中" in text and "输入" in text:
        return "cache_hit_price_per_million"
    if "缓存未命中" in text and "输入" in text:
        return "input_price_per_million"
    if "输出" in text and "百万" in text:
        return "output_price_per_million"
    return ""


def parse_price(value: str) -> str | None:
    """Parse one non-negative DeepSeek price amount."""
    text = str(value or "").replace(",", "").strip()
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:元|CNY|RMB)?", text)
    return match.group(1) if match else None


def build_models(
    model_ids: list[str],
    price_values: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """Build parsed model dictionaries for the standard catalog builder."""
    models = []
    for index, model_id in enumerate(model_ids):
        item = {
            "model_id": model_id,
            "model_name": model_id,
            "display_name": display_name(model_id),
            "aliases": aliases_for_model(model_id),
            "currency": DEFAULT_CURRENCY,
            "notes": (
                "Extracted from DeepSeek official pricing table; prices "
                "are published per 1M tokens."
            ),
        }
        for key, values in price_values.items():
            if index < len(values):
                item[key] = values[index]
        if (
            item.get("input_price_per_million") is not None
            and item.get("output_price_per_million") is not None
        ):
            models.append(item)
    return models


def aliases_for_model(model_id: str) -> list[str]:
    """Return compatibility aliases published by DeepSeek."""
    if model_id == "deepseek-v4-flash":
        return [
            model_id,
            "deepseek-chat",
            "deepseek-v3",
            "deepseek-v3.1",
            "deepseek-v3.2",
            "deepseek-v3.2-exp",
        ]
    if model_id == "deepseek-v4-pro":
        return [
            model_id,
            "deepseek-reasoner",
            "deepseek-r1",
            "deepseek-r1-0528",
        ]
    return [model_id]


def display_name(model_id: str) -> str:
    """Return DeepSeek's display name for one model ID."""
    return model_id.replace("-", " ").title()
