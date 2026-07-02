from __future__ import annotations

from typing import Any


def sync_vendor_catalog(
    vendor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return Aliyun official prices via the formal provider adapter."""
    from llm_ops.price_collectors import collect_vendor_price_catalog

    return collect_vendor_price_catalog("aliyun", vendor or {})
