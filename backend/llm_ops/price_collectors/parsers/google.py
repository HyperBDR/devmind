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


PRICING_URL = (
    "https://cloud.google.com/gemini-enterprise-agent-platform/"
    "generative-ai/pricing?hl=en"
)
DEFAULT_CURRENCY = "USD"
SUPPORTED_STANDARD_SECTIONS = {
    "standard",
    "gemini 3",
    "gemini omni",
    "agents",
    "gemini 2.5",
    "gemini 2.0",
    "token-based pricing",
    "gemma",
}
SKIPPED_STANDARD_SECTIONS = {
    "flex/batch",
    "priority",
    "modality-based pricing",
    "tuning",
    "imagen",
    "veo",
    "lyria",
}


class GooglePriceCatalogCollector:
    """Collect Google Gemini official prices into standard catalog JSON."""

    provider_code = "google"

    def collect_catalog(
        self,
        vendor_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return Google Gemini prices as standard catalog JSON."""
        vendor = dict(vendor_config or {})
        source_url = str(vendor.get("source_url") or PRICING_URL).strip()
        page_html = str(vendor.get("raw_html") or "")
        if not page_html and vendor.get("verify_source") is False:
            return sync_official_vendor_catalog("google", vendor)
        if not page_html:
            page_html = fetch_text(source_url)

        models = extract_models(page_html)
        models = filter_models_by_codes(models, vendor.get("model_codes"))
        if not models:
            return sync_official_vendor_catalog("google", vendor)

        provider_name = str(vendor.get("provider_name") or "Google").strip()
        currency = str(vendor.get("currency") or DEFAULT_CURRENCY).strip()
        return build_text_token_standard_catalog(
            provider_code="google",
            provider_name=provider_name,
            currency=currency or DEFAULT_CURRENCY,
            source_url=source_url,
            models=models,
            notes=(
                "Extracted Google Gemini text token prices from the "
                "official Google Cloud Agent Platform pricing table."
            ),
            raw_payload={
                "provider_code": "google",
                "collector": "llm_ops.price_collectors.google",
                "source_url": source_url,
                "model_codes": list(vendor.get("model_codes") or []),
                "raw_html_supplied": bool(vendor.get("raw_html")),
            },
        )


def fetch_text(url: str) -> str:
    """Fetch one Google Cloud pricing document as UTF-8 text."""
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
    return response.text or ""


def extract_models(page_html: str) -> list[dict[str, Any]]:
    """Extract standard Gemini text-token price rows from HTML tables."""
    models: dict[str, dict[str, Any]] = {}
    for section_title, table_html in extract_pricing_tables(page_html):
        section = normalize_section_title(section_title)
        if section in SKIPPED_STANDARD_SECTIONS:
            continue
        if not supports_standard_section(section):
            continue
        for item in models_from_table(table_html, section):
            upsert_model(models, item)

    return [
        item
        for item in sorted(
            models.values(),
            key=lambda candidate: candidate["model_id"].lower(),
        )
    ]


def extract_pricing_tables(page_html: str) -> list[tuple[str, str]]:
    """Return pricing table fragments with nearest preceding H3 title."""
    pattern = re.compile(
        r"(<h3\b.*?</h3>)|(<table\b.*?</table>)",
        flags=re.DOTALL | re.IGNORECASE,
    )
    section_title = ""
    tables = []
    for match in pattern.finditer(page_html):
        heading_html, table_html = match.groups()
        if heading_html:
            section_title = clean_cell_text(heading_html)
            continue
        if table_html:
            tables.append((section_title, table_html))
    return tables


def supports_standard_section(section: str) -> bool:
    """Return whether a heading contains supported standard token prices."""
    return section in SUPPORTED_STANDARD_SECTIONS


def normalize_section_title(value: str) -> str:
    """Normalize a pricing section heading for matching."""
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def models_from_table(
    table_html: str,
    section: str,
) -> list[dict[str, Any]]:
    """Build Google model price items from one table."""
    rows = expand_rows(table_html)
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        if len(row) < 3 or is_header_row(row):
            continue
        model_id = model_id_from_name(row[0])
        if not model_id:
            continue
        price_kind = price_kind_from_label(row[1])
        if not price_kind:
            continue
        prices = [parse_price(value) for value in row[2:]]
        prices = [price for price in prices if price is not None]
        if not prices:
            continue
        item = grouped.setdefault(
            model_id,
            {
                "model_id": model_id,
                "model_name": model_id,
                "display_name": display_name_from_cell(row[0]),
                "aliases": aliases_for_model(model_id, row[0]),
                "currency": DEFAULT_CURRENCY,
                "_section": section,
                "_prices": {},
            },
        )
        item["_prices"][price_kind] = prices

    models = []
    for item in grouped.values():
        model = build_model(item)
        if model:
            models.append(model)
    return models


def expand_rows(table_html: str) -> list[list[str]]:
    """Expand table rows while preserving simple row and column spans."""
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
    """Convert one HTML cell body into normalized text."""
    text = re.sub(r"<br\s*/?>", "\n", inner_html, flags=re.IGNORECASE)
    text = re.sub(r"</(?:p|blockquote|div)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text).replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def is_header_row(row: list[str]) -> bool:
    """Return whether one row is a table header."""
    joined = " ".join(row).lower()
    return "model" in joined and ("price" in joined or "input" in joined)


def model_id_from_name(value: str) -> str:
    """Normalize a Google model display name into a model ID."""
    text = display_name_from_cell(value).lower()
    if not re.match(r"^(gemini|gemma)\b", text):
        return ""
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.replace("flash lite", "flash-lite")
    text = text.replace("flash-lite image", "flash-lite-image")
    text = text.replace("image generation", "image-generation")
    text = text.replace("live api", "live-api")
    text = text.replace("computer use-preview", "computer-use-preview")
    text = re.sub(r"[^a-z0-9.]+", "-", text)
    return text.strip("-")


def display_name_from_cell(value: str) -> str:
    """Return a readable model name from a table cell."""
    text = re.sub(r"\s+", " ", str(value or "").replace("\n", " "))
    return text.strip()


def aliases_for_model(model_id: str, display_name: str) -> list[str]:
    """Return matching aliases for one Google model row."""
    aliases = [model_id]
    original = display_name_from_cell(display_name)
    if original and original not in aliases:
        aliases.append(original)
    return aliases


def price_kind_from_label(value: str) -> str:
    """Return normalized text-token price dimension for a row label."""
    text = normalize_label(value)
    if "output" in text and "text" in text:
        return "output"
    if "input" in text and not is_audio_only_input_label(text):
        return "input"
    return ""


def is_audio_only_input_label(text: str) -> bool:
    """Return whether a Google input row only prices audio tokens."""
    if "audio" not in text:
        return False
    return not any(token in text for token in ("text", "image", "video"))


def normalize_label(value: str) -> str:
    """Normalize a price row label for matching."""
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def parse_price(value: str) -> str | None:
    """Parse the first non-negative USD price from one cell."""
    text = str(value or "").replace(",", "").strip()
    if not text or text in {"-", "n/a"}:
        return None
    match = re.search(r"\$?\s*([0-9]+(?:\.[0-9]+)?)", text)
    return match.group(1) if match else None


def build_model(item: dict[str, Any]) -> dict[str, Any]:
    """Build one parsed model with complete input and output prices."""
    prices = item.get("_prices") or {}
    input_prices = list(prices.get("input") or [])
    output_prices = list(prices.get("output") or [])
    if not input_prices or not output_prices:
        return {}

    row_count = min(len(input_prices), len(output_prices), 2)
    price_rows = []
    for index in range(row_count):
        row = {
            "input_price_per_million": input_prices[index],
            "output_price_per_million": output_prices[index],
            "currency": DEFAULT_CURRENCY,
        }
        cache_price = cache_hit_price(input_prices, index)
        if cache_price:
            row["cache_hit_price_per_million"] = cache_price
        token_range = token_range_for_index(index, row_count)
        if token_range:
            row["input_token_range"] = token_range
            row["output_token_range"] = token_range
        price_rows.append(row)

    if not price_rows:
        return {}
    result = {
        key: value
        for key, value in item.items()
        if not key.startswith("_")
    }
    result.update(
        {
            "input_price_per_million": price_rows[0][
                "input_price_per_million"
            ],
            "output_price_per_million": price_rows[0][
                "output_price_per_million"
            ],
            "price_rows": price_rows,
            "notes": (
                "Extracted from Google Cloud Agent Platform pricing; "
                f"section={item.get('_section') or '-'}."
            ),
        }
    )
    return result


def cache_hit_price(input_prices: list[str], index: int) -> str:
    """Return parsed cache-hit price when present in the same table row."""
    cache_index = index + 2
    if cache_index < len(input_prices):
        return input_prices[cache_index]
    return ""


def token_range_for_index(index: int, row_count: int) -> str:
    """Return the Google context-window tier for a price row."""
    if row_count < 2:
        return ""
    return "0-200000" if index == 0 else "200001-"


def upsert_model(
    models: dict[str, dict[str, Any]],
    item: dict[str, Any],
) -> None:
    """Merge one parsed model into the extracted catalog."""
    model_id = item["model_id"]
    existing = models.get(model_id)
    if existing is None:
        models[model_id] = item
        return
    existing_rows = existing.setdefault("price_rows", [])
    for row in item.get("price_rows") or []:
        if row not in existing_rows:
            existing_rows.append(row)
