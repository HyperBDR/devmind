from __future__ import annotations

from typing import Any

from common import sync_official_vendor_catalog


def sync_vendor_catalog(
    vendor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return Aliyun Wanx official prices as standard catalog JSON."""
    return sync_official_vendor_catalog("aliyun-wanx", vendor)
