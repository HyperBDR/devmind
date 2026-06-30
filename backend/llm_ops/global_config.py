"""Runtime configuration helpers for LLM operations."""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from .models import LLMOpsGlobalConfig, PriceCollectionSource

logger = logging.getLogger(__name__)

CRON_FIELD_PATTERN = re.compile(r"^[0-9*,/\-]+$")
META_MODEL_SYNC_TASK_NAME = "llm_ops_meta_models_dev_sync"
META_MODEL_SYNC_TASK = "llm_ops.tasks.sync_meta_models_from_models_dev"
LEGACY_OFFICIAL_COLLECT_TASK_NAME = "llm_ops_official_collect"
MODEL_PRICE_SYNC_AGENT_TASK_NAME = "llm_ops_model_price_sync_agent"
MODEL_PRICE_SYNC_AGENT_TASK = "llm_ops.tasks.run_model_price_sync_agent"
PRICE_SOURCE_TASK_PREFIX = "llm_ops_price_source_collect_"
PRICE_SOURCE_TASK = "llm_ops.tasks.collect_price_source_prices"
SUPPORTED_PRICE_SYNC_PROVIDER_CODES = (
    "aliyun",
    "aliyun-wanx",
    "baidu",
    "volcengine",
)


def price_source_task_name(source_id: int) -> str:
    """Return the beat task name for a price source."""
    return f"{PRICE_SOURCE_TASK_PREFIX}{source_id}"


def extract_price_source_id(task_name: str) -> Optional[int]:
    """Return the source id encoded in a managed price task name."""
    if not task_name.startswith(PRICE_SOURCE_TASK_PREFIX):
        return None

    suffix = task_name[len(PRICE_SOURCE_TASK_PREFIX) :]
    try:
        return int(suffix)
    except ValueError:
        return None


def parse_cron(cron_expr: str):
    """Parse a five-field cron expression into a CrontabSchedule."""
    from django_celery_beat.models import CrontabSchedule

    parts = (cron_expr or "").strip().split()
    if len(parts) != 5:
        return None
    minute, hour, day_of_month, month_of_year, day_of_week = parts
    obj, _created = CrontabSchedule.objects.get_or_create(
        minute=minute,
        hour=hour,
        day_of_week=day_of_week,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
    )
    return obj


def is_valid_cron(cron_expr: str) -> bool:
    """Return whether a five-field cron expression is structurally valid."""
    parts = (cron_expr or "").strip().split()
    if len(parts) != 5:
        return False
    return all(CRON_FIELD_PATTERN.match(part) for part in parts)


def normalize_source_ids(source_ids) -> list[int]:
    """Return enabled source ids that support model price updates."""
    if not isinstance(source_ids, list):
        return []
    normalized = []
    for value in source_ids:
        try:
            normalized.append(int(value))
        except (TypeError, ValueError):
            continue
    if not normalized:
        return []
    allowed_ids = set(
        price_sync_source_queryset()
        .filter(id__in=normalized)
        .values_list("id", flat=True)
    )
    return [source_id for source_id in normalized if source_id in allowed_ids]


def validate_price_collection_source_ids(
    source_ids,
    *,
    existing_source_ids: list[int] | None = None,
) -> list[int]:
    """Validate and normalize user-selected source ids."""
    if not isinstance(source_ids, list):
        raise ValueError("Expected a list of source ids.")

    existing_ids = set(existing_source_ids or [])
    normalized = []
    invalid_values = []
    for value in source_ids:
        try:
            normalized.append(int(value))
        except (TypeError, ValueError):
            invalid_values.append(value)
    if invalid_values:
        raise ValueError(
            "Invalid source id values: "
            + ", ".join(str(value) for value in invalid_values)
        )
    if not normalized:
        return []

    allowed_ids = set(
        price_sync_source_queryset()
        .filter(id__in=normalized)
        .values_list("id", flat=True)
    )
    missing_ids = [
        source_id
        for source_id in normalized
        if source_id not in allowed_ids and source_id not in existing_ids
    ]
    if missing_ids:
        raise ValueError(
            "Unknown or unsupported source ids: "
            + ", ".join(str(source_id) for source_id in missing_ids)
        )

    result = []
    seen = set()
    for source_id in normalized:
        if source_id in seen:
            continue
        seen.add(source_id)
        result.append(source_id)
    return result


def selected_price_collection_sources(config):
    """Return sources selected by config, falling back to enabled sources."""
    queryset = price_sync_source_queryset().select_related(
        "provider",
        "channel",
    )
    raw_source_ids = config.price_collection_source_ids
    source_ids = normalize_source_ids(raw_source_ids)
    if source_ids:
        queryset = queryset.filter(id__in=source_ids)
    elif isinstance(raw_source_ids, list) and raw_source_ids:
        queryset = queryset.none()
    else:
        queryset = queryset.filter(is_enabled=True)
    return list(queryset.order_by("source_category", "name", "id"))


def price_sync_task_source_ids(config: LLMOpsGlobalConfig) -> list[int] | None:
    """Return source ids for the Agent beat task.

    ``None`` means "sync all enabled supported sources". An empty list means
    a persisted explicit selection no longer contains supported sources, so
    the scheduled Agent should do no work instead of broadening the scope.
    """
    raw_source_ids = config.price_collection_source_ids
    source_ids = normalize_source_ids(raw_source_ids)
    if source_ids:
        return source_ids
    if isinstance(raw_source_ids, list) and raw_source_ids:
        return []
    return None


def price_sync_source_queryset():
    """Return sources currently supported by runtime price sync."""
    return PriceCollectionSource.objects.filter(
        provider__code__in=SUPPORTED_PRICE_SYNC_PROVIDER_CODES,
        slug__in=official_provider_source_slugs(),
        source_category=(
            PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
        ),
        updates_model_prices=True,
    )


def official_provider_source_slugs() -> tuple[str, ...]:
    """Return supported provider-level official source slugs."""
    return tuple(
        f"{provider_code}-official"
        for provider_code in SUPPORTED_PRICE_SYNC_PROVIDER_CODES
    )


def sync_global_config_to_beat(config: LLMOpsGlobalConfig) -> None:
    """Create or update beat rows owned by the global config UI.

    ``register_periodic_tasks`` and ``TASK_REGISTRY`` remain the bootstrap
    path for code-defined default tasks, and they skip existing rows to
    preserve admin changes during deploy. This runtime sync is narrower:
    it only updates task names owned by ``LLMOpsGlobalConfig`` after an
    explicit API/admin config save. The legacy official collector task
    is disabled on this explicit sync path so the new Agent cadence is
    the single active price collection schedule.
    """
    from django_celery_beat.models import PeriodicTask, PeriodicTasks

    meta_crontab = parse_cron(config.meta_model_sync_cron)
    price_crontab = parse_cron(config.price_collection_cron)
    if meta_crontab is None or price_crontab is None:
        logger.warning("llm_ops: skipped beat sync due to invalid cron")
        return

    PeriodicTask.objects.update_or_create(
        name=META_MODEL_SYNC_TASK_NAME,
        defaults={
            "task": META_MODEL_SYNC_TASK,
            "args": json.dumps([]),
            "kwargs": json.dumps(
                {"source_url": config.meta_model_sync_source_url}
            ),
            "crontab": meta_crontab,
            "interval": None,
            "enabled": config.meta_model_sync_enabled,
        },
    )

    PeriodicTask.objects.update_or_create(
        name=MODEL_PRICE_SYNC_AGENT_TASK_NAME,
        defaults={
            "task": MODEL_PRICE_SYNC_AGENT_TASK,
            "args": json.dumps([]),
            "kwargs": json.dumps(
                {
                    "source_ids": price_sync_task_source_ids(config),
                    "verify_source": True,
                }
            ),
            "crontab": price_crontab,
            "interval": None,
            "enabled": config.price_collection_enabled,
        },
    )

    legacy_source_task_names = PeriodicTask.objects.filter(
        name__startswith=PRICE_SOURCE_TASK_PREFIX
    ).values_list("name", flat=True)
    obsolete_task_names = [
        task_name
        for task_name in legacy_source_task_names
        if extract_price_source_id(task_name) is not None
    ]
    if obsolete_task_names:
        PeriodicTask.objects.filter(name__in=obsolete_task_names).delete()

    PeriodicTask.objects.filter(
        name=LEGACY_OFFICIAL_COLLECT_TASK_NAME,
        task="llm_ops.tasks.collect_official_model_prices",
    ).update(enabled=False)

    PeriodicTasks.update_changed()
