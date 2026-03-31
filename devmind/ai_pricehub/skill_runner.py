import importlib.util
import inspect
from pathlib import Path
from types import ModuleType


def run_vendor_skill(vendor_slug: str, vendor: dict | None = None) -> dict:
    module = _load_vendor_skill_module(vendor_slug)
    sync_vendor_catalog = getattr(module, "sync_vendor_catalog", None)
    if sync_vendor_catalog is None:
        raise ValueError(f"Vendor skill script for '{vendor_slug}' does not expose sync_vendor_catalog().")
    signature = inspect.signature(sync_vendor_catalog)
    if signature.parameters:
        result = sync_vendor_catalog(vendor)
    else:
        result = sync_vendor_catalog()
    if not isinstance(result, dict):
        raise ValueError(f"Vendor skill script for '{vendor_slug}' returned invalid catalog data.")
    return result


def _load_vendor_skill_module(vendor_slug: str) -> ModuleType:
    slug = (vendor_slug or "").strip().lower().replace("-", "_")
    if not slug:
        raise ValueError("Vendor slug is required to resolve vendor skill script.")
    script_path = (
        Path(__file__).resolve().parent
        / "skills"
        / "pricing-vendor-agent"
        / "scripts"
        / f"vendor_pricing_{slug}.py"
    )
    if not script_path.exists():
        raise ValueError(f"Vendor pricing skill script not found for slug '{vendor_slug}': {script_path}")

    spec = importlib.util.spec_from_file_location(f"ai_pricehub_vendor_skill_{slug}", script_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Unable to load vendor pricing skill script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
