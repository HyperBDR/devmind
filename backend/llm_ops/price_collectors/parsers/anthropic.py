from __future__ import annotations

from typing import Any
import re

import requests

from .common import (
    build_text_token_standard_catalog,
    filter_models_by_codes,
    sync_official_vendor_catalog,
)


PRICING_URL = "https://docs.anthropic.com/en/docs/about-claude/pricing"
PRICING_MARKDOWN_URL = (
    "https://platform.claude.com/docs/en/about-claude/pricing.md"
)
DEFAULT_CURRENCY = "USD"


class AnthropicPriceCatalogCollector:
    """Collect Anthropic official prices into the standard catalog JSON."""

    provider_code = "anthropic"

    def collect_catalog(
        self,
        vendor_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return Anthropic official prices as standard catalog JSON."""
        vendor = dict(vendor_config or {})
        source_url = str(vendor.get("source_url") or PRICING_URL).strip()
        raw_text = str(
            vendor.get("raw_markdown") or vendor.get("raw_html") or ""
        )
        markdown_url = str(
            vendor.get("markdown_url") or PRICING_MARKDOWN_URL
        ).strip()
        if not raw_text and vendor.get("verify_source") is False:
            return sync_official_vendor_catalog("anthropic", vendor)
        if not raw_text:
            raw_text = fetch_text(markdown_url)

        models = extract_models(raw_text)
        models = filter_models_by_codes(models, vendor.get("model_codes"))
        if not models:
            return sync_official_vendor_catalog("anthropic", vendor)

        provider_name = str(
            vendor.get("provider_name") or "Anthropic"
        ).strip()
        currency = str(vendor.get("currency") or DEFAULT_CURRENCY).strip()
        return build_text_token_standard_catalog(
            provider_code="anthropic",
            provider_name=provider_name,
            currency=currency or DEFAULT_CURRENCY,
            source_url=source_url,
            models=models,
            notes=(
                "Extracted Anthropic Claude text token prices from the "
                "official pricing table."
            ),
            raw_payload={
                "provider_code": "anthropic",
                "collector": "llm_ops.price_collectors.anthropic",
                "source_url": source_url,
                "markdown_url": markdown_url,
                "model_codes": list(vendor.get("model_codes") or []),
                "raw_markdown_supplied": bool(vendor.get("raw_markdown")),
                "raw_html_supplied": bool(vendor.get("raw_html")),
            },
        )


def fetch_text(url: str) -> str:
    """Fetch one Anthropic pricing document as UTF-8 text."""
    response = requests.get(
        url,
        headers={
            "Accept": "text/markdown,text/plain,text/html,*/*",
            "User-Agent": "DevMind-LLMOpsPriceCollector/1.0",
        },
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    return response.text or ""


def extract_models(raw_text: str) -> list[dict[str, Any]]:
    """Extract Anthropic model price rows from markdown or HTML text."""
    rows = markdown_model_rows(raw_text)
    if not rows:
        rows = html_model_rows(raw_text)
    models = [model_from_row(row) for row in rows]
    return [
        model
        for model in sorted(
            models,
            key=lambda item: item.get("model_id", "").lower(),
        )
        if model
    ]


def markdown_model_rows(raw_text: str) -> list[list[str]]:
    """Return markdown table rows from the model pricing table."""
    rows = []
    in_pricing_table = False
    for line in str(raw_text or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_pricing_table and rows:
                break
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        normalized = [normalize_header(cell) for cell in cells]
        if "model" in normalized and "baseinputtokens" in normalized:
            in_pricing_table = True
            continue
        if not in_pricing_table:
            continue
        if is_markdown_separator(cells):
            continue
        if len(cells) >= 6:
            rows.append(cells[:6])
    return rows


def html_model_rows(raw_text: str) -> list[list[str]]:
    """Return HTML table rows from the model pricing table."""
    table_pattern = re.compile(
        r"<table\b.*?</table>",
        flags=re.DOTALL | re.IGNORECASE,
    )
    for table_html in table_pattern.findall(raw_text):
        rows = []
        has_pricing_header = False
        for row_html in re.findall(
            r"<tr\b.*?</tr>",
            table_html,
            flags=re.DOTALL | re.IGNORECASE,
        ):
            cells = parse_html_cells(row_html)
            normalized = [normalize_header(cell) for cell in cells]
            if "model" in normalized and "baseinputtokens" in normalized:
                has_pricing_header = True
                continue
            if has_pricing_header and len(cells) >= 6:
                rows.append(cells[:6])
        if rows:
            return rows
    return []


def parse_html_cells(row_html: str) -> list[str]:
    """Parse one HTML row into cell text values."""
    values = []
    for inner_html in re.findall(
        r"<(?:td|th)(?:\s[^>]*)?>(.*?)</(?:td|th)>",
        row_html,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        text = re.sub(r"<br\s*/?>", "\n", inner_html, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        values.append(clean_text(text))
    return values


def model_from_row(row: list[str]) -> dict[str, Any]:
    """Build one parsed Anthropic model price item."""
    model_name = clean_model_name(row[0])
    model_id = model_id_from_name(model_name)
    prices = [parse_price(value) for value in row[1:6]]
    if not model_id or prices[0] is None or prices[4] is None:
        return {}

    input_price = prices[0]
    cache_hit_price = prices[3]
    output_price = prices[4]
    price_row = {
        "input_price_per_million": input_price,
        "output_price_per_million": output_price,
        "currency": DEFAULT_CURRENCY,
    }
    if cache_hit_price is not None:
        price_row["cache_hit_price_per_million"] = cache_hit_price

    item = {
        "model_id": model_id,
        "model_name": model_id,
        "display_name": model_name,
        "aliases": aliases_for_model(model_id, model_name),
        "input_price_per_million": input_price,
        "output_price_per_million": output_price,
        "currency": DEFAULT_CURRENCY,
        "price_rows": [price_row],
        "notes": "Extracted from Anthropic official model pricing table.",
    }
    if cache_hit_price is not None:
        item["cache_hit_price_per_million"] = cache_hit_price
    return item


def normalize_header(value: str) -> str:
    """Normalize a table header for matching."""
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def is_markdown_separator(cells: list[str]) -> bool:
    """Return whether one markdown row is a separator."""
    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def clean_model_name(value: str) -> str:
    """Normalize an Anthropic model name cell."""
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", " ", str(value or ""))
    text = re.sub(r"\([^)]*\)", " ", text)
    return clean_text(text)


def clean_text(value: str) -> str:
    """Collapse whitespace in one extracted text value."""
    return re.sub(r"\s+", " ", str(value or "").replace("&amp;", "&")).strip()


def model_id_from_name(value: str) -> str:
    """Convert a Claude display name into a stable model code."""
    text = clean_model_name(value).lower()
    if not text.startswith("claude "):
        return ""
    text = text.replace(".", "-")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def aliases_for_model(model_id: str, model_name: str) -> list[str]:
    """Return matching aliases for one Anthropic model."""
    aliases = [model_id]
    name = clean_model_name(model_name)
    if name and name not in aliases:
        aliases.append(name)
    return aliases


def parse_price(value: str) -> str | None:
    """Parse one non-negative Anthropic USD price."""
    text = str(value or "").replace(",", "").strip()
    if not text or text in {"-", "n/a"}:
        return None
    match = re.search(r"\$?\s*([0-9]+(?:\.[0-9]+)?)", text)
    return match.group(1) if match else None
