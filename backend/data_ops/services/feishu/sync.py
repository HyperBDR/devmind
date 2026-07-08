from __future__ import annotations

import re
from datetime import datetime
from datetime import timezone as datetime_timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from data_ops.models import (
    Contract,
    ContractHistory,
    DomesticLedger,
    OverseaProject,
    OverseaSettlement,
    Project,
    ProjectInit,
    ProjectScope,
    SalesRecord,
    SyncCursor,
    SyncIssueCode,
    SyncJob,
    SyncStatus,
    SyncTableStatus,
)

from .client import FeishuBitableClient, _classify_feishu_error
from .global_config import get_feishu_date_timezone_name
from .mappings import BITABLE_SOURCES, iter_bitable_tables


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
def run_full_sync(*, job_id: str | None = None) -> dict:
    return _run_sync(source_key=None, table_key=None, job_id=job_id)


def run_incremental_sync(
    *,
    source_key: str,
    job_id: str | None = None,
) -> dict:
    if source_key not in BITABLE_SOURCES:
        raise ValueError(f"Unknown source_key: {source_key}")
    return _run_sync(source_key=source_key, table_key=None, job_id=job_id)


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
    )


def _run_sync(
    *,
    source_key: str | None,
    table_key: str | None,
    job_id: str | None,
) -> dict:
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
    client = FeishuBitableClient()

    try:
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
            )
            _refresh_sync_lock(lock_token)
            results[f"{resolved_source_key}.{table_key}"] = table_result
            total_records += table_result.get("records", 0)
            if table_result["status"] == SyncStatus.FAILED:
                failed_tables += 1
            elif table_result["status"] == SyncStatus.WARNING:
                warning_tables += 1

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


def _sync_one_table(
    *,
    client: FeishuBitableClient,
    source_key: str,
    source: dict,
    table_key: str,
    table: dict,
    lock_token: str = "",
) -> dict:
    app_token = source["app_token"]
    table_id = table["table_id"]
    table_name = table["name"]
    expected_fields = table.get("expected_fields", [])

    check = client.check_table_access(
        app_token=app_token,
        table_id=table_id,
        table_name=table_name,
        expected_fields=expected_fields,
    )
    check.expected_min_records = table.get("expected_min_records")
    if check.status == SyncStatus.FAILED:
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
        return {"status": SyncStatus.FAILED, "records": 0}

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
        return {"status": SyncStatus.FAILED, "records": 0}
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
        return {"status": SyncStatus.FAILED, "records": 0}

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

    previous = SyncTableStatus.objects.filter(
        source_key=source_key,
        table_key=table_key,
    ).first()
    expected_floor = _current_record_floor(
        previous=previous,
        expected_min_records=table.get("expected_min_records"),
    )
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

    model_name = table["model"]
    with transaction.atomic():
        count = _upsert_records(
            model_name=model_name,
            records=records,
            field_map=table.get("field_map", {}),
            app_token=app_token,
            table_id=table_id,
        )
        if model_name == "project_init":
            _sync_projects_from_project_init(
                records,
                table,
                app_token,
                table_id,
            )
        elif model_name == "oversea_project":
            _sync_projects_from_oversea(records, table, app_token, table_id)
        history_count = 0
        history_error = None
        if model_name == "contract":
            history_count, history_error = _sync_contract_histories(
                client=client,
                records=records,
                app_token=app_token,
                table_id=table_id,
                table_name=table_name,
                lock_token=lock_token,
            )
        _update_cursor(
            source_key=source_key,
            table_key=table_key,
            app_token=app_token,
            table_id=table_id,
            table_name=table_name,
            record_count=count,
        )

    final_status = SyncStatus.OK
    issue_code = ""
    message = ""
    resolution_hint = ""
    if history_error:
        final_status = SyncStatus.WARNING
        issue_code = history_error.issue_code
        message = history_error.message
        resolution_hint = history_error.resolution_hint

    _save_table_status(
        source_key=source_key,
        table_key=table_key,
        app_token=app_token,
        table_id=table_id,
        table_name=table_name,
        status=final_status,
        issue_code=issue_code,
        message=message,
        resolution_hint=resolution_hint,
        record_count=count,
        expected_fields=expected_fields,
        missing_fields=[],
        expected_min_records=table.get("expected_min_records"),
    )
    return {
        "status": final_status,
        "records": count,
        "total": total,
        "incomplete": incomplete,
        "history_entries": history_count,
    }


def _upsert_records(
    *,
    model_name: str,
    records: list[dict],
    field_map: dict[str, str],
    app_token: str,
    table_id: str,
) -> int:
    model = MODEL_MAP[model_name]
    source_record_ids = []
    for record in records:
        values = _map_record(record, field_map, app_token, table_id)
        source_record_ids.append(values["source_record_id"])
        if model_name == "domestic_ledger_receipt":
            values["ledger_type"] = values.get("ledger_type") or "收入"
        elif model_name == "domestic_ledger_payment":
            values["ledger_type"] = values.get("ledger_type") or "支出"
        model.all_objects.update_or_create(
            source_app_token=app_token,
            source_table_id=table_id,
            source_record_id=values["source_record_id"],
            defaults=values,
        )
    _mark_missing_inactive(
        model=model,
        app_token=app_token,
        table_id=table_id,
        source_record_ids=source_record_ids,
    )
    return len(records)


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
        "is_active": True,
        "synced_at": timezone.now(),
    }
    for source_field, model_field in field_map.items():
        if source_field not in fields:
            continue
        values[model_field] = _parse_value(fields[source_field], model_field)
    return values


def _sync_contract_histories(
    *,
    client: FeishuBitableClient,
    records: list[dict],
    app_token: str,
    table_id: str,
    table_name: str,
    lock_token: str = "",
) -> tuple[int, object | None]:
    written = 0
    first_error = None
    for record in records:
        if lock_token:
            _refresh_sync_lock(lock_token)
        record_id = record.get("record_id", "")
        if not record_id:
            continue
        contract = Contract.all_objects.filter(
            source_app_token=app_token,
            source_table_id=table_id,
            source_record_id=record_id,
        ).first()
        if contract is None:
            continue
        try:
            history_items = client.list_record_history(
                app_token,
                table_id,
                record_id,
            )
        except httpx.HTTPStatusError as exc:
            first_error = first_error or _classify_feishu_error(
                table_name=table_name,
                stage="记录历史读取",
                response=exc.response,
            )
            continue
        except Exception as exc:
            first_error = first_error or _classify_feishu_error(
                table_name=table_name,
                stage="记录历史读取",
                exc=exc,
            )
            continue
        written += _upsert_contract_history(
            contract=contract,
            source_record_id=record_id,
            history_items=history_items,
        )
    return written, first_error


def _refresh_sync_lock(lock_token: str) -> None:
    if not lock_token:
        return
    if cache.get(SYNC_LOCK_KEY) == lock_token:
        cache.set(SYNC_LOCK_KEY, lock_token, timeout=SYNC_LOCK_TIMEOUT)


def _upsert_contract_history(
    *,
    contract: Contract,
    source_record_id: str,
    history_items: list[dict],
) -> int:
    written = 0
    for item in history_items:
        changed_at = _parse_history_time(item.get("update_time"))
        if changed_at is None:
            continue
        updater = item.get("updater") or {}
        old_value = _parse_text(item.get("pre_value"))
        new_value = _parse_text(item.get("cur_value"))
        ContractHistory.objects.update_or_create(
            contract=contract,
            source_record_id=source_record_id,
            field_name=str(item.get("field_name") or ""),
            changed_at=changed_at,
            defaults={
                "old_value": old_value,
                "new_value": new_value,
                "changed_by": _parse_text(
                    updater.get("name") or updater.get("id"),
                ),
                "change_type": _history_change_type(item),
            },
        )
        written += 1
    return written


def _parse_history_time(raw: Any):
    if not raw:
        return None
    try:
        timestamp = int(raw) / 1000
    except (TypeError, ValueError):
        return None
    parsed = datetime.fromtimestamp(timestamp, tz=datetime_timezone.utc)
    return parsed


def _history_change_type(item: dict) -> str:
    if item.get("pre_value") is None:
        return "create"
    if item.get("cur_value") is None:
        return "delete"
    return "update"


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
