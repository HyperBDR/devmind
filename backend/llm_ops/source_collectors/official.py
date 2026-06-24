from __future__ import annotations

from llm_ops.collection_services import sync_official_provider_model_prices
from llm_ops.collectors.official import OFFICIAL_PROVIDER_CONFIGS
from llm_ops.models import PriceCollectionSource

from .base import CollectorResult


class OfficialProviderPriceSourceCollector:
    """Collect prices from one model vendor's official source."""

    provider_code = ""

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
        return source.provider.code == self.provider_code

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


class OpenAIOfficialPriceSourceCollector(OfficialProviderPriceSourceCollector):
    """Collect prices from OpenAI's official pricing source."""

    provider_code = "openai"


class AnthropicOfficialPriceSourceCollector(
    OfficialProviderPriceSourceCollector,
):
    """Collect prices from Anthropic's official pricing source."""

    provider_code = "anthropic"


class GoogleOfficialPriceSourceCollector(
    OfficialProviderPriceSourceCollector,
):
    """Collect prices from Google's official pricing source."""

    provider_code = "google"


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


class VolcengineOfficialPriceSourceCollector(
    OfficialProviderPriceSourceCollector,
):
    """Collect prices from Volcengine's official pricing source."""

    provider_code = "volcengine"


class DeepSeekOfficialPriceSourceCollector(
    OfficialProviderPriceSourceCollector,
):
    """Collect prices from DeepSeek's official pricing source."""

    provider_code = "deepseek"


OFFICIAL_COLLECTOR_CLASSES = {
    "aliyun": AliyunOfficialPriceSourceCollector,
    "aliyun-wanx": AliyunWanxOfficialPriceSourceCollector,
    "anthropic": AnthropicOfficialPriceSourceCollector,
    "deepseek": DeepSeekOfficialPriceSourceCollector,
    "google": GoogleOfficialPriceSourceCollector,
    "openai": OpenAIOfficialPriceSourceCollector,
    "volcengine": VolcengineOfficialPriceSourceCollector,
}


def build_official_provider_collectors() -> tuple[
    OfficialProviderPriceSourceCollector,
    ...,
]:
    """Build one collector per supported official provider."""
    collectors = []
    for provider_code in sorted(OFFICIAL_PROVIDER_CONFIGS):
        collector_class = OFFICIAL_COLLECTOR_CLASSES[provider_code]
        collectors.append(collector_class())
    return tuple(collectors)
