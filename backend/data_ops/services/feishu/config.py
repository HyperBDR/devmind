from __future__ import annotations

import unicodedata
from collections import defaultdict
from datetime import timedelta

import httpx
from django.db import models
from django.http import Http404
from django.utils import timezone

from data_ops.models import (
    CollectionFrequency,
    FeishuBitableCollectionConfig,
    SyncCursor,
    SyncJob,
    SyncStatus,
    SyncTableStatus,
)

from .global_config import get_active_sync_job_timeout_hours
from .mappings import iter_default_collection_configs


FREQUENCY_INTERVALS = {
    CollectionFrequency.HOURLY: timedelta(hours=1),
    CollectionFrequency.DAILY: timedelta(days=1),
    CollectionFrequency.WEEKLY: timedelta(days=7),
}

LEGACY_DEFAULT_SOURCE_NAMES = {
    "Wabotech business management",
    "Overseas landed project statistics",
    "Overseas settlement statistics",
}

LEGACY_DEFAULT_TABLE_NAMES = {
    "Contracts before 2025.3",
    "Contracts after 2025.3",
    "Overseas license projects",
    "Sales product and service income ledger",
    "Project purchase expense ledger",
    "Project initiation",
    "Overseas landed project summary",
    "Overseas to domestic settlement orders",
}


def ensure_bitable_collection_configs() -> list[FeishuBitableCollectionConfig]:
    """Create missing Feishu Bitable collection configs from defaults."""
    _migrate_legacy_oversea_settlement_config()
    default_items = list(iter_default_collection_configs())
    _remove_unsupported_collection_configs(default_items)
    configs = []
    for item in default_items:
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
        _apply_default_config_values(config, item)
        configs.append(config)
    return configs


def _remove_unsupported_collection_configs(default_items: list[dict]) -> None:
    supported_keys = {
        (item["source_key"], item["table_key"])
        for item in default_items
    }
    for config in FeishuBitableCollectionConfig.objects.all():
        config_key = (config.source_key, config.table_key)
        if config_key in supported_keys:
            continue
        SyncCursor.objects.filter(
            source_key=config.source_key,
            table_key=config.table_key,
        ).delete()
        SyncTableStatus.objects.filter(
            source_key=config.source_key,
            table_key=config.table_key,
        ).delete()
        config.delete()


def _apply_default_config_values(
    config: FeishuBitableCollectionConfig,
    item: dict,
) -> None:
    update_fields = []
    default_app_token = item.get("app_token", "")

    if default_app_token and config.app_token != default_app_token:
        config.app_token = default_app_token
        update_fields.append("app_token")
        if config.table_id:
            config.table_id = ""
            update_fields.append("table_id")
    if item.get("source_name") and (
        not config.source_name
        or config.source_name in LEGACY_DEFAULT_SOURCE_NAMES
    ):
        config.source_name = item["source_name"]
        update_fields.append("source_name")
    if item.get("table_name") and (
        not config.table_name
        or config.table_name in LEGACY_DEFAULT_TABLE_NAMES
    ):
        config.table_name = item["table_name"]
        update_fields.append("table_name")
    if item.get("expected_min_records") and not config.expected_min_records:
        config.expected_min_records = item["expected_min_records"]
        update_fields.append("expected_min_records")
    if item.get("required_permissions") and not config.required_permissions:
        config.required_permissions = item["required_permissions"]
        update_fields.append("required_permissions")

    if update_fields:
        config.save(update_fields=[*update_fields, "updated_at"])


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


def discover_bitable_table_ids(
    *,
    client=None,
    source_key: str | None = None,
    table_key: str | None = None,
) -> dict:
    """Resolve table IDs from the live Feishu table directory."""
    if client is None:
        from .client import FeishuBitableClient

        client = FeishuBitableClient()

    configs = ensure_bitable_collection_configs()
    configs = [
        config
        for config in configs
        if (source_key is None or config.source_key == source_key)
        and (table_key is None or config.table_key == table_key)
    ]
    configs_by_token = defaultdict(list)
    result = {
        "app_tokens": 0,
        "tables_seen": 0,
        "matched": 0,
        "updated": 0,
        "unmatched": [],
        "ambiguous": [],
        "errors": [],
        "message": "",
    }

    for config in configs:
        if not config.app_token:
            result["errors"].append(
                {
                    "config": _config_key(config),
                    "message": "未配置飞书 Base App Token。",
                }
            )
            continue
        configs_by_token[config.app_token].append(config)

    result["app_tokens"] = len(configs_by_token)
    for app_token, token_configs in configs_by_token.items():
        try:
            tables = client.list_tables(app_token)
        except httpx.HTTPStatusError as exc:
            result["errors"].append(
                _discovery_http_error(token_configs, exc)
            )
            continue
        except Exception as exc:
            result["errors"].append(
                {
                    "configs": [
                        _config_key(config) for config in token_configs
                    ],
                    "message": (
                        "飞书表目录读取失败："
                        f"{type(exc).__name__}"
                    ),
                    "resolution_hint": (
                        "请检查服务到 open.feishu.cn 的网络、"
                        "DNS 和代理配置。"
                    ),
                }
            )
            continue

        result["tables_seen"] += len(tables)
        tables_by_name = defaultdict(list)
        for table in tables:
            if not isinstance(table, dict):
                continue
            table_name = _normalize_table_name(table.get("name"))
            table_id = str(table.get("table_id") or "").strip()
            if table_name and table_id:
                tables_by_name[table_name].append(table_id)

        for config in token_configs:
            config_key = _config_key(config)
            matches = list(
                dict.fromkeys(
                    tables_by_name.get(
                        _normalize_table_name(config.table_name),
                        [],
                    )
                )
            )
            if not matches:
                result["unmatched"].append(config_key)
                continue
            if len(matches) > 1:
                result["ambiguous"].append(config_key)
                continue

            result["matched"] += 1
            if config.table_id == matches[0]:
                continue
            config.table_id = matches[0]
            config.save(update_fields=["table_id", "updated_at"])
            result["updated"] += 1

    result["message"] = _discovery_message(result)
    return result


def _normalize_table_name(value) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).strip()


def _config_key(config: FeishuBitableCollectionConfig) -> str:
    return f"{config.source_key}/{config.table_key}"


def _discovery_http_error(configs, exc: httpx.HTTPStatusError) -> dict:
    response = exc.response
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    return {
        "configs": [_config_key(config) for config in configs],
        "message": "飞书表目录读取失败。",
        "http_status": response.status_code,
        "feishu_code": payload.get("code"),
        "feishu_msg": payload.get("msg") or "",
        "request_id": response.headers.get("x-request-id", ""),
        "log_id": response.headers.get("x-tt-logid", ""),
        "resolution_hint": (
            "请将飞书应用添加到对应多维表格，"
            "并授予多维表格读取权限。"
        ),
    }


def _discovery_message(result: dict) -> str:
    message = (
        f"已从 {result['app_tokens']} 个飞书 Base 发现 "
        f"{result['tables_seen']} 张表，匹配 {result['matched']} 张。"
    )
    if result["unmatched"]:
        message += f" {len(result['unmatched'])} 张未按表名匹配。"
    if result["ambiguous"]:
        message += f" {len(result['ambiguous'])} 张存在同名歧义。"
    if result["errors"]:
        message += (
            f" {len(result['errors'])} 个目录读取失败或缺少配置。"
        )
    return message


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
