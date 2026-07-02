from __future__ import annotations

from decimal import Decimal, InvalidOperation
from html import unescape
from typing import Any
import json
import re

import requests

from llm_ops.collectors import (
    CollectedModelPricing,
    CollectedPricingCatalog,
    NormalizedPriceRow,
)
from llm_ops.skill_runner import (
    MODEL_PRICE_CATALOG_SCHEMA_VERSION,
    collected_catalog_to_standard_catalog,
)

from .common import filter_models_by_codes


PRICING_URL = "https://siliconflow.cn/pricing"
DEFAULT_CURRENCY = "CNY"
COMPONENT_PRICE_KEYS = {
    "input-tokens": "input_price",
    "output-tokens": "output_price",
    "cached-input-tokens": "cache_hit_input_price",
}
UPSTREAM_PROVIDER_ALIASES = {
    "deepseek-ai": "DeepSeek",
    "zai-org": "智谱",
}


class SiliconFlowPriceCatalogCollector:
    """Collect SiliconFlow supplier prices into standard catalog JSON."""

    provider_code = "siliconflow"

    def collect_catalog(
        self,
        vendor_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return SiliconFlow marketplace prices as standard catalog JSON."""
        vendor = dict(vendor_config or {})
        source_url = str(vendor.get("source_url") or PRICING_URL).strip()
        page_html = str(vendor.get("raw_html") or "")
        if not page_html:
            page_html = fetch_text(source_url)

        models = extract_models(page_html)
        models = filter_models_by_codes(models, vendor.get("model_codes"))
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
    """Build a standard SiliconFlow price catalog payload."""
    provider_name = str(vendor.get("provider_name") or "SiliconFlow").strip()
    catalog = CollectedPricingCatalog(
        source_url=source_url,
        total_models=len(models),
        models=[
            collected_model_from_item(
                item,
                source_url=source_url,
            )
            for item in sorted(models, key=model_sort_key)
        ],
    )
    return collected_catalog_to_standard_catalog(
        catalog=catalog,
        provider_code="siliconflow",
        provider_name=provider_name or "SiliconFlow",
        currency=DEFAULT_CURRENCY,
        source_type="provider_adapter",
        notes=(
            "Extracted SiliconFlow supplier text model token prices from "
            "the pricing page."
        ),
        raw_payload={
            "provider_code": "siliconflow",
            "collector": "llm_ops.price_collectors.siliconflow",
            "source_url": source_url,
            "model_codes": list(vendor.get("model_codes") or []),
            "raw_html_supplied": bool(vendor.get("raw_html")),
        },
    )


def fetch_text(url: str) -> str:
    """Fetch the SiliconFlow pricing page as UTF-8 text."""
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
    """Extract token prices from SiliconFlow embedded pricing payloads."""
    items = extract_pricing_api_items(page_html)
    grouped: dict[str, dict[str, Any]] = {}
    for item in items:
        component = str(item.get("componentCode") or "").strip()
        price_key = COMPONENT_PRICE_KEYS.get(component)
        if not price_key:
            continue
        model_id = exposed_model_name(item)
        if not model_id:
            continue
        price = price_per_million_tokens(item)
        if price == "":
            continue

        model = grouped.setdefault(
            model_id,
            {
                "model_id": model_id,
                "model_name": model_id,
                "display_name": display_name(item, model_id),
                "provider": upstream_provider(item),
                "aliases": aliases_for_item(item, model_id),
                "sort": item.get("playgroundSort") or 0,
                "price_rows": {},
            },
        )
        row_key = price_row_key(item)
        row = model["price_rows"].setdefault(
            row_key,
            {
                "currency": DEFAULT_CURRENCY,
                "deployment_scope": "siliconflow",
                "market": "supplier",
                "billing_scope": price_scenario(item),
            },
        )
        row[price_key] = price

    return [normalize_grouped_model(item) for item in grouped.values()]


def extract_pricing_api_items(page_html: str) -> list[dict[str, Any]]:
    """Return decoded pricingApiItems entries from Next.js RSC scripts."""
    items: list[dict[str, Any]] = []
    for payload in iter_decoded_next_payloads(page_html):
        marker = '"pricingApiItems":'
        start = payload.find(marker)
        if start < 0:
            continue
        array_start = payload.find("[", start + len(marker))
        if array_start < 0:
            continue
        array_text = extract_json_array(payload, array_start)
        if not array_text:
            continue
        try:
            decoded = json.loads(array_text)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, list):
            items.extend(item for item in decoded if isinstance(item, dict))
    return items


def iter_decoded_next_payloads(page_html: str):
    """Yield decoded Next.js flight payload strings."""
    pattern = re.compile(
        r"<script>self\.__next_f\.push\(\[1,\"(.*?)\"\]\)</script>",
        flags=re.DOTALL,
    )
    for match in pattern.finditer(page_html):
        raw = match.group(1)
        if "pricingApiItems" not in raw:
            continue
        try:
            yield json.loads(f'"{raw}"')
        except json.JSONDecodeError:
            continue


def extract_json_array(text: str, start: int) -> str:
    """Extract a JSON array from text starting at an opening bracket."""
    if start < 0 or start >= len(text) or text[start] != "[":
        return ""
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def exposed_model_name(item: dict[str, Any]) -> str:
    """Return the source-facing model name users pass to SiliconFlow."""
    return str(item.get("playgroundName") or "").strip()


def display_name(item: dict[str, Any], model_id: str) -> str:
    """Return a compact model display name."""
    value = str(item.get("playgroundName") or model_id).strip()
    if "/" in value:
        return value.rsplit("/", 1)[-1]
    return value


def upstream_provider(item: dict[str, Any]) -> str:
    """Infer the upstream model provider from SiliconFlow model names."""
    for key in ("playgroundName", "skuName", "objectName"):
        value = str(item.get(key) or "").strip()
        if "/" in value:
            namespace = value.split("/", 1)[0]
            return UPSTREAM_PROVIDER_ALIASES.get(namespace, namespace)
    return "SiliconFlow"


def aliases_for_item(item: dict[str, Any], model_id: str) -> list[str]:
    """Return known source aliases for one SiliconFlow model."""
    values = [
        model_id,
        item.get("skuName"),
        item.get("objectName"),
        item.get("playgroundName"),
    ]
    aliases = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        aliases.append(text)
    return aliases


def price_per_million_tokens(item: dict[str, Any]) -> str:
    """Convert CNY/K tokens into CNY/M tokens."""
    value = str(item.get("realTimePriceCnyUnit") or "").strip()
    try:
        amount = Decimal(value) * Decimal("1000")
    except (InvalidOperation, TypeError, ValueError):
        return ""
    if amount < 0:
        return ""
    return format_decimal(amount)


def format_decimal(value: Decimal) -> str:
    """Format a Decimal without redundant trailing zeroes."""
    formatted = format(value.normalize(), "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted or "0"


def price_row_key(item: dict[str, Any]) -> str:
    """Return the row key used to group tiered component prices."""
    return str(item.get("coordinateDesc") or "").strip()


def price_scenario(item: dict[str, Any]) -> str:
    """Return the SiliconFlow price scenario label."""
    return str(item.get("price_scenario") or "").strip()


def normalize_grouped_model(item: dict[str, Any]) -> dict[str, Any]:
    """Convert grouped component prices into standard model rows."""
    rows = []
    for row_key, row in item["price_rows"].items():
        normalized = dict(row)
        token_range = token_range_from_coordinate(row_key)
        if token_range:
            normalized["input_token_range"] = token_range
            normalized["output_token_range"] = token_range
        rows.append(normalized)
    return {
        "model_id": item["model_id"],
        "model_name": item["model_name"],
        "display_name": item["display_name"],
        "provider": item["provider"],
        "aliases": item["aliases"],
        "sort": item.get("sort") or 0,
        "price_rows": rows,
        "notes": "SiliconFlow supplier token prices.",
    }


def token_range_from_coordinate(value: str) -> str:
    """Normalize SiliconFlow coordinate descriptions into token ranges."""
    text = unescape(str(value or "")).strip()
    match = re.search(r"\[([0-9.]+)k?\s*,\s*([0-9.]+)k?\)", text, re.I)
    if not match:
        return ""
    start = token_boundary(match.group(1))
    end = token_boundary(match.group(2))
    if start == "" or end == "":
        return ""
    return f"{start}-{end}"


def token_boundary(value: str) -> str:
    """Convert a k-token boundary into raw token count text."""
    try:
        amount = Decimal(str(value)) * Decimal("1000")
    except (InvalidOperation, TypeError, ValueError):
        return ""
    return format_decimal(amount)


def collected_model_from_item(
    item: dict[str, Any],
    *,
    source_url: str,
) -> CollectedModelPricing:
    """Build a collected pricing object for one SiliconFlow model."""
    model_id = str(item["model_id"])
    aliases = list(item.get("aliases") or [model_id])
    rows = [
        NormalizedPriceRow(
            kind="text_token",
            values=dict(row),
            raw={
                "model_id": model_id,
                "aliases": aliases,
                "source_note": str(item.get("notes") or ""),
            },
        )
        for row in item.get("price_rows") or []
    ]
    return CollectedModelPricing(
        model_source="SiliconFlow",
        model_type="文本模型",
        source_model_type="Text",
        name=str(item.get("display_name") or model_id),
        model_id=model_id,
        platform_id=model_id,
        mode="supplier",
        provider=str(item.get("provider") or ""),
        billing_type="按量计费",
        billing_unit=DEFAULT_CURRENCY,
        currency=DEFAULT_CURRENCY,
        unit=1000000,
        billing_mode="pay_as_you_go",
        price_rows=rows,
        raw_price_info={
            "currency": DEFAULT_CURRENCY,
            "unit": 1000000,
            "billing_mode": "pay_as_you_go",
        },
        raw_detail={
            "official_source_url": source_url,
            "official_provider": "SiliconFlow",
            "model_id": model_id,
            "exposed_model_name": model_id,
            "aliases": aliases,
            "currency": DEFAULT_CURRENCY,
            "model_info": {
                "provider": item.get("provider") or "",
                "model_id": model_id,
                "exposed_model_name": model_id,
            },
        },
    )


def model_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    """Return deterministic ordering for SiliconFlow models."""
    try:
        sort = int(item.get("sort") or 0)
    except (TypeError, ValueError):
        sort = 0
    return (-sort, str(item.get("model_id") or ""))
