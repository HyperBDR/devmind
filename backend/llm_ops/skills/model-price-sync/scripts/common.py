from __future__ import annotations

import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


def sync_official_vendor_catalog(
    provider_code: str,
    vendor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Collect one official vendor catalog as standard JSON."""
    _bootstrap_django()

    from llm_ops.collectors.official import (
        OFFICIAL_PROVIDER_CONFIGS,
        collect_official_pricing_catalog,
    )
    from llm_ops.skill_runner import collected_catalog_to_standard_catalog

    vendor = dict(vendor or {})
    config = OFFICIAL_PROVIDER_CONFIGS[provider_code]
    source_url = str(vendor.get("source_url") or config.source_url).strip()
    model_codes = _normalize_model_codes(vendor.get("model_codes"))
    verify_source = _as_bool(vendor.get("verify_source"), default=True)
    timeout = _as_int(vendor.get("timeout"), default=20)
    catalog = collect_official_pricing_catalog(
        provider_code=provider_code,
        model_codes=set(model_codes),
        source_url=source_url,
        verify_source=verify_source,
        timeout=timeout,
    )
    provider_name = str(
        vendor.get("provider_name") or config.provider_label
    ).strip()
    currency = str(vendor.get("currency") or config.currency).strip()
    return collected_catalog_to_standard_catalog(
        catalog=catalog,
        provider_code=provider_code,
        provider_name=provider_name or config.provider_label,
        currency=currency or config.currency,
        source_type="vendor_python_skill",
        notes=(
            f"Collected {catalog.total_models} {provider_code} official "
            "model price rows."
        ),
        raw_payload={
            "provider_code": provider_code,
            "collector": "llm_ops.official_provider_config",
            "model_codes": sorted(model_codes),
            "source_url": source_url,
            "verify_source": verify_source,
            "timeout": timeout,
        },
    )


def build_text_token_standard_catalog(
    *,
    provider_code: str,
    provider_name: str,
    currency: str,
    source_url: str,
    models: list[dict[str, Any]],
    notes: str,
    raw_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build standard JSON from parsed text-token price rows."""
    _bootstrap_django()

    from llm_ops.collectors import (
        CollectedModelPricing,
        CollectedPricingCatalog,
        NormalizedPriceRow,
    )
    from llm_ops.skill_runner import collected_catalog_to_standard_catalog

    collected = []
    for item in models:
        model_id = str(
            item.get("model_id") or item.get("model_name") or ""
        ).strip()
        if not model_id:
            continue
        values = {}
        for source_key, target_key in (
            ("input_price_per_million", "input_price"),
            ("output_price_per_million", "output_price"),
            ("cache_hit_price_per_million", "cache_hit_input_price"),
        ):
            value = _format_price_value(item.get(source_key))
            if value != "":
                values[target_key] = value
        if not values:
            continue

        aliases = _normalize_aliases(item.get("aliases"), model_id)
        row = NormalizedPriceRow(
            kind="text_token",
            values=values,
            raw={
                "model_id": model_id,
                "aliases": aliases,
                "source_note": str(item.get("notes") or ""),
            },
        )
        raw_detail = {
            "official_source_url": source_url,
            "official_provider": provider_name,
            "model_id": model_id,
            "aliases": aliases,
            "currency": currency,
            "model_info": {
                "provider": provider_name,
                "model_id": model_id,
            },
        }
        collected.append(
            CollectedModelPricing(
                model_source=provider_name,
                model_type="文本模型",
                source_model_type="Text",
                name=str(item.get("display_name") or model_id),
                model_id=model_id,
                platform_id=model_id,
                mode="official",
                provider=provider_name,
                billing_type="按量计费",
                billing_unit=currency,
                currency=currency,
                unit=1000000,
                billing_mode="pay_as_you_go",
                price_rows=[row],
                raw_price_info={
                    "currency": currency,
                    "unit": 1000000,
                    "billing_mode": "pay_as_you_go",
                },
                raw_detail=raw_detail,
            )
        )

    catalog = CollectedPricingCatalog(
        source_url=source_url,
        total_models=len(collected),
        models=sorted(collected, key=lambda model: model.model_id.lower()),
    )
    return collected_catalog_to_standard_catalog(
        catalog=catalog,
        provider_code=provider_code,
        provider_name=provider_name,
        currency=currency,
        source_type="vendor_python_skill",
        notes=notes,
        raw_payload=raw_payload or {},
    )


def filter_models_by_codes(
    models: list[dict[str, Any]],
    model_codes: Any,
) -> list[dict[str, Any]]:
    """Keep parsed models matching requested codes, or all when empty."""
    targets = {
        _normalize_model_code(value)
        for value in _normalize_model_codes(model_codes)
        if _normalize_model_code(value)
    }
    if not targets:
        return models

    filtered = []
    for item in models:
        candidates = [
            item.get("model_id"),
            item.get("model_name"),
            *(item.get("aliases") or []),
        ]
        normalized_candidates = {
            _normalize_model_code(value)
            for value in candidates
            if _normalize_model_code(value)
        }
        if targets & normalized_candidates:
            filtered.append(item)
    return filtered


def _bootstrap_django() -> None:
    backend_root = Path(__file__).resolve().parents[4]
    backend_root_str = str(backend_root)
    if backend_root_str not in sys.path:
        sys.path.insert(0, backend_root_str)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

    try:
        import django
        from django.apps import apps
    except ImportError:
        return

    if not apps.ready:
        django.setup()


def _normalize_model_codes(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    else:
        try:
            values = list(value)
        except TypeError:
            values = [value]
    result = []
    seen = set()
    for item in values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _normalize_aliases(value: Any, model_id: str) -> list[str]:
    aliases = _normalize_model_codes(value)
    if model_id and model_id not in aliases:
        aliases.insert(0, model_id)
    return aliases


def _normalize_model_code(value: Any) -> str:
    text = str(value or "").strip().lower().replace("_", "-")
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    return text


def _format_price_value(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return ""
    if decimal_value < 0:
        return ""
    formatted = format(decimal_value.normalize(), "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted or "0"


def _as_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"0", "false", "no", "off"}:
        return False
    if text in {"1", "true", "yes", "on"}:
        return True
    return default


def _as_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
