"""Runtime configuration helpers for LLM operations."""
from __future__ import annotations

import json
import logging
import re

from .models import LLMOpsGlobalConfig, PriceCollectionSource

logger = logging.getLogger(__name__)

CRON_FIELD_PATTERN = re.compile(r"^[0-9*,/\-]+$")
META_MODEL_SYNC_TASK_NAME = "llm_ops_meta_models_dev_sync"
META_MODEL_SYNC_TASK = "llm_ops.tasks.sync_meta_models_from_models_dev"
LEGACY_OFFICIAL_COLLECT_TASK_NAME = "llm_ops_official_collect"
PRICE_SOURCE_TASK_PREFIX = "llm_ops_price_source_collect_"
PRICE_SOURCE_TASK = "llm_ops.tasks.collect_price_source_prices"


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
        PriceCollectionSource.objects.filter(
            id__in=normalized,
            updates_model_prices=True,
        ).values_list("id", flat=True)
    )
    return [source_id for source_id in normalized if source_id in allowed_ids]


def selected_price_collection_sources(config):
    """Return sources selected by config, falling back to enabled sources."""
    queryset = PriceCollectionSource.objects.filter(
        updates_model_prices=True,
    ).select_related("provider", "channel")
    source_ids = normalize_source_ids(config.price_collection_source_ids)
    if source_ids:
        queryset = queryset.filter(id__in=source_ids)
    else:
        queryset = queryset.filter(is_enabled=True)
    return list(queryset.order_by("source_category", "name", "id"))


def sync_global_config_to_beat(config: LLMOpsGlobalConfig) -> None:
    """Create or update django-celery-beat rows for global LLM Ops config."""
    from django_celery_beat.models import PeriodicTask, PeriodicTasks

    meta_crontab = parse_cron(config.meta_model_sync_cron)
    price_crontab = parse_cron(config.price_collection_cron)
    if meta_crontab is None or price_crontab is None:
        logger.warning("llm_ops: skipped beat sync due to invalid cron")
        return

    PeriodicTask.objects.filter(
        name=LEGACY_OFFICIAL_COLLECT_TASK_NAME
    ).update(enabled=False)

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

    PeriodicTask.objects.filter(
        name__startswith=PRICE_SOURCE_TASK_PREFIX
    ).delete()
    for source in selected_price_collection_sources(config):
        PeriodicTask.objects.update_or_create(
            name=f"{PRICE_SOURCE_TASK_PREFIX}{source.id}",
            defaults={
                "task": PRICE_SOURCE_TASK,
                "args": json.dumps([]),
                "kwargs": json.dumps(
                    {"source_id": source.id, "verify_source": True}
                ),
                "crontab": price_crontab,
                "interval": None,
                "enabled": (
                    config.price_collection_enabled
                    and source.is_enabled
                    and source.updates_model_prices
                ),
            },
        )

    PeriodicTasks.update_changed()
