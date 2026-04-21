from __future__ import annotations

import importlib
import inspect
from typing import Any, Callable


VendorCatalog = dict[str, Any]
VendorConfig = dict[str, Any]
VendorSyncCallable = Callable[..., VendorCatalog]

REGISTERED_VENDOR_MODULES: dict[str, str] = {
    "aliyun": "ai_pricehub.vendors.aliyun",
    "baidu": "ai_pricehub.vendors.baidu",
    "deepseek": "ai_pricehub.vendors.deepseek",
    "volcengine": "ai_pricehub.vendors.volcengine",
    "zhipu": "ai_pricehub.vendors.zhipu",
}


def normalize_vendor_slug(vendor_slug: str) -> str:
    slug = (vendor_slug or "").strip().lower().replace("-", "_")
    if not slug:
        raise ValueError("Vendor slug is required.")
    return slug


def execute_vendor_sync(
    sync_vendor_catalog: VendorSyncCallable,
    vendor_config: VendorConfig | None = None,
) -> VendorCatalog:
    signature = inspect.signature(sync_vendor_catalog)
    if len(signature.parameters) >= 1:
        result = sync_vendor_catalog(vendor_config or {})
    else:
        result = sync_vendor_catalog()
    return validate_vendor_catalog(result)


def run_registered_vendor_sync(
    vendor_slug: str,
    vendor_config: VendorConfig | None = None,
) -> VendorCatalog:
    module = _load_registered_vendor_module(vendor_slug)
    sync_vendor_catalog = getattr(module, "sync_vendor_catalog", None)
    if sync_vendor_catalog is None:
        raise ValueError(
            f"Registered vendor module '{module.__name__}' does not expose sync_vendor_catalog()."
        )
    return execute_vendor_sync(sync_vendor_catalog, vendor_config)


def validate_vendor_catalog(result: Any) -> VendorCatalog:
    if not isinstance(result, dict):
        raise ValueError("Vendor pricing handler returned invalid catalog data.")
    return result


def _load_registered_vendor_module(vendor_slug: str):
    slug = normalize_vendor_slug(vendor_slug)
    module_path = REGISTERED_VENDOR_MODULES.get(slug)
    if not module_path:
        raise ValueError(f"No registered vendor pricing handler for slug '{vendor_slug}'.")
    return importlib.import_module(module_path)
