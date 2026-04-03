from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError

from data_collector.models import CollectorConfig

from .models import PriceSourceConfig

AI_PRICEHUB_PLATFORM = "ai_pricehub"
AI_PRICEHUB_CONFIG_KEY = "ai_pricehub_global"


def _default_runtime_state() -> dict[str, Any]:
    return {
        "first_collect_at": None,
        "last_collect_start_at": None,
        "last_collect_end_at": None,
        "last_success_collect_at": None,
        "last_validate_at": None,
        "last_cleanup_at": None,
    }


def _pricing_sources_path() -> Path:
    return Path(__file__).resolve().parent / "config" / "pricing_sources.json"


def _fallback_default_source() -> dict[str, Any]:
    default = json.loads(_pricing_sources_path().read_text(encoding="utf-8"))[
        "primary_vendor"
    ]
    endpoint_url = (
        default.get("models_source", {}).get("url")
        or default.get("pricing_url")
        or ""
    )
    return {
        "id": 1,
        "vendor_slug": "agione",
        "platform_slug": default.get("slug", "agione"),
        "vendor_name": default.get("name", "AGIOne"),
        "region": default.get("region", ""),
        "endpoint_url": endpoint_url,
        "parser_llm_config_uuid": "",
        "currency": default.get("currency", "CNY"),
        "points_per_currency_unit": default.get("points_per_currency_unit", 10.0),
        "is_enabled": default.get("is_enabled", True),
        "notes": default.get("notes", ""),
    }


def _normalize_source(data: dict[str, Any], *, default_id: int) -> dict[str, Any]:
    parser_uuid = data.get("parser_llm_config_uuid")
    return {
        "id": int(data.get("id") or default_id),
        "vendor_slug": str(data.get("vendor_slug") or "agione"),
        "platform_slug": str(data.get("platform_slug") or ""),
        "vendor_name": str(data.get("vendor_name") or ""),
        "region": str(data.get("region") or ""),
        "endpoint_url": str(data.get("endpoint_url") or ""),
        "parser_llm_config_uuid": str(parser_uuid) if parser_uuid else "",
        "currency": str(data.get("currency") or "CNY"),
        "points_per_currency_unit": float(
            data.get("points_per_currency_unit") or 10.0
        ),
        "is_enabled": bool(data.get("is_enabled", True)),
        "notes": str(data.get("notes") or ""),
    }


def _serialize_legacy_row(config: PriceSourceConfig, *, default_id: int) -> dict[str, Any]:
    return {
        "id": config.pk or default_id,
        "vendor_slug": config.vendor_slug,
        "platform_slug": config.platform_slug,
        "vendor_name": config.vendor_name,
        "region": config.region,
        "endpoint_url": config.endpoint_url,
        "parser_llm_config_uuid": (
            str(config.parser_llm_config_uuid) if config.parser_llm_config_uuid else ""
        ),
        "currency": config.currency,
        "points_per_currency_unit": config.points_per_currency_unit,
        "is_enabled": config.is_enabled,
        "notes": config.notes,
    }


def _sort_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        sources,
        key=lambda item: (
            str(item.get("region") or ""),
            str(item.get("vendor_name") or "").lower(),
            int(item.get("id") or 0),
        ),
    )


def _get_global_config_row() -> CollectorConfig | None:
    return (
        CollectorConfig.objects.filter(
            platform=AI_PRICEHUB_PLATFORM,
            key=AI_PRICEHUB_CONFIG_KEY,
        )
        .order_by("id")
        .first()
    )


def _build_collector_value(primary_sources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schedule_cron": "0 */2 * * *",
        "cleanup_cron": "0 3 * * *",
        "retention_days": 180,
        "runtime_state": _default_runtime_state(),
        "project_keys": ["sync"],
        "primary_sources": _sort_sources(primary_sources),
    }


def list_primary_source_configs() -> list[dict[str, Any]]:
    try:
        row = _get_global_config_row()
    except (OperationalError, ProgrammingError):
        row = None
    if row:
        raw = (row.value or {}).get("primary_sources") or []
        if isinstance(raw, list) and raw:
            sources = [
                _normalize_source(item, default_id=index + 1)
                for index, item in enumerate(raw)
                if isinstance(item, dict)
            ]
            if sources:
                return _sort_sources(sources)

    try:
        legacy_rows = list(
            PriceSourceConfig.objects.filter(vendor_slug="agione").order_by(
                "region",
                "vendor_name",
                "id",
            )
        )
    except (OperationalError, ProgrammingError):
        legacy_rows = []
    if legacy_rows:
        return [
            _serialize_legacy_row(row, default_id=index + 1)
            for index, row in enumerate(legacy_rows)
        ]

    return [_fallback_default_source()]


def _upsert_global_config_row(
    *,
    owner_user,
    primary_sources: list[dict[str, Any]],
) -> CollectorConfig:
    with transaction.atomic():
        row = _get_global_config_row()
        if row:
            current_value = row.value or {}
            merged = {
                **current_value,
                "runtime_state": current_value.get("runtime_state")
                or _default_runtime_state(),
                "primary_sources": _sort_sources(primary_sources),
            }
            row.value = merged
            row.is_enabled = True
            row.save(update_fields=["value", "is_enabled", "updated_at"])
            return row

        owner_row = CollectorConfig.objects.filter(
            user=owner_user,
            platform=AI_PRICEHUB_PLATFORM,
        ).first()
        value = _build_collector_value(primary_sources)
        if owner_row:
            owner_row.key = AI_PRICEHUB_CONFIG_KEY
            owner_row.value = value
            owner_row.is_enabled = True
            owner_row.save(
                update_fields=["key", "value", "is_enabled", "updated_at"]
            )
            return owner_row

        return CollectorConfig.objects.create(
            user=owner_user,
            platform=AI_PRICEHUB_PLATFORM,
            key=AI_PRICEHUB_CONFIG_KEY,
            value=value,
            is_enabled=True,
        )


def create_primary_source_config(data: dict[str, Any], *, owner_user) -> dict[str, Any]:
    sources = list_primary_source_configs()
    next_id = max((int(item.get("id") or 0) for item in sources), default=0) + 1
    source = _normalize_source(data, default_id=next_id)
    source["id"] = next_id
    _upsert_global_config_row(owner_user=owner_user, primary_sources=[*sources, source])
    return source


def sync_primary_sources_to_collector(*, owner_user) -> list[dict[str, Any]]:
    """
    Ensure current primary source configs are persisted in CollectorConfig.

    This is used to synchronize legacy/default ai_pricehub config state into
    data_collector task configuration payload.
    """
    sources = list_primary_source_configs()
    _upsert_global_config_row(owner_user=owner_user, primary_sources=sources)
    return sources


def set_primary_source_configs(
    sources: list[dict[str, Any]],
    *,
    owner_user,
) -> list[dict[str, Any]]:
    normalized = [
        _normalize_source(item, default_id=index + 1)
        for index, item in enumerate(sources)
        if isinstance(item, dict)
    ]
    if not normalized:
        normalized = list_primary_source_configs()
    _upsert_global_config_row(owner_user=owner_user, primary_sources=normalized)
    return _sort_sources(normalized)


def get_primary_source_config(config_id: int) -> dict[str, Any] | None:
    for source in list_primary_source_configs():
        if int(source.get("id") or 0) == int(config_id):
            return source
    return None


def update_primary_source_config(
    config_id: int,
    data: dict[str, Any],
    *,
    owner_user,
) -> dict[str, Any] | None:
    sources = list_primary_source_configs()
    updated: list[dict[str, Any]] = []
    target: dict[str, Any] | None = None
    for source in sources:
        if int(source.get("id") or 0) != int(config_id):
            updated.append(source)
            continue
        merged = {**source, **data, "id": int(source["id"])}
        target = _normalize_source(merged, default_id=int(source["id"]))
        updated.append(target)
    if target is None:
        return None
    _upsert_global_config_row(owner_user=owner_user, primary_sources=updated)
    return target


def get_primary_vendor_configs() -> list[dict[str, Any]]:
    return [
        {
            "slug": source["platform_slug"],
            "vendor_slug": source.get("vendor_slug", "agione"),
            "platform_slug": source["platform_slug"],
            "name": source["vendor_name"],
            "region": source.get("region", ""),
            "parser_llm_config_uuid": source.get("parser_llm_config_uuid", ""),
            "currency": source.get("currency", "CNY"),
            "points_per_currency_unit": source.get(
                "points_per_currency_unit",
                10.0,
            ),
            "is_enabled": source.get("is_enabled", True),
            "models_source": {
                "type": "agione_model_list",
                "url": source.get("endpoint_url", ""),
            },
            "notes": source.get("notes", ""),
        }
        for source in list_primary_source_configs()
    ]
