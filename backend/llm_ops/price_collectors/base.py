from __future__ import annotations

from typing import Any, Protocol


class VendorPriceCatalogCollector(Protocol):
    """Collect one vendor pricing source into the standard catalog JSON."""

    provider_code: str

    def collect_catalog(
        self,
        vendor_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a standard model price catalog JSON payload."""
        ...
