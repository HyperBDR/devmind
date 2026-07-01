from __future__ import annotations

from llm_ops.collectors.official import OFFICIAL_PROVIDER_CONFIGS
from llm_ops.models import PriceCollectionSource

from .base import CollectorResult

OFFICIAL_COLLECTOR_REGISTRY = {}


def register_official_provider_collector(collector_class):
    """Register a backend-implemented official price collector."""
    provider_code = getattr(collector_class, "provider_code", "")
    if not provider_code:
        raise ValueError("Official collector must define provider_code.")
    if provider_code not in OFFICIAL_PROVIDER_CONFIGS:
        raise ValueError(f"Unknown official provider: {provider_code}")
    OFFICIAL_COLLECTOR_REGISTRY[provider_code] = collector_class
    return collector_class


def registered_official_provider_codes() -> tuple[str, ...]:
    """Return provider codes with implemented official collectors."""
    return tuple(sorted(OFFICIAL_COLLECTOR_REGISTRY))


class OfficialProviderPriceSourceCollector:
    """Collect prices from one model vendor's official source."""

    provider_code = ""

    def __init__(self, provider_code: str | None = None):
        if provider_code is not None:
            self.provider_code = provider_code

    @property
    def collector_id(self) -> str:
        """Return a stable registry key for logs and tests."""
        return f"official_provider:{self.provider_code}"

    def supports(self, source: PriceCollectionSource) -> bool:
        """Return whether this official collector owns the source."""
        if (
            source.source_category
            != PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
        ):
            return False
        if not source.provider_id:
            return False
        return (
            source.provider.code == self.provider_code
            and source.slug == f"{self.provider_code}-official"
        )

    def collect(
        self,
        source: PriceCollectionSource,
        *,
        verify_source: bool = True,
    ) -> CollectorResult:
        """Collect prices using the provider-specific official sync."""
        from llm_ops.collection_services import (
            sync_official_provider_model_prices,
        )

        return sync_official_provider_model_prices(
            provider=source.provider,
            source=source,
            verify_source=verify_source,
        )


@register_official_provider_collector
class AliyunOfficialPriceSourceCollector(
    OfficialProviderPriceSourceCollector,
):
    """Collect prices from Aliyun Bailian's official pricing source."""

    provider_code = "aliyun"


def build_official_provider_collectors() -> tuple[
    OfficialProviderPriceSourceCollector,
    ...,
]:
    """Build one collector per supported official provider."""
    return tuple(
        collector_class()
        for _provider_code, collector_class in sorted(
            OFFICIAL_COLLECTOR_REGISTRY.items()
        )
    )
