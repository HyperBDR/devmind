from __future__ import annotations

from typing import Any

from .base import VendorPriceCatalogCollector
from .parsers.aliyun import AliyunPriceCatalogCollector
from .parsers.deepseek import DeepSeekPriceCatalogCollector
from .parsers.siliconflow import SiliconFlowPriceCatalogCollector


PRICE_CATALOG_COLLECTORS: dict[str, VendorPriceCatalogCollector] = {
    "aliyun": AliyunPriceCatalogCollector(),
    "deepseek": DeepSeekPriceCatalogCollector(),
    "siliconflow": SiliconFlowPriceCatalogCollector(),
}


def registered_vendor_price_collector_codes() -> tuple[str, ...]:
    """Return provider codes with a concrete price catalog collector."""
    return tuple(sorted(PRICE_CATALOG_COLLECTORS))


def vendor_price_collector_exists(provider_code: str) -> bool:
    """Return whether a formal catalog collector exists for a provider."""
    return normalize_provider_code(provider_code) in PRICE_CATALOG_COLLECTORS


def collect_vendor_price_catalog(
    provider_code: str,
    vendor_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a registered collector and validate the standard catalog."""
    normalized_code = normalize_provider_code(provider_code)
    collector = PRICE_CATALOG_COLLECTORS.get(normalized_code)
    if collector is None:
        raise ValueError(
            "Vendor price catalog collector not found for provider "
            f"'{provider_code}'."
        )

    from llm_ops.skill_runner import validate_standard_price_catalog

    payload = collector.collect_catalog(vendor_config or {})
    return validate_standard_price_catalog(payload, normalized_code)


def normalize_provider_code(provider_code: str) -> str:
    """Normalize provider code used by the registry."""
    code = str(provider_code or "").strip().lower()
    if not code:
        raise ValueError("Provider code is required.")
    return code
