from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from llm_ops.collectors import (
    CollectedModelPricing,
    CollectedPricingCatalog,
    NormalizedPriceRow,
)
from llm_ops.collectors.official import (
    OFFICIAL_PROVIDER_CONFIGS,
    collect_official_pricing_catalog,
)
from llm_ops.skill_runner import collected_catalog_to_standard_catalog


def sync_official_vendor_catalog(
    provider_code: str,
    vendor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Collect one official vendor catalog as standard JSON."""
    vendor = dict(vendor or {})
    config = OFFICIAL_PROVIDER_CONFIGS[provider_code]
    source_url = str(vendor.get("source_url") or config.source_url).strip()
    model_codes = normalize_model_codes(vendor.get("model_codes"))
    verify_source = as_bool(vendor.get("verify_source"), default=True)
    timeout = as_int(vendor.get("timeout"), default=20)
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
        source_type="provider_adapter",
        notes=(
            f"Collected {catalog.total_models} {provider_code} official "
            "model price rows."
        ),
        raw_payload={
            "provider_code": provider_code,
            "collector": "llm_ops.price_collectors.official_config",
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
    collected = []
    for item in models:
        model_id = str(
            item.get("model_id") or item.get("model_name") or ""
        ).strip()
        if not model_id:
            continue
        price_rows = text_token_price_rows(item)
        if not price_rows:
            continue

        aliases = normalize_aliases(item.get("aliases"), model_id)
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
                price_rows=price_rows,
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
        source_type="provider_adapter",
        notes=notes,
        raw_payload=raw_payload or {},
    )


def filter_models_by_codes(
    models: list[dict[str, Any]],
    model_codes: Any,
) -> list[dict[str, Any]]:
    """Keep parsed models matching requested codes, or all when empty."""
    targets = {
        normalize_model_code(value)
        for value in normalize_model_codes(model_codes)
        if normalize_model_code(value)
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
            normalize_model_code(value)
            for value in candidates
            if normalize_model_code(value)
        }
        if targets & normalized_candidates:
            filtered.append(item)
    return filtered


def text_token_price_rows(item: dict[str, Any]):
    """Return normalized token price rows for one parsed model."""
    rows = []
    raw_rows = item.get("price_rows")
    if isinstance(raw_rows, list) and raw_rows:
        for row in raw_rows:
            if not isinstance(row, dict):
                continue
            values = normalize_text_token_values(row)
            if values:
                rows.append(build_text_token_row(item, values))
        return rows

    values = normalize_text_token_values(item)
    if not values:
        return []
    return [build_text_token_row(item, values)]


def normalize_text_token_values(row: dict[str, Any]) -> dict[str, str]:
    """Normalize provider token price keys to platform price dimensions."""
    values = {}
    for source_key, target_key in (
        ("input_price_per_million", "input_price"),
        ("output_price_per_million", "output_price"),
        ("cache_hit_price_per_million", "cache_hit_input_price"),
    ):
        value = format_price_value(row.get(source_key))
        if value != "":
            values[target_key] = value
    for key in ("input_token_range", "output_token_range"):
        value = str(row.get(key) or "").strip()
        if value:
            values[key] = value
    for key in (
        "currency",
        "deployment_scope",
        "region",
        "market",
        "billing_scope",
    ):
        value = str(row.get(key) or "").strip()
        if value:
            values[key] = value
    return values


def build_text_token_row(
    item: dict[str, Any],
    values: dict[str, str],
) -> NormalizedPriceRow:
    """Build a normalized price row for text-token pricing."""
    model_id = str(
        item.get("model_id") or item.get("model_name") or ""
    ).strip()
    aliases = normalize_aliases(item.get("aliases"), model_id)
    return NormalizedPriceRow(
        kind="text_token",
        values=values,
        raw={
            "model_id": model_id,
            "aliases": aliases,
            "source_note": str(item.get("notes") or ""),
        },
    )


def normalize_model_codes(value: Any) -> list[str]:
    """Normalize one or many model code values."""
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


def normalize_aliases(value: Any, model_id: str) -> list[str]:
    """Normalize model aliases and ensure model_id is included."""
    aliases = normalize_model_codes(value)
    if model_id and model_id not in aliases:
        aliases.insert(0, model_id)
    return aliases


def normalize_model_code(value: Any) -> str:
    """Normalize a model code for matching."""
    text = str(value or "").strip().lower().replace("_", "-")
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    return text


def format_price_value(value: Any) -> str:
    """Format a non-negative price as a compact decimal string."""
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


def as_bool(value: Any, *, default: bool) -> bool:
    """Parse a loose boolean value."""
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


def as_int(value: Any, *, default: int) -> int:
    """Parse a loose integer value."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
