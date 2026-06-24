"""Price source collector registry."""

from .registry import (
    collect_price_source,
    get_price_source_collector,
    source_supports_code_collection,
)

__all__ = [
    "collect_price_source",
    "get_price_source_collector",
    "source_supports_code_collection",
]
