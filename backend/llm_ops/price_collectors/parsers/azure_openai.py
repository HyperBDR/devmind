from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal, InvalidOperation
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from .common import (
    build_text_token_standard_catalog,
    filter_models_by_codes,
)


PRICING_URL = (
    "https://azure.microsoft.com/en-us/pricing/details/"
    "azure-openai/#pricing"
)
RETAIL_PRICES_API_URL = "https://prices.azure.com/api/retail/prices"
DEFAULT_CURRENCY = "USD"
DEFAULT_REGION = "eastus"
PRODUCT_FILTER = "contains(productName, 'Azure OpenAI')"
REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "DevMind-LLMOpsPriceCollector/1.0",
}
EXCLUDED_TEXT_MARKERS = {
    " aud ",
    " audio ",
    " batch ",
    " batch api ",
    " code-interpreter",
    " file-search",
    " fine tune",
    " fine-tune",
    " ft ",
    " hosting",
    " image",
    " img ",
    " pricing with batch api ",
    " pp ",
    " priority ",
    " priority processing ",
    " prty ",
    " realtime",
    " rt ",
    " transcribe",
    " training",
    " tts",
}
EXCLUDED_TEXT_PATTERNS = (
    re.compile(r"\baud\d*\b"),
    re.compile(r"\brt(?:ime)?\b"),
    re.compile(r"\btcrb\b"),
    re.compile(r"\btrscb\b"),
)
SCOPE_SCORES = {
    "global": 4,
    "regional": 3,
    "data_zone": 2,
    "unknown": 1,
}
CONTEXT_SCORES = {
    "short_context": 3,
    "unknown": 2,
    "long_context": 1,
}


class AzureOpenAIPriceCatalogCollector:
    """Collect Azure OpenAI retail prices into the standard catalog JSON."""

    provider_code = "azure-openai"

    def collect_catalog(
        self,
        vendor_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return Azure OpenAI prices as standard catalog JSON."""
        vendor = dict(vendor_config or {})
        source_url = str(vendor.get("source_url") or PRICING_URL).strip()
        items = vendor.get("raw_retail_items")
        if not isinstance(items, list):
            items = fetch_retail_prices(vendor)

        models = extract_models(items)
        models = filter_models_by_codes(models, vendor.get("model_codes"))
        provider_name = str(
            vendor.get("provider_name") or "Azure OpenAI"
        ).strip()
        currency = str(vendor.get("currency") or DEFAULT_CURRENCY).strip()
        return build_text_token_standard_catalog(
            provider_code="azure-openai",
            provider_name=provider_name,
            currency=currency or DEFAULT_CURRENCY,
            source_url=source_url,
            models=models,
            notes=(
                "Extracted Azure OpenAI text token prices from the "
                "Azure Retail Prices API."
            ),
            raw_payload={
                "provider_code": "azure-openai",
                "collector": "llm_ops.price_collectors.azure_openai",
                "source_url": source_url,
                "retail_prices_api": RETAIL_PRICES_API_URL,
                "region": azure_region(vendor),
                "model_codes": list(vendor.get("model_codes") or []),
                "raw_retail_items_supplied": bool(
                    vendor.get("raw_retail_items")
                ),
            },
        )


def fetch_retail_prices(vendor: dict[str, Any]) -> list[dict[str, Any]]:
    """Fetch Azure OpenAI retail prices from Azure's public API."""
    region = azure_region(vendor)
    currency = str(vendor.get("currency") or DEFAULT_CURRENCY).strip()
    query_filter = (
        f"{PRODUCT_FILTER} and armRegionName eq '{region}' "
        f"and currencyCode eq '{currency or DEFAULT_CURRENCY}' "
        "and priceType eq 'Consumption'"
    )
    params = {
        "api-version": "2023-01-01-preview",
        "$filter": query_filter,
    }
    timeout = int(vendor.get("timeout") or 30)
    max_pages = max(1, int(vendor.get("max_pages") or 100))
    concurrent_pages = max(1, int(vendor.get("concurrent_pages") or 8))
    first_payload = fetch_retail_price_page(params, timeout)
    items: list[dict[str, Any]] = list(first_payload.get("Items") or [])
    next_skip = skip_from_next_page_link(
        str(first_payload.get("NextPageLink") or "")
    )
    if not next_skip and len(items) >= 1000:
        next_skip = len(items)
    if not next_skip or max_pages == 1:
        return items

    page_size = max(next_skip, len(items), 1)
    fetched_pages = 1
    current_skip = next_skip
    stop_after_batch = False

    while current_skip and fetched_pages < max_pages and not stop_after_batch:
        remaining_pages = max_pages - fetched_pages
        batch_size = min(concurrent_pages, remaining_pages)
        skips = [
            current_skip + page_size * index
            for index in range(batch_size)
        ]
        for page_skip, payload in fetch_price_pages_concurrently(
            params,
            skips,
            timeout,
        ):
            page_items = list(payload.get("Items") or [])
            items.extend(page_items)
            fetched_pages += 1
            if len(page_items) < page_size:
                stop_after_batch = True
        current_skip = skips[-1] + page_size
    return items


def fetch_price_pages_concurrently(
    base_params: dict[str, str],
    skips: list[int],
    timeout: int,
) -> list[tuple[int, dict[str, Any]]]:
    """Fetch multiple Azure Retail Prices API pages concurrently."""
    pages = []
    with ThreadPoolExecutor(max_workers=len(skips)) as executor:
        future_map = {
            executor.submit(
                fetch_retail_price_page,
                {**base_params, "$skip": str(page_skip)},
                timeout,
            ): page_skip
            for page_skip in skips
        }
        for future in as_completed(future_map):
            pages.append((future_map[future], future.result()))
    return sorted(pages, key=lambda item: item[0])


def fetch_retail_price_page(
    params: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    """Fetch one page from Azure's public retail prices API."""
    response = requests.get(
        RETAIL_PRICES_API_URL,
        params=params,
        headers=REQUEST_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def skip_from_next_page_link(value: str) -> int:
    """Extract the next Azure Retail Prices API skip offset."""
    if not value:
        return 0
    query = parse_qs(urlparse(value).query)
    try:
        return int((query.get("$skip") or ["0"])[0])
    except (TypeError, ValueError):
        return 0


def azure_region(vendor: dict[str, Any]) -> str:
    """Return the Azure region used for retail price collection."""
    region = str(vendor.get("region") or DEFAULT_REGION).strip()
    return region or DEFAULT_REGION


def extract_models(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract text token prices from Azure retail price items."""
    models: dict[str, dict[str, Any]] = {}
    for item in items:
        parsed = parse_retail_item(item)
        if parsed is None:
            continue
        upsert_dimension(models, parsed)

    result = []
    for model in models.values():
        rows = list((model.get("price_rows") or {}).values())
        complete_rows = [
            row
            for row in rows
            if row.get("input_price_per_million")
            and row.get("output_price_per_million")
        ]
        if not complete_rows:
            continue
        complete_rows.sort(key=row_score, reverse=True)
        preferred = complete_rows[0]
        result.append(
            {
                "model_id": model["model_id"],
                "model_name": model["model_id"],
                "display_name": display_name(model["model_id"]),
                "aliases": sorted(model["aliases"]),
                "input_price_per_million": preferred[
                    "input_price_per_million"
                ],
                "output_price_per_million": preferred[
                    "output_price_per_million"
                ],
                "cache_hit_price_per_million": preferred.get(
                    "cache_hit_price_per_million",
                    "",
                ),
                "currency": preferred.get("currency") or DEFAULT_CURRENCY,
                "price_rows": complete_rows,
                "notes": (
                    "Extracted from Azure Retail Prices API; "
                    f"preferred_scope={preferred.get('deployment_scope')}; "
                    f"region={preferred.get('region')}."
                ),
            }
        )
    return sorted(result, key=lambda item: item["model_id"].lower())


def parse_retail_item(item: dict[str, Any]) -> dict[str, Any] | None:
    """Return a normalized Azure token price item, or None if unsupported."""
    meter = str(item.get("meterName") or item.get("skuName") or "").strip()
    if not meter:
        return None
    normalized = normalize_text(meter)
    if not is_text_token_meter(normalized, item):
        return None
    dimension = price_dimension(normalized)
    if dimension is None:
        return None
    model_id = model_id_from_meter(meter, item)
    if not model_id:
        return None
    price = price_per_million(
        item.get("retailPrice"),
        item.get("unitOfMeasure"),
    )
    if price is None:
        return None
    return {
        "model_id": model_id,
        "aliases": {model_id, compact_model_id(model_id)},
        "dimension": dimension,
        "price": price,
        "scope": deployment_scope(normalized),
        "context_window": context_window(normalized),
        "region": str(item.get("armRegionName") or "").strip(),
        "currency": str(item.get("currencyCode") or DEFAULT_CURRENCY).strip(),
        "meter_name": meter,
    }


def is_text_token_meter(text: str, item: dict[str, Any]) -> bool:
    """Return whether a retail item is a text token meter."""
    unit = str(item.get("unitOfMeasure") or "").strip().lower()
    if unit not in {"1k", "1m"}:
        return False
    item_text = " ".join(
        [
            text,
            normalize_text(str(item.get("skuName") or "")),
            normalize_text(str(item.get("productName") or "")),
        ]
    )
    padded = f" {item_text} "
    if any(marker in padded for marker in EXCLUDED_TEXT_MARKERS):
        return False
    return not any(
        pattern.search(item_text) for pattern in EXCLUDED_TEXT_PATTERNS
    )


def price_dimension(text: str) -> str | None:
    """Return normalized input/output/cache dimension for one meter."""
    padded = f" {text} "
    if any(
        marker in padded
        for marker in (" cached ", " cched ", " cchd ", " ccchd ", " cd ")
    ):
        return "cache"
    if any(
        marker in padded
        for marker in (" input ", " inp ", " inpt ", " in ")
    ):
        return "input"
    if any(
        marker in padded
        for marker in (" output ", " outp ", " outpt ", " opt ")
    ):
        return "output"
    return None


def model_id_from_meter(meter: str, item: dict[str, Any]) -> str:
    """Extract an Azure OpenAI model ID from a meter name."""
    source = normalize_text(meter)
    source = re.sub(r"\b(tokens?|1k|1m|input|inp|inpt|output)\b", " ", source)
    source = re.sub(
        r"\b(outp|outpt|opt|cached|cched|cchd|ccchd|cd)\b",
        " ",
        source,
    )
    source = re.sub(r"\b(global|glbl|gl|regional|regnl|rgnl)\b", " ", source)
    source = re.sub(r"\b(data zone|dzone|dz|dzn)\b", " ", source)
    source = re.sub(r"\b(shortco|short co|longco|long co)\b", " ", source)
    source = re.sub(r"\s+", " ", source).strip()

    match = re.search(
        r"\b(gpt[\s-]*(?:4(?:\.1|o)?|5(?:\.\d+)?|35)"
        r"(?:[\s-]*(?:mini|nano|pro|turbo|codex|chat|latest))?"
        r"(?:[\s-]*\d{4})?)\b",
        source,
    )
    if match:
        return normalize_model_id(match.group(1))

    product_name = normalize_text(str(item.get("productName") or ""))
    if "gpt5" in product_name or "gpt 5" in product_name:
        number_match = re.search(
            r"\b(5(?:\.\d+)?)(?:\s+(mini|nano|pro|codex|chat))?\b",
            source,
        )
        if number_match:
            suffix = number_match.group(2) or ""
            return normalize_model_id(f"gpt {number_match.group(1)} {suffix}")
    return ""


def normalize_model_id(value: str) -> str:
    """Normalize a model name to the catalog's model ID style."""
    text = normalize_text(value)
    text = text.replace("gpt4o", "gpt 4o")
    text = text.replace("gpt4", "gpt 4")
    text = text.replace("gpt5", "gpt 5")
    text = text.replace("gpt 35", "gpt-35")
    text = re.sub(r"[^a-z0-9.]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    text = text.replace("gpt-4o", "gpt-4o")
    return text


def compact_model_id(value: str) -> str:
    """Return a compact alias without separators in the GPT prefix."""
    return str(value or "").replace("gpt-4o", "gpt4o")


def price_per_million(price: Any, unit: Any) -> str | None:
    """Convert Azure retail token price to per-million token price."""
    try:
        value = Decimal(str(price))
    except (InvalidOperation, TypeError, ValueError):
        return None
    unit_text = str(unit or "").strip().lower()
    if unit_text == "1k":
        value *= Decimal("1000")
    elif unit_text != "1m":
        return None
    return format_decimal(value)


def format_decimal(value: Decimal) -> str:
    """Format a decimal value for stable catalog JSON."""
    formatted = format(value.normalize(), "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted or "0"


def deployment_scope(text: str) -> str:
    """Return Azure deployment scope from a meter name."""
    padded = f" {text} "
    if any(marker in padded for marker in (" global ", " glbl ", " gl ")):
        return "global"
    if any(marker in padded for marker in (" regional ", " regnl ", " rgnl ")):
        return "regional"
    if any(marker in padded for marker in (" data zone ", " dzone ", " dz ")):
        return "data_zone"
    return "unknown"


def context_window(text: str) -> str:
    """Return Azure context window group from a meter name."""
    padded = f" {text} "
    if " shortco " in padded or " short co " in padded:
        return "short_context"
    if " longco " in padded or " long co " in padded:
        return "long_context"
    return "unknown"


def upsert_dimension(
    models: dict[str, dict[str, Any]],
    parsed: dict[str, Any],
) -> None:
    """Merge one Azure retail meter into model price rows by scope."""
    model = models.setdefault(
        parsed["model_id"],
        {
            "model_id": parsed["model_id"],
            "aliases": set(parsed["aliases"]),
            "price_rows": {},
        },
    )
    model["aliases"].update(parsed["aliases"])
    row_key = (
        parsed["scope"],
        parsed["context_window"],
        parsed["region"],
        parsed["currency"],
    )
    row = model["price_rows"].setdefault(
        row_key,
        {
            "deployment_scope": parsed["scope"],
            "context_window": parsed["context_window"],
            "region": parsed["region"],
            "currency": parsed["currency"],
        },
    )
    if parsed["context_window"] != "unknown":
        row["billing_scope"] = parsed["context_window"]
    if parsed["dimension"] == "input":
        row["input_price_per_million"] = parsed["price"]
    elif parsed["dimension"] == "output":
        row["output_price_per_million"] = parsed["price"]
    elif parsed["dimension"] == "cache":
        row["cache_hit_price_per_million"] = parsed["price"]


def row_score(row: dict[str, str]) -> tuple[int, int, int]:
    """Rank Azure rows so global standard prices become the default."""
    scope = row.get("deployment_scope") or "unknown"
    context = row.get("context_window") or "unknown"
    has_cache = int(bool(row.get("cache_hit_price_per_million")))
    return (
        SCOPE_SCORES.get(scope, 0),
        CONTEXT_SCORES.get(context, 0),
        has_cache,
    )


def display_name(model_id: str) -> str:
    """Return a readable Azure model display name."""
    return str(model_id or "").replace("-", " ").upper()


def normalize_text(value: str) -> str:
    """Normalize Azure meter text for matching."""
    text = str(value or "").strip()
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    text = text.lower()
    text = text.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", text)
