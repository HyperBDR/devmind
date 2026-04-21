from __future__ import annotations

from typing import Any


def resolve_acquisition_config(
    vendor: dict[str, Any] | None,
    *,
    default_method: str,
) -> dict[str, Any]:
    acquisition = dict((vendor or {}).get("acquisition") or {})
    acquisition.setdefault("method", default_method)
    return acquisition


def resolve_vendor_url(
    vendor: dict[str, Any] | None,
    *,
    default_url: str,
    acquisition_key: str = "page_url",
) -> str:
    acquisition = resolve_acquisition_config(
        vendor,
        default_method="page",
    )
    return (
        acquisition.get(acquisition_key)
        or (vendor or {}).get("pricing_url")
        or default_url
    )


def build_vendor_metadata(
    *,
    vendor: dict[str, Any] | None,
    slug: str,
    name: str,
    pricing_url: str,
    default_method: str,
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        "slug": slug,
        "name": name,
        "pricing_url": (vendor or {}).get("pricing_url") or pricing_url,
        "acquisition": resolve_acquisition_config(
            vendor,
            default_method=default_method,
        ),
    }
    payload.update(extra)
    return payload
