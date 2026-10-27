"""Native background collection with resumable shards and atomic publication."""

import hashlib
import json
import logging
import math
import re
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import timedelta
from threading import Lock
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException

from agione_ops.client import AgioneOpsError
from agione_ops.models import ConnectionGrant, DatasetVersion, SourceConnection
from agione_ops.models import SyncRun
from agione_ops.native_analytics import (
    business_text, entity, normalize_log, parse_time, token,
)
from agione_ops.native_finance import amount
from agione_ops.native_client import NativeClient
from agione_ops.native_sync_models import (
    NativePublishedSnapshot, NativeStagedRecord, NativeSyncShard,
    NativeSyncState,
)
from agione_ops.permissions import get_connection_for

logger = logging.getLogger(__name__)

ROW_FIELDS = frozenset({
    "record_id", "customer_id", "model_id", "user_id", "project_id",
    "subject_type", "occurred_at", "result", "input_tokens",
    "output_tokens", "total_tokens", "failureKey", "latencyState",
})
RETRY_CODES = frozenset({
    "SOURCE_TIMEOUT", "SOURCE_RATE_LIMITED", "SOURCE_UNAVAILABLE",
    "SOURCE_UNREACHABLE", "SOURCE_REJECTED",
    "SOURCE_CHANGED_DURING_PAGING", "SOURCE_INCOMPLETE_PAGING",
})
FINANCE_FIELDS = frozenset({
    "available", "readOnly", "mode", "independentOfFilters", "scopeLabel",
    "totalCustomers", "coveredCustomers", "balanceCustomers",
    "cycleCustomers", "accountCount", "requestedMonth",
    "balanceDistributions", "periodSummaries", "balances", "cycles",
    "trend", "trendTotal", "trendCustomers", "trendReason", "oldestReadAt",
    "latestReadAt", "fetchedAt", "partial", "nextOffset",
    "processedCustomers", "offset", "latestObservations", "coverageBasis",
    "reason", "customerFinance",
})


def digest(data):
    """Digest only canonical normalized JSON, never transport payloads."""
    return hashlib.sha256(json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def validate_snapshot_data(data, content_digest):
    """Reject unknown persisted fields and credential-like free-form data."""
    def invalid():
        raise ValidationError("Invalid normalized native snapshot.")

    if not isinstance(data, dict) or set(data) not in ({
        "metadata", "rows", "customers", "models",
    }, {
        "metadata", "rows", "customers", "models", "finance",
    }):
        invalid()
    if digest(data) != content_digest:
        invalid()
    metadata = data["metadata"]
    if not isinstance(metadata, dict) or set(metadata) != {
        "configVersion", "credentialVersion", "roleState", "collectedAt",
    }:
        invalid()
    if any(type(metadata[x]) is not int or metadata[x] < 1 for x in (
        "configVersion", "credentialVersion",
    )) or metadata["roleState"] not in {"verified", "not_verified"}:
        invalid()
    parse_time(metadata["collectedAt"])
    if "finance" in data:
        finance = data["finance"]
        if (
            not isinstance(finance, dict)
            or not set(finance).issubset(FINANCE_FIELDS)
            or not {
                "available", "readOnly", "mode", "balanceDistributions",
                "periodSummaries", "balances", "cycles", "trend",
            }.issubset(finance)
            or finance["mode"] != "snapshot"
            or not isinstance(finance["trend"], list)
            or len(finance["trend"]) > 31
            or len(json.dumps(finance, ensure_ascii=True)) > 262144
        ):
            invalid()
        for row in finance["trend"]:
            if (
                not isinstance(row, dict)
                or set(row) not in (
                    {"date", "value"}, {"date", "value", "topUp"},
                )
                or not isinstance(row["date"], str)
                or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", row["date"])
                or amount(row["value"]) is None or amount(row["value"]) < 0
                or (row.get("topUp") is not None and (
                    amount(row["topUp"]) is None or amount(row["topUp"]) < 0
                ))
            ):
                invalid()
        shapes = (
            ("balanceDistributions", {
                "unit", "threshold", "healthyCustomers", "lowCustomers",
                "zeroCustomers", "negativeCustomers",
                "belowThresholdCustomers", "negativeTotal",
            }),
            ("periodSummaries", {
                "period", "unit", "topUp", "consumed", "adjustment",
                "roundOff", "consumingCustomers", "topUpCustomers",
                "coveredCustomers",
            }),
            ("balances", {"unit", "value"}),
            ("cycles", {"period", "unit", "value"}),
        )
        for field, keys in shapes:
            if not isinstance(finance[field], list) or any(
                not isinstance(row, dict) or set(row) != keys
                for row in finance[field]
            ):
                invalid()
        customer_finance = finance.get("customerFinance", {})
        if not isinstance(customer_finance, dict):
            invalid()
        for customer_id, value in customer_finance.items():
            entity(customer_id)
            if not isinstance(value, dict) or set(value) != {
                "accounts", "overview",
            }:
                invalid()
            if not isinstance(value["accounts"], list) or any(
                not isinstance(account, dict)
                or set(account) != {
                    "accountPurpose", "currency", "balance",
                }
                or account["accountPurpose"] != "USER_AVAILABLE"
                or not isinstance(account["currency"], str)
                or amount(account["balance"]) is None
                for account in value["accounts"]
            ):
                invalid()
            overview = value["overview"]
            allowed_overview = {
                "currentCycle", "cycleTopUpCredit",
                "cycleConsumedCredit", "cycleAdjustmentCredit",
                "cycleRoundOffCredit",
            }
            if (
                not isinstance(overview, dict)
                or not set(overview).issubset(allowed_overview)
                or (
                    overview
                    and not isinstance(overview.get("currentCycle"), str)
                )
                or any(
                    amount(item) is None
                    for key, item in overview.items()
                    if key != "currentCycle"
                )
            ):
                invalid()
    if not isinstance(data["customers"], dict):
        invalid()
    for key, value in data["customers"].items():
        entity(key)
        if not isinstance(value, dict) or set(value) != {
            "name", "organizationName",
        }:
            invalid()
        for label in value.values():
            if label is not None and business_text(label) != label:
                invalid()
    if not isinstance(data["models"], dict):
        invalid()
    for key, value in data["models"].items():
        entity(key)
        if business_text(value) != value:
            invalid()
    if not isinstance(data["rows"], list):
        invalid()
    seen = set()
    for row in data["rows"]:
        if not isinstance(row, dict) or set(row) != ROW_FIELDS:
            invalid()
        entity(row["record_id"])
        if row["record_id"] in seen:
            invalid()
        seen.add(row["record_id"])
        for field in ("customer_id", "model_id", "user_id", "project_id"):
            entity(row[field], optional=True)
        if row["customer_id"] not in data["customers"]:
            invalid()
        parse_time(row["occurred_at"])
        if row["result"] not in {"SUCCESS", "FAILURE", "UNKNOWN"}:
            invalid()
        if row["subject_type"] not in {"USER", "PROJECT"}:
            invalid()
        if row["latencyState"] != "UNIT_UNCONFIRMED":
            invalid()
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            if row[key] is not None and token(row[key]) is None:
                invalid()

        if not isinstance(row["failureKey"], str) or not re.fullmatch(
            r"(?:NOT_APPLICABLE|UNKNOWN|source:[A-Za-z0-9_:-]{1,60})",
            row["failureKey"],
        ):
            invalid()


def require_native(connection):
    """A native gate is separate from, never a relaxation of synthetic gates."""
    if getattr(settings, "AGIONE_OPS_NATIVE_ENABLED", False) is not True:
        raise AgioneOpsError("NATIVE_DISABLED", status_code=503)
    if connection.source_kind != "native" or not connection.enabled:
        raise AgioneOpsError("SOURCE_KIND_FORBIDDEN", status_code=403)
    if not connection.endpoint or not connection.expected_tenant_id:
        raise AgioneOpsError("SOURCE_NOT_CONFIGURED", status_code=503)


def authorize_native_run(run, connection):
    """Reload active-user and grant authority at each checkpoint/publication."""
    require_native(connection)
    user = get_user_model().objects.filter(pk=run.initiated_by_id).first()
    if user is None or not user.is_active:
        raise AgioneOpsError("ACCESS_REVOKED", status_code=403)
    try:
        get_connection_for(user, connection.pk, "run_sync")
    except APIException:
        raise AgioneOpsError("ACCESS_REVOKED", status_code=403) from None
    grant = ConnectionGrant.objects.filter(
        connection=connection, user=user, can_sync=True,
    ).first()
    if grant is None or grant.revision != run.grant_revision:
        raise AgioneOpsError("ACCESS_REVOKED", status_code=403)
    if (
        connection.config_version != run.config_version
        or connection.credential_version != run.credential_version
    ):
        raise AgioneOpsError("CONFIGURATION_CHANGED", status_code=409)


def _setting(name, default, minimum, maximum):
    value = getattr(settings, name, default)
    if type(value) is not int or not minimum <= value <= maximum:
        raise AgioneOpsError("NATIVE_SYNC_CONFIG_INVALID", status_code=503)
    return value


def _identity(client, connection):
    value = client.identity()
    if not isinstance(value, dict) or any(
        value.get(key) != getattr(connection, field)
        for key, field in (
            ("tenant_id", "expected_tenant_id"),
            ("platform", "platform"),
            ("principal_kind", "principal_kind"),
        )
    ):
        raise AgioneOpsError("SOURCE_IDENTITY_MISMATCH", status_code=403)
    return value


def _prepare(run, connection, client, checkpoint):
    """Persist directory/model versions before starting call-log shards."""
    state, _ = NativeSyncState.objects.get_or_create(run=run)
    if not state.directory_complete:
        checkpoint("directory")
        operator = connection.principal_kind == "operator"
        key = "tenantId" if operator else "customerTenantId"
        path = "/coperation/tenant/" + (
            "op-customers" if operator else "provider-customers"
        )
        directory, seen, total = {}, set(), None
        for page in range(1, 101):
            checkpoint("directory")
            raw = client.get(path, {
                **({"identityCode": "EU"} if operator else {}),
                "pageIndex": page, "pageSize": 50,
            })
            checkpoint("directory")
            if not isinstance(raw, dict):
                raise AgioneOpsError("SOURCE_SHAPE_CHANGED")
            rows, current_total = raw.get("data"), raw.get("total")
            if (
                not isinstance(rows, list) or len(rows) > 50
                or type(current_total) is not int
                or not 0 <= current_total <= 5000
            ):
                raise AgioneOpsError("SOURCE_SHAPE_CHANGED")
            if total is None:
                total = current_total
            elif total != current_total:
                raise AgioneOpsError("SOURCE_CHANGED_DURING_PAGING")
            for row in rows:
                if not isinstance(row, dict):
                    raise AgioneOpsError("SOURCE_SHAPE_CHANGED")
                cid = entity(row.get(key))
                if cid in seen:
                    raise AgioneOpsError("SOURCE_DUPLICATE_PAGE")
                seen.add(cid)
                directory[cid] = {
                    "name": business_text(
                        row.get("customerName")
                        or row.get("organizationName")
                        or row.get("companyName"), cid,
                    ),
                    "organizationName": business_text(
                        row.get("organizationName"),
                    ),
                }
            if len(seen) == total:
                break
            if not rows or len(seen) > total:
                raise AgioneOpsError("SOURCE_INCOMPLETE_PAGING")
        else:
            raise AgioneOpsError("SOURCE_PAGE_LIMIT")
        count = len(directory)
        if not operator:
            cid = entity(connection.expected_tenant_id)
            directory.setdefault(cid, {"name": cid, "organizationName": None})
        checkpoint("models")
        raw_models = client.get("/xapi/observability/models/options")
        checkpoint("models")
        if not isinstance(raw_models, list) or len(raw_models) > 10000:
            raise AgioneOpsError("SOURCE_SHAPE_CHANGED")
        models = {}
        for row in raw_models:
            if not isinstance(row, dict):
                raise AgioneOpsError("SOURCE_SHAPE_CHANGED")
            mid = entity(row.get("modelId", row.get("id")))
            if mid in models:
                raise AgioneOpsError("SOURCE_DUPLICATE_DIRECTORY")
            models[mid] = business_text(
                row.get("metaModelName") or row.get("modelName"), mid,
            )
        state.directory = directory
        state.directory_count = count
        state.model_names = models
        state.directory_complete = True
        state.save()
    if not run.native_shards.exists():
        zone = ZoneInfo("Asia/Shanghai")
        at = run.window_start.astimezone(zone)
        while at < run.window_end:
            midnight = at.replace(
                hour=0, minute=0, second=0, microsecond=0,
            ) + timedelta(days=1)
            stop = min(midnight, run.window_end)
            NativeSyncShard.objects.get_or_create(
                run=run, window_start=at, window_end=stop,
            )
            at = stop
    return state



def _seed_timed_out(run, state, checkpoint):
    """Resume fully staged slices from an earlier timed-out collection."""
    if run.attempt != 1:
        return
    previous = SyncRun.objects.filter(
        connection_id=run.connection_id,
        config_version=run.config_version,
        credential_version=run.credential_version,
        initiated_by_id=run.initiated_by_id,
        grant_revision=run.grant_revision,
        created_at__gte=timezone.now() - timedelta(days=1),
        status="failed", error_code="NATIVE_SYNC_DEADLINE",
        native_state__directory_complete=True,
    ).exclude(pk=run.pk).select_related("native_state").order_by("-created_at")
    for old in previous:
        if set(old.native_state.directory) != set(state.directory):
            continue
        for shard in run.native_shards.filter(status="pending"):
            source = old.native_shards.filter(
                status="succeeded", window_start=shard.window_start,
                window_end=shard.window_end,
            ).first()
            if source is None:
                continue
            records = list(source.records.all())
            if len(records) != source.record_count or any(
                not isinstance(record.data, dict)
                or record.content_digest != digest(record.data)
                or not shard.window_start <= record.occurred_at < shard.window_end
                or record.data.get("record_id") != record.record_id
                or record.data.get("customer_id") not in state.directory
                or parse_time(record.data.get("occurred_at")) != record.occurred_at
                for record in records
            ):
                continue
            checkpoint("incremental")
            _stage(run, shard, [record.data for record in records], 0,
                   source.excluded_count, checkpoint)

def _seed_incremental(run, state, checkpoint):
    """Reuse only old fully covered shards; overlap is freshly re-collected."""
    if run.attempt != 1:
        return
    snapshots = NativePublishedSnapshot.objects.filter(
        version__connection_id=run.connection_id,
        version__run__config_version=run.config_version,
        version__run__credential_version=run.credential_version,
        version__window_start__lt=run.window_end,
        version__window_end__gt=run.window_start,
        version__run__status="succeeded",
    ).select_related("version").order_by("-version__published_at")
    overlap = _setting(
        "AGIONE_OPS_NATIVE_OVERLAP_SECONDS", 86400, 3600, 2678400,
    )
    checked = set()
    for shard in run.native_shards.filter(status="pending"):
        previous = next((item for item in snapshots if (
            item.version.coverage.get("pagingComplete")
            and not item.version.coverage.get("partial")
            and isinstance(item.data, dict)
            and set(item.data.get("customers", {})) == set(state.directory)
            and item.version.window_start <= shard.window_start
            and shard.window_end <= item.version.window_end
            and shard.window_end <= run.window_end - timedelta(seconds=overlap)
        )), None)
        if previous is None:
            continue
        if previous.pk not in checked:
            validate_snapshot_data(previous.data, previous.content_digest)
            checked.add(previous.pk)
        checkpoint("incremental")
        rows = [row for row in previous.data["rows"] if (
            shard.window_start <= parse_time(row["occurred_at"])
            < shard.window_end and row["customer_id"] in state.directory
        )]
        _stage(run, shard, rows, 0, 0, checkpoint)


def _read_shard(client, shard, workers, checkpoint):
    """Fetch bounded page batches with one shared thread-safe HTTP/token pool."""
    size = 200
    limit = _setting("AGIONE_OPS_NATIVE_SHARD_MAX_PAGES", 8, 1, 100)
    zone = ZoneInfo("Asia/Shanghai")
    start = shard.window_start.astimezone(zone)
    stop = shard.window_end.astimezone(zone)
    month_end = (start.replace(day=28) + timedelta(days=4)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0,
    )
    clipped = stop == month_end
    upper = stop - timedelta(seconds=1) if clipped else stop
    params = {
        "startTime": start.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "endTime": upper.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "size": size,
    }
    path = "/xapi/observability/call-logs"
    checkpoint("calls")
    first = client.get(path, {**params, "current": 1})
    checkpoint("calls")

    def validate(raw, expected=None):
        if not isinstance(raw, dict):
            raise AgioneOpsError("SOURCE_SHAPE_CHANGED")
        rows, total = raw.get("records"), raw.get("total")
        if (
            not isinstance(rows, list) or len(rows) > size
            or type(total) is not int or total < 0
        ):
            raise AgioneOpsError("SOURCE_SHAPE_CHANGED")
        if expected is not None and expected != total:
            raise AgioneOpsError("SOURCE_CHANGED_DURING_PAGING")
        return rows, total

    rows, total = validate(first)
    pages = max(1, math.ceil(total / size))
    if pages > limit:
        raise AgioneOpsError("SOURCE_PAGE_LIMIT", status_code=409)
    all_rows = list(rows)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for at in range(2, pages + 1, workers):
            checkpoint("calls")
            numbers = range(at, min(at + workers, pages + 1))
            futures = [executor.submit(
                client.get, path, {**params, "current": page},
            ) for page in numbers]
            for future in futures:
                batch, _ = validate(future.result(), total)
                all_rows.extend(batch)
            checkpoint("calls")
    keys = set()
    for row in all_rows:
        if not isinstance(row, dict):
            raise AgioneOpsError("SOURCE_SHAPE_CHANGED")
        if (
            clipped and type(row.get("createTime")) in (int, float)
            and row["createTime"] % 1000
        ):
            raise AgioneOpsError("SOURCE_TIME_PRECISION_CHANGED", status_code=409)
        key = entity(row.get("id", row.get("record_id")))
        if key in keys:
            raise AgioneOpsError("SOURCE_DUPLICATE_PAGE")
        keys.add(key)
    if len(all_rows) != total:
        raise AgioneOpsError("SOURCE_INCOMPLETE_PAGING")
    return all_rows, pages


def _stage(run, shard, rows, pages, excluded, checkpoint):
    """Commit one successful shard and its normalized rows as one unit."""
    from agione_ops.sync import _assert_lease

    checkpoint("staging")
    with transaction.atomic():
        locked = SourceConnection.objects.select_for_update().get(
            pk=run.connection_id,
        )
        current = SyncRun.objects.select_for_update().get(pk=run.pk)
        _assert_lease(locked, current, run._token, run._epoch)
        authorize_native_run(current, locked)
        for row in rows:
            NativeStagedRecord.objects.update_or_create(
                run=run, record_id=row["record_id"],
                defaults={
                    "shard": shard,
                    "occurred_at": parse_time(row["occurred_at"]),
                    "content_digest": digest(row), "data": row,
                },
            )
        NativeSyncShard.objects.filter(pk=shard.pk).update(
            status="succeeded", pages_read=pages, record_count=len(rows),
            excluded_count=excluded, error_code="",
            completed_at=timezone.now(),
        )
        state = NativeSyncState.objects.get(run=run)
        watermark = run.window_start
        for item in run.native_shards.exclude(status="split"):
            if item.status != "succeeded" or item.window_start > watermark:
                break
            watermark = max(watermark, item.window_end)
        state.watermark = watermark
        state.save(update_fields=["watermark"])


def _split(run, shard):
    """Split days into hours, then bisect to one-second safety floor."""
    duration = shard.window_end - shard.window_start
    seconds = int(duration.total_seconds())
    if seconds <= 1:
        raise AgioneOpsError("SOURCE_SLICE_TOO_DENSE", status_code=409)
    step = 3600 if seconds > 3600 else max(1, seconds // 2)
    with transaction.atomic():
        at = shard.window_start
        while at < shard.window_end:
            stop = min(at + timedelta(seconds=step), shard.window_end)
            NativeSyncShard.objects.get_or_create(
                run=run, window_start=at, window_end=stop,
            )
            at = stop
        NativeSyncShard.objects.filter(pk=shard.pk).update(
            status="split", error_code="SOURCE_PAGE_LIMIT",
        )


def _publish(run, connection, state, finance, checkpoint):
    """No DatasetVersion or snapshot is visible until all shards succeed."""
    from agione_ops.sync import (
        _assert_lease, _project, _release, _update_run,
    )

    checkpoint("publishing")
    with transaction.atomic():
        connection = SourceConnection.objects.select_for_update().get(
            pk=connection.pk,
        )
        current = SyncRun.objects.select_for_update().get(pk=run.pk)
        _assert_lease(connection, current, run._token, run._epoch)
        authorize_native_run(current, connection)
        if run.native_shards.exclude(
            status__in=["succeeded", "split"],
        ).exists():
            raise AgioneOpsError("SOURCE_SHARDS_INCOMPLETE")
        rows = list(run.native_staging.order_by(
            "occurred_at", "record_id",
        ).values_list("data", flat=True))
        data = {
            "metadata": {
                "configVersion": run.config_version,
                "credentialVersion": run.credential_version,
                "roleState": state.role_state,
                "collectedAt": timezone.now().isoformat(),
            },
            "rows": rows, "customers": state.directory,
            "models": state.model_names, "finance": finance,
        }
        shards = list(run.native_shards.exclude(status="split"))
        coverage = {
            "sourceKind": "native", "mode": "snapshot",
            "pagingComplete": True, "partial": False,
            "directoryTotal": state.directory_count,
            "confirmedDirectoryCount": state.directory_count,
            "sourceRecordCount": len(rows),
            "pagesRead": sum(x.pages_read for x in shards),
            "quarantinedRecordCount": sum(x.excluded_count for x in shards),
            "shardsComplete": len(shards),
            "watermark": state.watermark.isoformat()
            if state.watermark else None,
            "collectedAt": data["metadata"]["collectedAt"],
            "comparisonHistoryVerified": False,
            "latencyUnitVerified": False,
        }
        version = DatasetVersion.objects.create(
            connection=connection, run=current,
            window_start=run.window_start, window_end=run.window_end,
            timezone=run.timezone, coverage=coverage,
        )
        NativePublishedSnapshot.objects.create(
            version=version, data=data, content_digest=digest(data),
        )
        authorize_native_run(current, connection)
        _update_run(
            current, status="succeeded", phase="succeeded", error_code="",
            processed_count=len(rows), total_count=len(rows),
            finished_at=timezone.now(), heartbeat_at=timezone.now(),
        )
        _release(connection)
        if not getattr(settings, "AGIONE_OPS_FINANCE_REFRESH_ON_SYNC", True):
            try:
                from agione_ops.native_finance_refresh import schedule_finance

                with transaction.atomic():
                    schedule_finance(run.pk)
            except Exception:
                logger.exception("Native finance scheduling failed")
    _project(run.pk)
    return {"status": "succeeded", "dataVersion": str(version.pk)}


def execute_native_sync(run_id, *, client_factory=None):
    """Resume only pending/failed shards under the existing domain lease."""
    from agione_ops.sync import (
        _checkpoint, _claim, _finish_failure, _project,
    )

    claimed = _claim(run_id)
    if claimed is None:
        current = SyncRun.objects.filter(pk=run_id).first()
        _project(run_id)
        return {"status": current.status if current else "not_found"}
    run, connection, lease_token, epoch = claimed
    run._token, run._epoch = lease_token, epoch

    duration = _setting("AGIONE_OPS_NATIVE_MAX_SECONDS", 120, 30, 1800)
    elapsed = max(0, (timezone.now() - run.created_at).total_seconds())
    deadline = time.monotonic() + max(0, duration - elapsed)

    def checkpoint(phase):
        if time.monotonic() >= deadline:
            raise AgioneOpsError("NATIVE_SYNC_DEADLINE", status_code=504)
        _checkpoint(
            run.pk, lease_token, epoch, phase,
            run.native_staging.count(), None,
        )

    client = None
    try:
        workers = _setting("AGIONE_OPS_NATIVE_CONCURRENCY", 3, 1, 8)
        client = (client_factory or NativeClient)(connection)
        checkpoint("identity")
        identity = _identity(client, connection)
        checkpoint("identity")
        state = _prepare(run, connection, client, checkpoint)
        state.role_state = identity.get("role_state", "not_verified")
        if state.role_state not in {"verified", "not_verified"}:
            state.role_state = "not_verified"
        state.save(update_fields=["role_state"])
        _seed_timed_out(run, state, checkpoint)
        _seed_incremental(run, state, checkpoint)
        shard_workers = _setting(
            "AGIONE_OPS_NATIVE_SHARD_CONCURRENCY", 2, 1, 3,
        )

        def fetch_checkpoint(_phase):
            if time.monotonic() >= deadline:
                raise AgioneOpsError("NATIVE_SYNC_DEADLINE", status_code=504)

        def finish_shard(shard, raw_rows, pages):
            rows, excluded = [], 0
            for raw in raw_rows:
                row = normalize_log(raw, shard.window_start, shard.window_end)
                if row is None:
                    continue
                if row["customer_id"] not in state.directory:
                    excluded += 1
                    continue
                rows.append(row)
            _stage(run, shard, rows, pages, excluded, checkpoint)

        while True:
            shards = list(run.native_shards.filter(
                status__in=["pending", "failed", "running"],
            )[:shard_workers])
            if not shards:
                break
            checkpoint("calls")
            for shard in shards:
                NativeSyncShard.objects.filter(pk=shard.pk).update(
                    status="running", attempts=shard.attempts + 1,
                )
            if len(shards) == 1:
                shard = shards[0]
                try:
                    raw_rows, pages = _read_shard(
                        client, shard, workers, checkpoint,
                    )
                    finish_shard(shard, raw_rows, pages)
                except APIException as error:
                    if getattr(error, "code", "") == "SOURCE_PAGE_LIMIT":
                        checkpoint("splitting")
                        _split(run, shard)
                        continue
                    NativeSyncShard.objects.filter(pk=shard.pk).update(
                        status="failed",
                        error_code=getattr(error, "code", "SOURCE_FAILED"),
                    )
                    raise
                continue
            with ThreadPoolExecutor(max_workers=len(shards)) as executor:
                pending = {
                    executor.submit(_read_shard, client, shard, 1,
                                    fetch_checkpoint): shard
                    for shard in shards
                }
                while pending:
                    completed, _ = wait(pending, timeout=2,
                                        return_when=FIRST_COMPLETED)
                    checkpoint("calls")
                    for future in completed:
                        shard = pending.pop(future)
                        try:
                            raw_rows, pages = future.result()
                            finish_shard(shard, raw_rows, pages)
                        except APIException as error:
                            if getattr(error, "code", "") == "SOURCE_PAGE_LIMIT":
                                checkpoint("splitting")
                                _split(run, shard)
                                continue
                            NativeSyncShard.objects.filter(pk=shard.pk).update(
                                status="failed",
                                error_code=getattr(error, "code", "SOURCE_FAILED"),
                            )
                            raise
        checkpoint("identity")
        _identity(client, connection)
        checkpoint("identity")
        state.refresh_from_db()
        checkpoint("finance")
        from agione_ops.native_finance import unavailable_finance
        finance = None
        if finance is None:
            finance = unavailable_finance("NATIVE_FINANCE_DEFERRED")
            finance["mode"] = "snapshot"

        heartbeat_lock = Lock()
        last_heartbeat = [0.0]

        def finance_heartbeat():
            """Renew the lease without a DB write around every HTTP call."""
            now = time.monotonic()
            with heartbeat_lock:
                if now - last_heartbeat[0] < 15:
                    return
                last_heartbeat[0] = now
            checkpoint("finance")

        if getattr(settings, "AGIONE_OPS_FINANCE_REFRESH_ON_SYNC", True):
            from agione_ops.native_queries import collect_native_finance
            try:
                finance = collect_native_finance(
                    connection,
                    get_user_model().objects.get(pk=run.initiated_by_id),
                    client_factory=client_factory,
                    heartbeat=finance_heartbeat,
                )
            except APIException as error:
                if getattr(error, "code", "") in {
                    "ACCESS_REVOKED", "CONNECTION_CHANGED",
                    "CONFIGURATION_CHANGED", "NATIVE_DISABLED",
                }:
                    raise
                finance = unavailable_finance(
                    getattr(error, "code", "NATIVE_FINANCE_NOT_COLLECTED")
                )
                finance["mode"] = "snapshot"
        checkpoint("finance")
        return _publish(run, connection, state, finance, checkpoint)
    except APIException as error:
        if getattr(error, "code", "") in RETRY_CODES:
            error.retryable = True
        return _finish_failure(
            run, connection, lease_token, epoch, error,
        )
    except Exception:
        return _finish_failure(
            run, connection, lease_token, epoch,
            AgioneOpsError("SYNC_FAILED", status_code=500),
        )
    finally:
        if client is not None:
            client.close()
