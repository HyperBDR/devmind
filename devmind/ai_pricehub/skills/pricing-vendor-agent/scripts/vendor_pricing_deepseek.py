import re

import requests

from ai_pricehub.vendor_pricing_common import build_vendor_metadata, resolve_vendor_url


PRICING_URL = "https://api-docs.deepseek.com/zh-cn/quick_start/pricing"
DEFAULT_CURRENCY = "CNY"


def sync_vendor_catalog(vendor: dict | None = None) -> dict:
    pricing_url = _resolve_pricing_url(vendor)
    content = _fetch_text(pricing_url)
    models = _extract_models(content)
    return {
        "vendor": build_vendor_metadata(
            vendor=vendor,
            slug="deepseek",
            name="DeepSeek",
            pricing_url=pricing_url,
            default_method="page",
        ),
        "models": models,
        "notes": f"Extracted {len(models)} priced text models from the official DeepSeek pricing page.",
    }


def _resolve_pricing_url(vendor: dict | None) -> str:
    return resolve_vendor_url(vendor, default_url=PRICING_URL)


def _fetch_text(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def _extract_models(content: str) -> list[dict]:
    matched_input = _extract_price(content, "百万tokens输入（缓存命中）")
    uncached_input = _extract_price(content, "百万tokens输入（缓存未命中）")
    output_price = _extract_price(content, "百万tokens输出")
    models = []
    for model_name in ["deepseek-chat", "deepseek-reasoner"]:
        notes = []
        if matched_input is not None:
            notes.append(f"cache_hit_input={matched_input}元/百万tokens")
        if uncached_input is not None:
            notes.append(f"cache_miss_input={uncached_input}元/百万tokens")
        models.append(
            {
                "model_name": model_name,
                "aliases": [model_name],
                "family": "text",
                "input_price_per_million": uncached_input,
                "output_price_per_million": output_price,
                "currency": DEFAULT_CURRENCY,
                "notes": "; ".join(notes) if notes else "Extracted from official pricing page.",
            }
        )
    return models


def _extract_price(content: str, label: str) -> float | None:
    pattern = rf"{re.escape(label)}\s*\|\s*([0-9]+(?:\.[0-9]+)?)元"
    match = re.search(pattern, content)
    if not match:
        return None
    return float(match.group(1))
