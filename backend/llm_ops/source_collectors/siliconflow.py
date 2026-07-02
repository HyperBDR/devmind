from __future__ import annotations

from urllib.parse import urlparse

from llm_ops.collection_services import sync_vendor_price_source_catalog
from llm_ops.models import PriceCollectionSource

from .base import CollectorResult


class SiliconFlowPriceSourceCollector:
    """Collect prices from SiliconFlow supplier pricing pages."""

    collector_id = "supplier:siliconflow"

    def supports(self, source: PriceCollectionSource) -> bool:
        """Return whether this collector owns the price source."""
        if (
            source.source_category
            != PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER
        ):
            return False
        parsed = urlparse(source.endpoint_url or "")
        host = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        return host.endswith("siliconflow.cn") and path == "/pricing"

    def collect(
        self,
        source: PriceCollectionSource,
        *,
        verify_source: bool = True,
    ) -> CollectorResult:
        """Collect and persist SiliconFlow supplier prices."""
        return sync_vendor_price_source_catalog(
            provider_code="siliconflow",
            source=source,
            verify_source=verify_source,
        )
