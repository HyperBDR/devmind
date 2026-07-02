from __future__ import annotations

from llm_ops.collection_services import sync_official_provider_model_prices
from llm_ops.collectors.official import OFFICIAL_PROVIDER_CONFIGS
from llm_ops.models import PriceCollectionSource
from llm_ops.price_collectors import registered_vendor_price_collector_codes

from .base import CollectorResult

SUPPORTED_OFFICIAL_PROVIDER_CODES = tuple(
    code
    for code in registered_vendor_price_collector_codes()
    if code in OFFICIAL_PROVIDER_CONFIGS
)


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
        return sync_official_provider_model_prices(
            provider=source.provider,
            source=source,
            verify_source=verify_source,
        )


class AliyunOfficialPriceSourceCollector(
    OfficialProviderPriceSourceCollector,
):
    """Collect prices from Aliyun Bailian's official pricing source."""

    provider_code = "aliyun"


class AliyunWanxOfficialPriceSourceCollector(
    OfficialProviderPriceSourceCollector,
):
    """Collect prices from Aliyun Wanxiang's official pricing source."""

    provider_code = "aliyun-wanx"


class BaiduOfficialPriceSourceCollector(
    OfficialProviderPriceSourceCollector,
):
    """Collect prices from Baidu Qianfan's official pricing source."""

    provider_code = "baidu"


class VolcengineOfficialPriceSourceCollector(
    OfficialProviderPriceSourceCollector,
):
    """Collect prices from VolcEngine Ark's official pricing source."""

    provider_code = "volcengine"


OFFICIAL_COLLECTOR_CLASSES = {
    "aliyun": AliyunOfficialPriceSourceCollector,
    "aliyun-wanx": AliyunWanxOfficialPriceSourceCollector,
    "baidu": BaiduOfficialPriceSourceCollector,
    "volcengine": VolcengineOfficialPriceSourceCollector,
}


def build_official_provider_collectors() -> tuple[
    OfficialProviderPriceSourceCollector,
    ...,
]:
    """Build one collector per supported official provider."""
    collectors = []
    for provider_code in SUPPORTED_OFFICIAL_PROVIDER_CODES:
        collector_class = OFFICIAL_COLLECTOR_CLASSES.get(
            provider_code,
            OfficialProviderPriceSourceCollector,
        )
        if collector_class is OfficialProviderPriceSourceCollector:
            collectors.append(collector_class(provider_code=provider_code))
        else:
            collectors.append(collector_class())
    return tuple(collectors)
