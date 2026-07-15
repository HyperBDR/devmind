from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from datetime import timezone as datetime_timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.utils import timezone

from data_ops.models import (
    Contract,
    DomesticLedger,
    OverseaProject,
    OverseaSettlement,
    Project,
    ProjectInit,
    ProjectScope,
    SalesRecord,
    SourceRecordChange,
    SourceRecordChangeType,
    SyncCursor,
    SyncIssueCode,
    SyncJob,
    SyncStatus,
    SyncTableStatus,
)

from .client import (
    FeishuBitableClient,
    FeishuCheckResult,
    build_bitable_table_url,
    _classify_feishu_error,
)
from .global_config import get_feishu_date_timezone_name
from .mappings import ACTIVE_SOURCE_KEYS, iter_bitable_tables


MODEL_MAP = {
    "contract": Contract,
    "sales_record": SalesRecord,
    "domestic_ledger_receipt": DomesticLedger,
    "domestic_ledger_payment": DomesticLedger,
    "project_init": ProjectInit,
    "oversea_project": OverseaProject,
    "oversea_settlement": OverseaSettlement,
}

DATE_FIELDS = {
    "allocation_date",
    "expiry_date",
    "huawei_cloud_expiry",
    "invoice_date",
    "license_expiry",
    "oa_initiation_date",
    "order_date",
    "payment_date",
    "receipt_time",
    "service_end",
    "service_start",
    "signing_date",
    "expected_payment_date",
}

DECIMAL_FIELDS = {
    "actual_revenue",
    "aisun_sub_fee_estimate",
    "allocation_quantity",
    "cost_usd",
    "estimated_amount",
    "estimated_exchange_rate",
    "estimated_revenue",
    "invoice_amount",
    "license_quantity",
    "license_unit_price",
    "outstanding",
    "overseas_initial_quote",
    "payment_amount",
    "payment_received",
    "purchase_quantity",
    "received_amount",
    "receivable_amount",
    "revenue_diff",
    "single_receive_amount",
    "stat_amount_usd",
    "tax_amount",
    "total_amount",
    "total_amount_usd",
    "total_contract_amount",
    "unit_price",
}

INTEGER_FIELDS = {"order_month", "order_year", "purchase_cycle"}
BOOLEAN_FIELDS = {"has_contract_attachment", "has_initial_quote_attachment"}
SYNC_LOCK_KEY = "data_ops:feishu_sync:global_lock"
SYNC_LOCK_TIMEOUT = 60 * 60 * 2


def run_full_sync(
    *,
    job_id: str | None = None,
    force: bool = True,
) -> dict:
    return _run_sync(
        source_key=None,
        table_key=None,
        job_id=job_id,
        skip_unchanged=not force,
    )


def run_incremental_sync(
    *,
    source_key: str,
    job_id: str | None = None,
) -> dict:
    if source_key not in ACTIVE_SOURCE_KEYS:
        raise ValueError(f"Unknown source_key: {source_key}")
    return _run_sync(
        source_key=source_key,
        table_key=None,
        job_id=job_id,
        skip_unchanged=True,
    )


def run_table_sync(
    *,
    source_key: str,
    table_key: str,
    job_id: str | None = None,
) -> dict:
    table_iter = list(
        iter_bitable_tables(
            source_filter=source_key,
            table_filter=table_key,
        )
    )
    if not table_iter:
        raise ValueError(
            f"Unknown or disabled table: {source_key}/{table_key}"
        )
    return _run_sync(
        source_key=source_key,
        table_key=table_key,
        job_id=job_id,
        skip_unchanged=False,
    )


def _run_sync(
    *,
    source_key: str | None,
    table_key: str | None,
    job_id: str | None,
    skip_unchanged: bool,
) -> dict:
    from .config import (
        discover_bitable_table_ids,
        ensure_bitable_collection_configs,
    )

    ensure_bitable_collection_configs()
    job = _resolve_job(
        job_id=job_id,
        source_key=source_key,
        table_key=table_key,
    )
    lock_token = f"{job.id}:{uuid4()}"
    if not cache.add(SYNC_LOCK_KEY, lock_token, timeout=SYNC_LOCK_TIMEOUT):
        now = timezone.now()
        job.status = SyncStatus.WARNING
        job.finished_at = now
        job.error_message = (
            "已有 Data Ops 飞书同步任务正在执行，"
            "本次任务已跳过。"
        )
        job.save(
            update_fields=[
                "status",
                "finished_at",
                "error_message",
            ]
        )
        return {
            "status": job.status,
            "records_synced": 0,
            "failed_tables": 0,
            "warning_tables": 1,
            "results": {},
            "skipped": True,
            "reason": job.error_message,
        }

    job.status = SyncStatus.RUNNING
    job.started_at = timezone.now()
    job.finished_at = None
    job.error_message = ""
    job.locked_by = lock_token
    job.lock_acquired_at = job.started_at
    job.save(
        update_fields=[
            "status",
            "started_at",
            "finished_at",
            "error_message",
            "locked_by",
            "lock_acquired_at",
        ]
    )

    results = {}
    total_records = 0
    failed_tables = 0
    warning_tables = 0
    skipped_tables = 0
    client = FeishuBitableClient()

    try:
        discovery = discover_bitable_table_ids(
            client=client,
            source_key=source_key,
            table_key=table_key,
        )
        table_iter = list(
            iter_bitable_tables(
                source_filter=source_key,
                table_filter=table_key,
            )
        )
        for resolved_source_key, source, table_key, table in table_iter:
            _refresh_sync_lock(lock_token)
            table_result = _sync_one_table(
                client=client,
                source_key=resolved_source_key,
                source=source,
                table_key=table_key,
                table=table,
                lock_token=lock_token,
                skip_unchanged=skip_unchanged,
            )
            _refresh_sync_lock(lock_token)
            results[f"{resolved_source_key}.{table_key}"] = table_result
            total_records += table_result.get("records", 0)
            if table_result["status"] == SyncStatus.FAILED:
                failed_tables += 1
            elif table_result["status"] == SyncStatus.WARNING:
                warning_tables += 1
            if table_result.get("skipped"):
                skipped_tables += 1

        if failed_tables:
            job.status = SyncStatus.FAILED
        elif warning_tables:
            job.status = SyncStatus.WARNING
        else:
            job.status = SyncStatus.OK
        job.records_synced = total_records
        job.results = results
        return {
            "status": job.status,
            "records_synced": total_records,
            "failed_tables": failed_tables,
            "warning_tables": warning_tables,
            "skipped_tables": skipped_tables,
            "discovery": discovery,
            "results": results,
        }
    except Exception as exc:
        job.status = SyncStatus.FAILED
        job.error_message = str(exc)
        job.results = results
        raise
    finally:
        job.finished_at = timezone.now()
        job.locked_by = ""
        job.save(
            update_fields=[
                "status",
                "finished_at",
                "records_synced",
                "error_message",
                "results",
                "locked_by",
            ]
        )
        if cache.get(SYNC_LOCK_KEY) == lock_token:
            cache.delete(SYNC_LOCK_KEY)


def _resolve_job(
    *,
    job_id: str | None,
    source_key: str | None,
    table_key: str | None,
) -> SyncJob:
    if job_id:
        return SyncJob.objects.get(id=job_id)
    return SyncJob.objects.create(
        source_key=source_key or "",
        table_key=table_key or "",
        status=SyncStatus.PENDING,
    )


def _failed_table_result(check) -> dict:
    return {
        "status": SyncStatus.FAILED,
        "records": 0,
        "issue_code": check.issue_code,
        "message": check.message,
        "resolution_hint": check.resolution_hint,
        "feishu_detail": check.feishu_detail,
    }


def _config_missing_table_result(
    *,
    table_name: str,
    app_token: str,
    table_id: str,
):
    from .client import FeishuCheckResult

    return FeishuCheckResult(
        status=SyncStatus.FAILED,
        issue_code=SyncIssueCode.CONFIG_MISSING,
        message=(
            f"飞书多维表格「{table_name}」缺少 app_token 或 "
            "table_id，无法同步。"
        ),
        resolution_hint=(
            "当前只配置了 base 地址。请确认应用能通过 "
            "tables 接口列出数据表，或提供具体 table 链接。"
        ),
        feishu_detail={
            "stage": "本地配置检查",
            "table_url": build_bitable_table_url(app_token, table_id),
            "app_token": app_token,
            "table_id": table_id,
        },
    )


def _check_expected_fields(
    *,
    client: FeishuBitableClient,
    app_token: str,
    table_id: str,
    table_name: str,
    expected_fields: list[str],
) -> FeishuCheckResult | None:
    if not expected_fields:
        return None
    try:
        actual_fields = set(client.list_fields(app_token, table_id))
    except httpx.HTTPStatusError as exc:
        return _classify_feishu_error(
            table_name=table_name,
            stage="字段读取",
            response=exc.response,
        )
    except Exception as exc:
        return _classify_feishu_error(
            table_name=table_name,
            stage="字段读取",
            exc=exc,
        )

    missing_fields = [
        field for field in expected_fields if field not in actual_fields
    ]
    if not missing_fields:
        return None
    return FeishuCheckResult(
        status=SyncStatus.FAILED,
        issue_code=SyncIssueCode.FIELD_MISSING,
        message=(
            f"飞书多维表格「{table_name}」缺少预期字段："
            f"{', '.join(missing_fields)}。"
        ),
        resolution_hint=(
            "请恢复源表字段或更新字段映射后再同步，"
            "避免用空值覆盖已有数据。"
        ),
        expected_fields=expected_fields,
        missing_fields=missing_fields,
    )


def _sync_one_table(
    *,
    client: FeishuBitableClient,
    source_key: str,
    source: dict,
    table_key: str,
    table: dict,
    lock_token: str = "",
    skip_unchanged: bool = False,
) -> dict:
    app_token = source["app_token"]
    table_id = table["table_id"]
    table_name = table["name"]
    expected_fields = table.get("expected_fields", [])

    if not app_token or not table_id:
        result = _config_missing_table_result(
            table_name=table_name,
            app_token=app_token,
            table_id=table_id,
        )
        _save_table_status_from_check(
            source_key,
            table_key,
            app_token,
            table_id,
            table_name,
            result,
            expected_fields,
        )
        return _failed_table_result(result)

    result = _check_expected_fields(
        client=client,
        app_token=app_token,
        table_id=table_id,
        table_name=table_name,
        expected_fields=expected_fields,
    )
    if result is not None:
        _save_table_status_from_check(
            source_key,
            table_key,
            app_token,
            table_id,
            table_name,
            result,
            expected_fields,
        )
        return _failed_table_result(result)

    try:
        records, incomplete, total = client.list_records(app_token, table_id)
    except httpx.HTTPStatusError as exc:
        result = _classify_feishu_error(
            table_name=table_name,
            stage="记录读取",
            response=exc.response,
        )
        _save_table_status_from_check(
            source_key,
            table_key,
            app_token,
            table_id,
            table_name,
            result,
            expected_fields,
        )
        return _failed_table_result(result)
    except Exception as exc:
        result = _classify_feishu_error(
            table_name=table_name,
            stage="记录读取",
            exc=exc,
        )
        _save_table_status_from_check(
            source_key,
            table_key,
            app_token,
            table_id,
            table_name,
            result,
            expected_fields,
        )
        return _failed_table_result(result)

    if incomplete:
        _save_table_status(
            source_key=source_key,
            table_key=table_key,
            app_token=app_token,
            table_id=table_id,
            table_name=table_name,
            status=SyncStatus.FAILED,
            issue_code=SyncIssueCode.PAGINATION_INCOMPLETE,
            message=(
                f"飞书多维表格「{table_name}」"
                "分页读取不完整。"
            ),
            resolution_hint=(
                "请重试同步；若持续失败，"
                "请检查飞书 API 返回。"
            ),
            record_count=len(records),
            expected_fields=expected_fields,
            missing_fields=[],
            expected_min_records=table.get("expected_min_records"),
        )
        return {
            "status": SyncStatus.FAILED,
            "records": 0,
            "total": total,
            "incomplete": True,
        }

    expected_floor = max(int(table.get("expected_min_records") or 0), 0)
    if len(records) < expected_floor:
        _save_table_status(
            source_key=source_key,
            table_key=table_key,
            app_token=app_token,
            table_id=table_id,
            table_name=table_name,
            status=SyncStatus.FAILED,
            issue_code=SyncIssueCode.ZERO_RECORDS_UNEXPECTED,
            message=(
                f"飞书多维表格「{table_name}」本次仅读取到 "
                f"{len(records)} 条记录，低于历史或最低预期 "
                f"{expected_floor} 条。"
            ),
            resolution_hint=(
                "请确认飞书应用的数据表记录读取权限、"
                "视图过滤、表格共享范围和源表数据"
                "是否完整。"
            ),
            record_count=len(records),
            expected_fields=expected_fields,
            missing_fields=[],
            expected_min_records=table.get("expected_min_records"),
        )
        return {
            "status": SyncStatus.FAILED,
            "records": 0,
            "total": total,
            "expected_record_floor": expected_floor,
        }

    source_revision = _build_record_revision(records)
    cursor = SyncCursor.objects.filter(
        app_token=app_token,
        table_id=table_id,
    ).first()
    if (
        skip_unchanged
        and source_revision
        and cursor
        and cursor.source_revision == source_revision
        and cursor.record_count == len(records)
    ):
        message = (
            f"飞书多维表格「{table_name}」无修改，"
            "已跳过同步。"
        )
        _save_table_status(
            source_key=source_key,
            table_key=table_key,
            app_token=app_token,
            table_id=table_id,
            table_name=table_name,
            status=SyncStatus.OK,
            issue_code="",
            message=message,
            resolution_hint="",
            record_count=len(records),
            expected_fields=expected_fields,
            missing_fields=[],
            expected_min_records=table.get("expected_min_records"),
        )
        return {
            "status": SyncStatus.OK,
            "records": 0,
            "source_records": len(records),
            "total": total,
            "incomplete": False,
            "skipped": True,
            "reason": message,
        }

    model_name = table["model"]
    with transaction.atomic():
        stats = _upsert_records(
            model_name=model_name,
            records=records,
            field_map=table.get("field_map", {}),
            app_token=app_token,
            table_id=table_id,
            source_key=source_key,
            table_key=table_key,
        )
        source_count = stats["source_records"]
        changed_count = sum(
            stats[key]
            for key in ("created", "updated", "deleted", "restored")
        )
        if model_name == "project_init" and changed_count:
            _sync_projects_from_project_init(
                records,
                table,
                app_token,
                table_id,
            )
        elif model_name == "oversea_project" and changed_count:
            _sync_projects_from_oversea(records, table, app_token, table_id)
        _update_cursor(
            source_key=source_key,
            table_key=table_key,
            app_token=app_token,
            table_id=table_id,
            table_name=table_name,
            record_count=source_count,
            source_revision=source_revision,
        )

    _save_table_status(
        source_key=source_key,
        table_key=table_key,
        app_token=app_token,
        table_id=table_id,
        table_name=table_name,
        status=SyncStatus.OK,
        issue_code="",
        message="",
        resolution_hint="",
        record_count=source_count,
        expected_fields=expected_fields,
        missing_fields=[],
        expected_min_records=table.get("expected_min_records"),
    )
    return {
        "status": SyncStatus.OK,
        "records": changed_count,
        "source_records": source_count,
        "total": total,
        "incomplete": incomplete,
        "skipped": False,
        **stats,
    }


def _build_record_revision(records: list[dict]) -> str:
    if any(not record.get("record_id") for record in records):
        return ""

    revision_items = []
    for record in records:
        item = {
            "record_id": str(record["record_id"]),
            "fields": record.get("fields", {}),
        }
        if record.get("last_modified_time") not in (None, ""):
            item["last_modified_time"] = str(
                record["last_modified_time"]
            )
        revision_items.append(item)

    payload = json.dumps(
        sorted(revision_items, key=lambda item: item["record_id"]),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _upsert_records(
    *,
    model_name: str,
    records: list[dict],
    field_map: dict[str, str],
    app_token: str,
    table_id: str,
    source_key: str = "",
    table_key: str = "",
) -> dict[str, int]:
    model = MODEL_MAP[model_name]
    existing_records = {
        item.source_record_id: item
        for item in model.all_objects.filter(
            source_app_token=app_token,
            source_table_id=table_id,
        )
    }
    is_initial_snapshot = not existing_records
    now = timezone.now()
    source_record_ids = []
    to_create = []
    to_update = []
    metadata_updates = []
    to_deactivate = []
    change_events = []
    unchanged = 0
    restored = 0
    business_fields = set(field_map.values())

    for record in records:
        values = _map_record(record, field_map, app_token, table_id)
        values = _coerce_model_values(model, values)
        if model_name == "domestic_ledger_receipt":
            values["ledger_type"] = values.get("ledger_type") or "收入"
        elif model_name == "domestic_ledger_payment":
            values["ledger_type"] = values.get("ledger_type") or "支出"
        source_record_id = values["source_record_id"]
        source_record_ids.append(source_record_id)
        existing = existing_records.get(source_record_id)
        if existing is None:
            to_create.append(model(**values))
            if not is_initial_snapshot:
                change_events.append(
                    _build_change_event(
                        source_key=source_key,
                        table_key=table_key,
                        model_name=model_name,
                        source_record_id=source_record_id,
                        change_type=SourceRecordChangeType.CREATED,
                        changed_fields=business_fields,
                        source_changed_fields=set(values["raw_data"].keys()),
                        before_values={},
                        after_values={
                            field: values.get(field)
                            for field in business_fields
                        },
                        source_modified_time=values["source_modified_time"],
                    )
                )
            continue

        existing_hash = existing.source_content_hash
        if not existing_hash:
            existing_hash = _build_record_content_hash(existing.raw_data)
        content_changed = existing_hash != values["source_content_hash"]
        was_inactive = not existing.is_active
        if not content_changed and not was_inactive:
            metadata_changed = False
            for field in ("source_modified_time", "source_content_hash"):
                if getattr(existing, field) != values[field]:
                    setattr(existing, field, values[field])
                    metadata_changed = True
            if metadata_changed:
                metadata_updates.append(existing)
            unchanged += 1
            continue

        before_values, after_values = _business_value_diff(
            existing,
            values,
            business_fields,
        )
        changed_fields = set(before_values.keys())
        if was_inactive:
            before_values["is_active"] = False
            after_values["is_active"] = True
            changed_fields.add("is_active")
            restored += 1
            change_type = SourceRecordChangeType.RESTORED
        else:
            change_type = SourceRecordChangeType.UPDATED
        source_changed_fields = _source_changed_fields(
            existing.raw_data,
            values["raw_data"],
        )
        _assign_values(existing, values)
        to_update.append(existing)
        if changed_fields:
            change_events.append(
                _build_change_event(
                    source_key=source_key,
                    table_key=table_key,
                    model_name=model_name,
                    source_record_id=source_record_id,
                    change_type=change_type,
                    changed_fields=changed_fields,
                    source_changed_fields=source_changed_fields,
                    before_values=before_values,
                    after_values=after_values,
                    source_modified_time=values[
                        "source_modified_time"
                    ],
                )
            )

    remote_ids = set(source_record_ids)
    for source_record_id, existing in existing_records.items():
        if source_record_id in remote_ids or not existing.is_active:
            continue
        existing.is_active = False
        existing.synced_at = now
        to_deactivate.append(existing)
        change_events.append(
            _build_change_event(
                source_key=source_key,
                table_key=table_key,
                model_name=model_name,
                source_record_id=source_record_id,
                change_type=SourceRecordChangeType.DELETED,
                changed_fields={"is_active"},
                source_changed_fields=set(),
                before_values={"is_active": True},
                after_values={"is_active": False},
                source_modified_time=existing.source_modified_time,
            )
        )

    model.all_objects.bulk_create(to_create, batch_size=500)
    if to_update:
        model.all_objects.bulk_update(
            to_update,
            _sync_update_fields(model, field_map=field_map),
            batch_size=500,
        )
    if metadata_updates:
        model.all_objects.bulk_update(
            metadata_updates,
            ["source_modified_time", "source_content_hash"],
            batch_size=500,
        )
    if to_deactivate:
        model.all_objects.bulk_update(
            to_deactivate,
            ["is_active", "synced_at"],
            batch_size=500,
        )
    SourceRecordChange.objects.bulk_create(change_events, batch_size=500)

    updated = len(to_update) - restored
    return {
        "source_records": len(records),
        "created": len(to_create),
        "updated": updated,
        "deleted": len(to_deactivate),
        "restored": restored,
        "unchanged": unchanged,
        "change_events": len(change_events),
    }


def _sync_update_fields(
    model,
    *,
    field_map: dict[str, str],
) -> list[str]:
    field_names = {
        "is_active",
        "owner_identities",
        "raw_data",
        "source_content_hash",
        "source_modified_time",
        "synced_at",
        *field_map.values(),
    }
    return [
        field.name
        for field in model._meta.concrete_fields
        if not field.primary_key and field.name in field_names
    ]


def _assign_values(instance, values: dict) -> None:
    for field, value in values.items():
        setattr(instance, field, value)


def _business_value_diff(
    existing,
    values: dict,
    business_fields: set[str],
) -> tuple[dict, dict]:
    before_values = {}
    after_values = {}
    for field in sorted(business_fields):
        before = getattr(existing, field)
        after = values.get(field)
        if before == after:
            continue
        before_values[field] = before
        after_values[field] = after
    return before_values, after_values


def _source_changed_fields(before: dict, after: dict) -> set[str]:
    return {
        field
        for field in set(before) | set(after)
        if before.get(field) != after.get(field)
    }


def _build_change_event(
    *,
    source_key: str,
    table_key: str,
    model_name: str,
    source_record_id: str,
    change_type: str,
    changed_fields: set[str],
    source_changed_fields: set[str],
    before_values: dict,
    after_values: dict,
    source_modified_time: int | None,
) -> SourceRecordChange:
    return SourceRecordChange(
        source_key=source_key,
        table_key=table_key,
        model_name=model_name,
        source_record_id=source_record_id,
        change_type=change_type,
        changed_fields=sorted(changed_fields),
        source_changed_fields=sorted(source_changed_fields),
        before_values=_json_safe_dict(before_values),
        after_values=_json_safe_dict(after_values),
        source_modified_time=source_modified_time,
    )


def _json_safe_dict(value: dict) -> dict:
    payload = json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False)
    return json.loads(payload)


def _build_record_content_hash(fields: dict) -> str:
    payload = json.dumps(
        fields,
        default=str,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _map_record(
    record: dict,
    field_map: dict[str, str],
    app_token: str,
    table_id: str,
) -> dict:
    fields = record.get("fields", {})
    values = {
        "source_record_id": record.get("record_id", ""),
        "source_app_token": app_token,
        "source_table_id": table_id,
        "raw_data": fields,
        "source_content_hash": _build_record_content_hash(fields),
        "source_modified_time": _parse_source_modified_time(
            record.get("last_modified_time"),
        ),
        "is_active": True,
        "synced_at": timezone.now(),
    }
    owner_identities = {}
    for source_field, model_field in field_map.items():
        if source_field not in fields:
            continue
        raw_value = fields[source_field]
        values[model_field] = _parse_value(raw_value, model_field)
        if model_field in {"sales_person", "project_owner"}:
            identities = _parse_owner_identities(raw_value)
            if identities:
                owner_identities[model_field] = identities
    for model_field in set(field_map.values()):
        if model_field not in values:
            values[model_field] = _parse_value(None, model_field)
    values["owner_identities"] = owner_identities
    return values


def _parse_source_modified_time(raw: Any) -> int | None:
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _parse_owner_identities(raw: Any) -> list[dict[str, str]]:
    """Extract stable Feishu person identities without contact details."""
    items = raw if isinstance(raw, list) else [raw]
    identities = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        open_id = str(item.get("open_id") or item.get("id") or "").strip()
        if not open_id or open_id in seen:
            continue
        identity = {"open_id": open_id}
        for key in ("name", "en_name"):
            value = str(item.get(key) or "").strip()
            if value:
                identity[key] = value
        identities.append(identity)
        seen.add(open_id)
    return identities


def _coerce_model_values(model, values: dict) -> dict:
    coerced = dict(values)
    for field in model._meta.fields:
        if field.name not in coerced:
            continue
        value = coerced[field.name]
        if isinstance(field, models.CharField) and isinstance(value, str):
            max_length = field.max_length
            if max_length and len(value) > max_length:
                coerced[field.name] = value[:max_length]
    return coerced


def _refresh_sync_lock(lock_token: str) -> None:
    if not lock_token:
        return
    if cache.get(SYNC_LOCK_KEY) == lock_token:
        cache.set(SYNC_LOCK_KEY, lock_token, timeout=SYNC_LOCK_TIMEOUT)


def _sync_projects_from_project_init(
    records: list[dict],
    table: dict,
    app_token: str,
    table_id: str,
) -> None:
    field_map = {
        **table.get("field_map", {}),
        "国内/国际": "domestic_type",
    }
    source_record_ids = []
    for record in records:
        values = _map_record(record, field_map, app_token, table_id)
        values = _coerce_model_values(Project, values)
        source_record_ids.append(values["source_record_id"])
        values["project_scope"] = ProjectScope.DOMESTIC
        values["is_landed"] = False
        amount = values.get("estimated_amount") or Decimal("0")
        values["is_high_potential"] = amount > Decimal("500000")
        Project.all_objects.update_or_create(
            source_app_token=app_token,
            source_table_id=table_id,
            source_record_id=values["source_record_id"],
            defaults=values,
        )
    _mark_missing_inactive(
        model=Project,
        app_token=app_token,
        table_id=table_id,
        source_record_ids=source_record_ids,
    )


def _sync_projects_from_oversea(
    records: list[dict],
    table: dict,
    app_token: str,
    table_id: str,
) -> None:
    source_record_ids = []
    for record in records:
        values = _map_record(
            record,
            table.get("field_map", {}),
            app_token,
            table_id,
        )
        values = _coerce_model_values(Project, values)
        source_record_ids.append(values["source_record_id"])
        values["project_scope"] = ProjectScope.OVERSEAS
        values["is_landed"] = True
        values["license_days_left"] = _days_left(values.get("license_expiry"))
        values["license_risk_level"] = _risk_level(values["license_days_left"])
        Project.all_objects.update_or_create(
            source_app_token=app_token,
            source_table_id=table_id,
            source_record_id=values["source_record_id"],
            defaults=values,
        )
    _mark_missing_inactive(
        model=Project,
        app_token=app_token,
        table_id=table_id,
        source_record_ids=source_record_ids,
    )


def _mark_missing_inactive(
    *,
    model,
    app_token: str,
    table_id: str,
    source_record_ids: list[str],
) -> None:
    queryset = model.all_objects.filter(
        source_app_token=app_token,
        source_table_id=table_id,
        is_active=True,
    )
    if source_record_ids:
        queryset = queryset.exclude(source_record_id__in=source_record_ids)
    queryset.update(is_active=False, synced_at=timezone.now())


def _parse_value(raw: Any, model_field: str) -> Any:
    if model_field in DATE_FIELDS:
        return _parse_date(raw)
    if model_field in DECIMAL_FIELDS:
        return _parse_decimal(raw)
    if model_field in INTEGER_FIELDS:
        return _parse_int(raw)
    if model_field in BOOLEAN_FIELDS:
        return _parse_bool(raw)
    return _parse_text(raw)


def _parse_text(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, (int, float, Decimal)):
        return str(raw)
    if isinstance(raw, dict):
        for key in ("text", "name", "en_name", "value", "record_id", "url"):
            if raw.get(key):
                return _parse_text(raw[key])
        return ""
    if isinstance(raw, list):
        parts = [_parse_text(item) for item in raw]
        return ", ".join(item for item in parts if item)
    return str(raw).strip()


def _parse_decimal(raw: Any) -> Decimal | None:
    text = _parse_text(raw)
    if not text:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if not cleaned or cleaned in {"-", ".", "-."}:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_int(raw: Any) -> int | None:
    value = _parse_decimal(raw)
    if value is None:
        return None
    return int(value)


def _parse_bool(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float, Decimal)):
        return raw != 0

    text = _parse_text(raw).strip().lower()
    if not text:
        return False
    if text in {"false", "no", "n", "0", "否", "无", "没有"}:
        return False
    if text in {"true", "yes", "y", "1", "是", "有"}:
        return True
    return False


def _parse_date(raw: Any):
    if raw in (None, ""):
        return None
    if isinstance(raw, (int, float)):
        timestamp = raw / 1000 if raw > 10_000_000_000 else raw
        return datetime.fromtimestamp(
            timestamp,
            tz=_feishu_date_timezone(),
        ).date()
    text = _parse_text(raw)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _feishu_date_timezone():
    try:
        return ZoneInfo(get_feishu_date_timezone_name())
    except ZoneInfoNotFoundError:
        return datetime_timezone.utc


def _days_left(value) -> int | None:
    if not value:
        return None
    return (value - timezone.localdate()).days


def _risk_level(days_left: int | None) -> str:
    if days_left is None:
        return ""
    if days_left <= 14:
        return "high"
    if days_left <= 30:
        return "medium"
    return "low"


def _update_cursor(
    *,
    source_key: str,
    table_key: str,
    app_token: str,
    table_id: str,
    table_name: str,
    record_count: int,
    source_revision: str,
) -> None:
    now = timezone.now()
    SyncCursor.objects.update_or_create(
        app_token=app_token,
        table_id=table_id,
        defaults={
            "source_key": source_key,
            "table_key": table_key,
            "table_name": table_name,
            "last_sync_at": now,
            "last_success_at": now,
            "record_count": record_count,
            "source_revision": source_revision,
        },
    )


def _save_table_status_from_check(
    source_key: str,
    table_key: str,
    app_token: str,
    table_id: str,
    table_name: str,
    check,
    expected_fields: list[str],
) -> None:
    _save_table_status(
        source_key=source_key,
        table_key=table_key,
        app_token=app_token,
        table_id=table_id,
        table_name=table_name,
        status=check.status,
        issue_code=check.issue_code,
        message=check.message,
        resolution_hint=check.resolution_hint,
        record_count=check.record_count,
        expected_fields=check.expected_fields or expected_fields,
        missing_fields=check.missing_fields or [],
        expected_min_records=check.expected_min_records,
    )


def _save_table_status(
    *,
    source_key: str,
    table_key: str,
    app_token: str,
    table_id: str,
    table_name: str,
    status: str,
    issue_code: str,
    message: str,
    resolution_hint: str,
    record_count: int,
    expected_fields: list[str],
    missing_fields: list[str],
    expected_min_records: int | None,
) -> None:
    previous = SyncTableStatus.objects.filter(
        source_key=source_key,
        table_key=table_key,
    ).first()
    expected_record_floor = _next_record_floor(
        previous=previous,
        status=status,
        record_count=record_count,
        expected_min_records=expected_min_records,
    )
    defaults = {
        "app_token": app_token,
        "table_id": table_id,
        "table_name": table_name,
        "status": status,
        "issue_code": issue_code,
        "message": message,
        "resolution_hint": resolution_hint,
        "record_count": record_count,
        "expected_fields": expected_fields,
        "missing_fields": missing_fields,
        "expected_min_records": expected_min_records,
        "expected_record_floor": expected_record_floor,
        "last_checked_at": timezone.now(),
    }
    if status == SyncStatus.OK:
        defaults["last_success_at"] = timezone.now()
    SyncTableStatus.objects.update_or_create(
        source_key=source_key,
        table_key=table_key,
        defaults=defaults,
    )


def _current_record_floor(
    *,
    previous: SyncTableStatus | None,
    expected_min_records: int | None,
) -> int:
    previous_floor = previous.expected_record_floor if previous else 0
    previous_count = previous.record_count if previous else 0
    configured_floor = expected_min_records or 0
    return max(configured_floor, previous_floor, previous_count)


def _next_record_floor(
    *,
    previous: SyncTableStatus | None,
    status: str,
    record_count: int,
    expected_min_records: int | None,
) -> int:
    floor = _current_record_floor(
        previous=previous,
        expected_min_records=expected_min_records,
    )
    if status == SyncStatus.OK and record_count >= floor:
        return max(floor, record_count)
    return floor
