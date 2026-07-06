from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from .collectors import (
    CollectedModelPricing,
    CollectedPricingCatalog,
    NormalizedPriceRow,
)


MODEL_PRICE_CATALOG_SCHEMA_VERSION = "llm_ops.model_price_catalog.v1"


def run_vendor_pricing_skill(
    provider_code: str,
    vendor_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a skill script and return a standard model price catalog JSON."""
    module = _load_vendor_skill_module(provider_code)
    sync_vendor_catalog = getattr(module, "sync_vendor_catalog", None)
    if sync_vendor_catalog is None:
        raise ValueError(
            f"Vendor pricing skill for '{provider_code}' does not expose "
            "sync_vendor_catalog()."
        )
    signature = inspect.signature(sync_vendor_catalog)
    if signature.parameters:
        result = sync_vendor_catalog(vendor_config or {})
    else:
        result = sync_vendor_catalog()
    return validate_standard_price_catalog(result, provider_code)


def vendor_pricing_skill_exists(provider_code: str) -> bool:
    """Return whether a provider has a deterministic pricing skill."""
    slug = _normalize_provider_slug(provider_code)
    script_path = _skill_dir() / "scripts" / f"vendor_pricing_{slug}.py"
    return script_path.exists()


def validate_standard_price_catalog(
    result: Any,
    provider_code: str = "",
) -> dict[str, Any]:
    """Validate the standard JSON contract returned by a price skill."""
    if not isinstance(result, dict):
        raise ValueError("Vendor pricing skill returned invalid catalog data.")
    if result.get("schema_version") != MODEL_PRICE_CATALOG_SCHEMA_VERSION:
        raise ValueError("Vendor pricing skill returned unsupported schema.")
    if not isinstance(result.get("models"), list):
        raise ValueError("Vendor pricing skill catalog must include models.")
    provider = result.get("provider") or {}
    if provider_code and provider.get("code") != provider_code:
        raise ValueError("Vendor pricing skill returned the wrong provider.")
    return result


def standard_catalog_to_collected_catalog(
    payload: dict[str, Any],
) -> CollectedPricingCatalog:
    """Convert a standard skill JSON catalog to the persistence catalog."""
    validate_standard_price_catalog(payload)
    models = [
        _standard_model_to_collected_model(item)
        for item in payload.get("models") or []
    ]
    return CollectedPricingCatalog(
        source_url=str(payload.get("source_url") or ""),
        total_models=int(payload.get("total_models") or len(models)),
        models=models,
    )


def collected_catalog_to_standard_catalog(
    *,
    catalog: CollectedPricingCatalog,
    provider_code: str,
    provider_name: str,
    currency: str,
    source_type: str,
    notes: str = "",
    raw_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert an internal catalog to the standard skill JSON contract."""
    return {
        "schema_version": MODEL_PRICE_CATALOG_SCHEMA_VERSION,
        "source_type": source_type,
        "source_url": catalog.source_url,
        "total_models": catalog.total_models,
        "provider": {
            "code": provider_code,
            "name": provider_name,
            "currency": currency,
        },
        "models": [
            _collected_model_to_standard_model(item)
            for item in catalog.models
        ],
        "notes": notes,
        "raw_payload": raw_payload or {},
    }


def standard_catalog_run_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Return compact run metadata for a standard skill catalog."""
    validate_standard_price_catalog(payload)
    provider = payload.get("provider") or {}
    raw_payload = payload.get("raw_payload") or {}
    metadata = {
        "catalog_schema_version": payload.get("schema_version") or "",
        "catalog_source_type": payload.get("source_type") or "",
        "vendor_catalog_provider": provider.get("code") or "",
        "vendor_catalog_model_count": len(payload.get("models") or []),
        "vendor_skill_provider": provider.get("code") or "",
        "vendor_skill_model_count": len(payload.get("models") or []),
    }
    if raw_payload.get("collector"):
        metadata["vendor_catalog_collector"] = raw_payload["collector"]
        metadata["vendor_skill_collector"] = raw_payload["collector"]
    if "fallback_used" in raw_payload:
        metadata["vendor_catalog_fallback_used"] = bool(
            raw_payload.get("fallback_used")
        )
    if raw_payload.get("fallback_reason"):
        metadata["vendor_catalog_fallback_reason"] = str(
            raw_payload.get("fallback_reason")
        )
    return metadata


def _standard_model_to_collected_model(
    payload: dict[str, Any],
) -> CollectedModelPricing:
    rows = [
        NormalizedPriceRow(
            kind=str(row.get("kind") or ""),
            values=dict(row.get("values") or {}),
            raw=dict(row.get("raw") or {}),
        )
        for row in payload.get("price_rows") or []
    ]
    return CollectedModelPricing(
        model_source=str(payload.get("model_source") or ""),
        model_type=str(payload.get("model_type") or "文本模型"),
        source_model_type=str(payload.get("source_model_type") or "Text"),
        name=str(payload.get("name") or payload.get("model_id") or ""),
        model_id=str(payload.get("model_id") or ""),
        platform_id=payload.get("platform_id") or payload.get("model_id"),
        mode=str(payload.get("mode") or "official"),
        provider=str(payload.get("provider") or ""),
        billing_type=str(payload.get("billing_type") or "按量计费"),
        billing_unit=str(payload.get("billing_unit") or ""),
        currency=str(payload.get("currency") or ""),
        unit=payload.get("unit"),
        billing_mode=str(payload.get("billing_mode") or "pay_as_you_go"),
        price_rows=rows,
        raw_price_info=dict(payload.get("raw_price_info") or {}),
        raw_detail=dict(payload.get("raw_detail") or {}),
    )


def _collected_model_to_standard_model(
    item: CollectedModelPricing,
) -> dict[str, Any]:
    return {
        "model_source": item.model_source,
        "model_type": item.model_type,
        "source_model_type": item.source_model_type,
        "name": item.name,
        "model_id": item.model_id,
        "platform_id": item.platform_id,
        "mode": item.mode,
        "provider": item.provider,
        "billing_type": item.billing_type,
        "billing_unit": item.billing_unit,
        "currency": item.currency,
        "unit": item.unit,
        "billing_mode": item.billing_mode,
        "price_rows": [
            {
                "kind": row.kind,
                "values": row.values,
                "raw": row.raw,
            }
            for row in item.price_rows
        ],
        "raw_price_info": item.raw_price_info,
        "raw_detail": item.raw_detail,
    }


def _load_vendor_skill_module(provider_code: str) -> ModuleType:
    slug = _normalize_provider_slug(provider_code)
    script_dir = _skill_dir() / "scripts"
    script_path = script_dir / f"vendor_pricing_{slug}.py"
    if not script_path.exists():
        raise ValueError(
            "Vendor pricing skill script not found for provider "
            f"'{provider_code}': {script_path}"
        )
    script_dir_str = str(script_dir)
    if script_dir_str not in sys.path:
        sys.path.insert(0, script_dir_str)
    spec = importlib.util.spec_from_file_location(
        f"llm_ops_model_price_skill_{slug}",
        script_path,
    )
    if spec is None or spec.loader is None:
        raise ValueError(f"Unable to load vendor pricing skill: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_provider_slug(provider_code: str) -> str:
    slug = str(provider_code or "").strip().lower().replace("-", "_")
    if not slug:
        raise ValueError("Provider code is required.")
    return slug


def _skill_dir() -> Path:
    return Path(__file__).resolve().parent / "skills" / "model-price-sync"
