from __future__ import annotations

from llm_ops.models import PriceCollectionSource

from .base import CollectorResult, PriceSourceCollector
from .official import build_official_provider_collectors
from .siliconflow import SiliconFlowPriceSourceCollector


PRICE_SOURCE_COLLECTORS: tuple[PriceSourceCollector, ...] = (
    *build_official_provider_collectors(),
    SiliconFlowPriceSourceCollector(),
)


def get_price_source_collector(
    source: PriceCollectionSource,
) -> PriceSourceCollector | None:
    """Return the collector registered for a source, if any."""
    for collector in PRICE_SOURCE_COLLECTORS:
        if collector.supports(source):
            return collector
    return None


def source_supports_code_collection(source: PriceCollectionSource) -> bool:
    """Return whether backend code can sync this source directly."""
    return get_price_source_collector(source) is not None


def collect_price_source(
    source: PriceCollectionSource,
    *,
    verify_source: bool = True,
) -> CollectorResult:
    """Collect prices from a source through its registered collector."""
    collector = get_price_source_collector(source)
    if collector is None:
        raise ValueError("This source does not support code collection.")
    return collector.collect(source, verify_source=verify_source)
