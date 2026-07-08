from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.http import Http404
from django.utils import timezone

from data_ops.models import (
    CollectionFrequency,
    FeishuBitableCollectionConfig,
    SyncJob,
    SyncStatus,
)

from .global_config import get_active_sync_job_timeout_hours
from .mappings import iter_default_collection_configs


FREQUENCY_INTERVALS = {
    CollectionFrequency.HOURLY: timedelta(hours=1),
    CollectionFrequency.DAILY: timedelta(days=1),
    CollectionFrequency.WEEKLY: timedelta(days=7),
}
def ensure_bitable_collection_configs() -> list[FeishuBitableCollectionConfig]:
    """Create missing Feishu Bitable collection configs from defaults."""
    _migrate_legacy_oversea_settlement_config()
    configs = []
    for item in iter_default_collection_configs():
        config, _ = FeishuBitableCollectionConfig.objects.get_or_create(
            source_key=item["source_key"],
            table_key=item["table_key"],
            defaults={
                "source_name": item["source_name"],
                "table_name": item["table_name"],
                "app_token": item["app_token"],
                "table_id": item["table_id"],
                "expected_min_records": item["expected_min_records"],
                "required_permissions": item["required_permissions"],
            },
        )
        configs.append(config)
    return configs


def _migrate_legacy_oversea_settlement_config() -> None:
    legacy = FeishuBitableCollectionConfig.objects.filter(
        source_key="oversea",
        table_key="oversea_settlements",
    ).first()
    if legacy is None:
        return

    target = FeishuBitableCollectionConfig.objects.filter(
        source_key="oversea_stats",
        table_key="oversea_settlements",
    ).first()
    if target is None:
        legacy.source_key = "oversea_stats"
        legacy.source_name = legacy.source_name or "Overseas settlement"
        legacy.save(update_fields=["source_key", "source_name", "updated_at"])
        return

    legacy.delete()


def list_bitable_collection_configs():
    ensure_bitable_collection_configs()
    return FeishuBitableCollectionConfig.objects.order_by(
        "source_key",
        "table_key",
    )


def get_bitable_collection_config(
    config_id: str,
) -> FeishuBitableCollectionConfig:
    ensure_bitable_collection_configs()
    try:
        return FeishuBitableCollectionConfig.objects.get(id=config_id)
    except FeishuBitableCollectionConfig.DoesNotExist as exc:
        raise Http404("Feishu Bitable collection config not found") from exc


def get_bitable_collection_config_by_key(
    source_key: str,
    table_key: str,
) -> FeishuBitableCollectionConfig:
    ensure_bitable_collection_configs()
    try:
        return FeishuBitableCollectionConfig.objects.get(
            source_key=source_key,
            table_key=table_key,
        )
    except FeishuBitableCollectionConfig.DoesNotExist as exc:
        raise Http404("Feishu Bitable collection config not found") from exc


def mark_config_preflight(config: FeishuBitableCollectionConfig) -> None:
    config.last_preflight_at = timezone.now()
    config.save(update_fields=["last_preflight_at", "updated_at"])


def mark_config_manual_trigger(config: FeishuBitableCollectionConfig) -> None:
    config.last_manual_trigger_at = timezone.now()
    config.save(update_fields=["last_manual_trigger_at", "updated_at"])


def mark_config_scheduled(config: FeishuBitableCollectionConfig) -> None:
    config.last_scheduled_at = timezone.now()
    config.save(update_fields=["last_scheduled_at", "updated_at"])


def due_bitable_collection_configs(now=None):
    now = now or timezone.now()
    ensure_bitable_collection_configs()
    configs = FeishuBitableCollectionConfig.objects.filter(
        is_enabled=True,
    ).exclude(sync_frequency=CollectionFrequency.MANUAL)
    return [
        config
        for config in configs
        if is_config_due(config, now) and not has_active_sync_job(config, now)
    ]


def is_config_due(
    config: FeishuBitableCollectionConfig,
    now,
) -> bool:
    interval = FREQUENCY_INTERVALS.get(config.sync_frequency)
    if interval is None:
        return False
    last_run = config.last_scheduled_at
    if last_run is None:
        return True
    return last_run + interval <= now


def has_active_sync_job(
    config: FeishuBitableCollectionConfig,
    now=None,
) -> bool:
    now = now or timezone.now()
    active_since = now - timedelta(
        hours=get_active_sync_job_timeout_hours(),
    )
    return SyncJob.objects.filter(
        started_at__gte=active_since,
        status__in=[SyncStatus.PENDING, SyncStatus.RUNNING],
    ).filter(
        models.Q(source_key="", table_key="")
        | models.Q(source_key=config.source_key, table_key="")
        | models.Q(source_key=config.source_key, table_key=config.table_key)
    ).exists()
