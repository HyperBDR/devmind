from __future__ import annotations

from typing import List, Protocol, Union

from llm_ops.models import PriceCollectionSource


CollectorResult = dict[str, Union[int, List[str]]]


class PriceSourceCollector(Protocol):
    """Collect prices for one supported source family."""

    collector_id: str

    def supports(self, source: PriceCollectionSource) -> bool:
        """Return whether this collector can handle the source."""
        ...

    def collect(
        self,
        source: PriceCollectionSource,
        *,
        verify_source: bool = True,
    ) -> CollectorResult:
        """Collect and persist prices for the source."""
        ...
