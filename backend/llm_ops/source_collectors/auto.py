from __future__ import annotations

from llm_ops.models import PriceCollectionSource
from llm_ops.price_collectors import vendor_price_collector_exists

from .base import CollectorResult


class AutoPriceSourceCollector:
    """Collect prices for sources explicitly marked as auto-collectable."""

    collector_id = "auto_price_source"

    def supports(self, source: PriceCollectionSource) -> bool:
        """Return whether this source can be collected by registered code."""
        if not source_uses_auto_collection(source):
            return False
        return auto_collection_adapter_code(source) != ""

    def collect(
        self,
        source: PriceCollectionSource,
        *,
        verify_source: bool = True,
    ) -> CollectorResult:
        """Collect and persist prices through the registered parser."""
        adapter_code = auto_collection_adapter_code(source)
        if not adapter_code:
            raise ValueError("This source does not support code collection.")

        from llm_ops.collection_services import (
            sync_vendor_price_source_catalog,
        )

        return sync_vendor_price_source_catalog(
            provider_code=adapter_code,
            source=source,
            verify_source=verify_source,
        )


def source_uses_auto_collection(source: PriceCollectionSource) -> bool:
    """Return whether operators marked this source for automatic collection."""
    method = source.collection_method
    if method == PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT:
        return True
    if method in (
        PriceCollectionSource.COLLECTION_METHOD_MANUAL_ENTRY,
        PriceCollectionSource.COLLECTION_METHOD_MANUAL_IMPORT,
        PriceCollectionSource.COLLECTION_METHOD_API_SYNC,
    ):
        return False
    return bool(
        method == PriceCollectionSource.COLLECTION_METHOD_UNKNOWN
        and source.updates_model_prices
    )


def auto_collection_adapter_code(source: PriceCollectionSource) -> str:
    """Return the registered adapter code that should collect this source."""
    adapter_code = adapter_code_from_source_provider(source)
    if adapter_code:
        return adapter_code
    return adapter_code_from_source_defaults(source)


def adapter_code_from_source_provider(source: PriceCollectionSource) -> str:
    """Return the registered adapter code from the linked provider."""
    if not source.provider_id:
        return ""
    adapter_code = str(source.provider.code or "").strip().lower()
    if adapter_code and source_adapter_exists(adapter_code):
        return adapter_code
    return ""


def adapter_code_from_source_defaults(source: PriceCollectionSource) -> str:
    """Return the registered adapter code from source presets."""
    from llm_ops.collection_services import AUTO_SYNC_SOURCE_DEFAULTS

    for adapter_code, defaults in AUTO_SYNC_SOURCE_DEFAULTS.items():
        if source.slug != defaults.get("source_slug"):
            continue
        code = str(adapter_code or "").strip().lower()
        if code and source_adapter_exists(code):
            return code
    return ""


def source_adapter_exists(provider_code: str) -> bool:
    """Return whether a deterministic adapter exists for a provider code."""
    return vendor_price_collector_exists(provider_code)
