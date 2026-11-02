"""Synthetic-only synchronization with authorization and lease fencing."""

import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone as datetime_timezone

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone as django_timezone
from rest_framework.exceptions import APIException

from agione_ops.client import (
    MAX_PAGES,
    PAGE_SIZE,
    AgioneOpsError,
    get_client,
    require_synthetic_enabled,
)
from agione_ops.models import (
    CallFact,
    ConnectionGrant,
    DatasetVersion,
    SourceConnection,
    SyncRun,
    VersionCall,
)
from agione_ops.permissions import get_connection_for, require_action

LEASE_SECONDS = 120
MAX_ATTEMPTS = 3
ACTIVE_STATUSES = frozenset({"queued", "running", "retrying"})


def validate_window(window_start, window_end, timezone):
    """Validate explicit, aware, second-precision exclusive windows."""

    if timezone != "Asia/Shanghai":
        raise AgioneOpsError("TIMEZONE_NOT_SUPPORTED")
    if any(
        not isinstance(value, datetime)
        or django_timezone.is_naive(value)
        or value.microsecond
        for value in (window_start, window_end)
    ):
        raise AgioneOpsError("INVALID_WINDOW")
    duration = window_end - window_start
    if not timedelta(0) < duration <= timedelta(days=31):
        raise AgioneOpsError("INVALID_WINDOW")
    if window_end > django_timezone.now():
        raise AgioneOpsError("FUTURE_WINDOW")


def _project(run_id):
    """A projection failure must not change the domain run or publication."""

    try:
        from agione_ops.tracking import project_run

        project_run(str(run_id))
    except Exception:
        return


def _update_run(run, **changes):
    SyncRun.objects.filter(pk=run.pk).update(**changes)
    for key, value in changes.items():
        setattr(run, key, value)


def _update_connection(connection, **changes):
    SourceConnection.objects.filter(pk=connection.pk).update(**changes)
    for key, value in changes.items():
        setattr(connection, key, value)


def _release(connection):
    _update_connection(
        connection, active_run_id=None, lease_token=None, lease_expires_at=None
    )


def _identity_matches(connection, identity):
    return isinstance(identity, dict) and identity == {
        "tenant_id": connection.expected_tenant_id,
        "platform": connection.platform,
        "principal_kind": connection.principal_kind,
    }


def verify_connection(connection, user):
    """Explicitly verify fixture identity without reading any credentials."""

    require_action(user, "manage_connections")
    connection = SourceConnection.objects.get(pk=connection.pk)
    client = get_client(connection)
    identity = client.identity()
    if not connection.expected_tenant_id or not _identity_matches(
        connection, identity
    ):
        raise AgioneOpsError("SOURCE_IDENTITY_MISMATCH", status_code=409)
    with transaction.atomic():
        locked = SourceConnection.objects.select_for_update().get(
            pk=connection.pk
        )
        require_action(user, "manage_connections")
        require_synthetic_enabled(locked)
        if locked.config_version != connection.config_version:
            raise AgioneOpsError("CONFIGURATION_CHANGED", status_code=409)
        locked.verified_tenant_id = identity["tenant_id"]
        locked.verified_at = django_timezone.now()
        locked.save(update_fields=["verified_tenant_id", "verified_at"])
    return {"verified": True, "sourceKind": "synthetic"}


def _authorize_run(run, connection):
    if connection.source_kind == "native":
        from agione_ops.native_sync import authorize_native_run

        return authorize_native_run(run, connection)
    require_synthetic_enabled(connection)
    user = get_user_model().objects.filter(pk=run.initiated_by_id).first()
    if user is None:
        raise AgioneOpsError("ACCESS_REVOKED", status_code=403)
    get_connection_for(user, connection.pk, action="run_sync")
    grant = ConnectionGrant.objects.filter(
        connection=connection, user=user, can_sync=True
    ).first()
    if grant is None or grant.revision != run.grant_revision:
        raise AgioneOpsError("ACCESS_REVOKED", status_code=403)
    if (
        connection.config_version != run.config_version
        or connection.credential_version != run.credential_version
    ):
        raise AgioneOpsError("CONFIGURATION_CHANGED", status_code=409)
    if (
        not connection.verified_at
        or not connection.expected_tenant_id
        or connection.verified_tenant_id != connection.expected_tenant_id
    ):
        raise AgioneOpsError("CONNECTION_NOT_VERIFIED", status_code=409)


def _terminal(run, connection, status, code):
    _update_run(
        run,
        status=status,
        phase=status,
        error_code=code,
        finished_at=django_timezone.now(),
    )
    _release(connection)


def mark_dispatch_failed(run_id):
    """Record broker delivery failure without contacting the broker again."""

    run = SyncRun.objects.filter(pk=run_id).first()
    if run is None:
        return
    with transaction.atomic():
        connection = SourceConnection.objects.select_for_update().get(
            pk=run.connection_id
        )
        run = SyncRun.objects.select_for_update().get(pk=run_id)
        if (
            run.status in {"queued", "retrying"}
            and connection.active_run_id == run.pk
        ):
            _terminal(run, connection, "dispatch_failed", "DISPATCH_FAILED")
    _project(run_id)


def _dispatch(run_id):
    try:
        from agione_ops.tasks import run_sync

        run = SyncRun.objects.get(pk=run_id)
        if (
            getattr(settings, "AGIONE_OPS_LOCAL_EAGER", False) is True
            and run.connection.source_kind != "native"
        ):
            run_sync.apply(args=[str(run_id)], task_id=run.celery_id)
        else:
            run_sync.apply_async(
                args=[str(run_id)], task_id=run.celery_id, retry=False
            )
    except Exception:
        mark_dispatch_failed(run_id)
    _project(run_id)


def _submission_gate(connection):
    """Native configuration checks never instantiate an HTTP client."""
    if connection.source_kind == "native":
        from agione_ops.native_sync import require_native

        return require_native(connection)
    return get_client(connection)


def submit_sync(
    connection,
    user,
    window_start,
    window_end,
    timezone,
    idempotency_key,
):
    """Reserve one connection run and dispatch only after transaction commit."""

    validate_window(window_start, window_end, timezone)
    if not isinstance(idempotency_key, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", idempotency_key
    ):
        raise AgioneOpsError("INVALID_IDEMPOTENCY_KEY")
    connection = get_connection_for(user, connection.pk, action="run_sync")
    _submission_gate(connection)
    utc = datetime_timezone.utc
    payload = {
        "connection": str(connection.pk),
        "start": window_start.astimezone(utc).isoformat(),
        "end": window_end.astimezone(utc).isoformat(),
        "timezone": timezone,
        "kind": "current",
    }
    request_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    with transaction.atomic():
        connection = SourceConnection.objects.select_for_update().get(
            pk=connection.pk
        )
        get_connection_for(user, connection.pk, action="run_sync")
        _submission_gate(connection)
        existing = SyncRun.objects.filter(
            connection=connection,
            initiated_by=user,
            idempotency_key=idempotency_key,
        ).first()
        if existing is not None:
            if existing.request_hash != request_hash:
                raise AgioneOpsError("IDEMPOTENCY_CONFLICT", status_code=409)
            return existing, False
        if connection.source_kind != "native" and (
            not connection.verified_at
            or not connection.expected_tenant_id
            or connection.verified_tenant_id != connection.expected_tenant_id
        ):
            raise AgioneOpsError("CONNECTION_NOT_VERIFIED", status_code=409)
        now = django_timezone.now()
        if connection.active_run_id:
            active = SyncRun.objects.filter(
                pk=connection.active_run_id
            ).first()
            if active and active.status in ACTIVE_STATUSES:
                if connection.lease_expires_at and (
                    connection.lease_expires_at > now
                ):
                    raise AgioneOpsError("CONNECTION_BUSY", status_code=409)
                _terminal(active, connection, "interrupted", "LEASE_EXPIRED")
            else:
                _release(connection)
        grant = ConnectionGrant.objects.get(
            connection=connection, user=user, can_sync=True
        )
        epoch = connection.lease_epoch + 1
        run = SyncRun.objects.create(
            connection=connection,
            initiated_by=user,
            window_start=window_start,
            window_end=window_end,
            timezone=timezone,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            credential_version=connection.credential_version,
            config_version=connection.config_version,
            grant_revision=grant.revision,
            lease_epoch=epoch,
            celery_id=str(uuid.uuid4()),
        )
        _update_connection(
            connection,
            active_run_id=run.pk,
            lease_token=uuid.uuid4(),
            lease_epoch=epoch,
            lease_expires_at=now + timedelta(seconds=LEASE_SECONDS),
        )
        transaction.on_commit(lambda: _dispatch(run.pk))
    run.refresh_from_db()
    return run, True


def _claim(run_id):
    run = SyncRun.objects.filter(pk=run_id).first()
    if run is None:
        return None
    with transaction.atomic():
        connection = SourceConnection.objects.select_for_update().get(
            pk=run.connection_id
        )
        run = SyncRun.objects.select_for_update().get(pk=run_id)
        now = django_timezone.now()
        if connection.active_run_id != run.pk or run.status not in (
            ACTIVE_STATUSES
        ):
            return None
        if (
            run.status == "running"
            and connection.lease_expires_at
            and (connection.lease_expires_at > now)
        ):
            return None
        if (
            run.status == "retrying"
            and connection.lease_expires_at
            and now
            < connection.lease_expires_at - timedelta(seconds=LEASE_SECONDS)
        ):
            return None
        try:
            _authorize_run(run, connection)
        except APIException as error:
            _terminal(
                run,
                connection,
                "revoked",
                getattr(error, "code", "ACCESS_REVOKED"),
            )
            return None
        if run.attempt >= MAX_ATTEMPTS:
            _terminal(run, connection, "failed", "ATTEMPTS_EXHAUSTED")
            return None
        token = uuid.uuid4()
        epoch = connection.lease_epoch + 1
        _update_connection(
            connection,
            lease_token=token,
            lease_epoch=epoch,
            lease_expires_at=now + timedelta(seconds=LEASE_SECONDS),
        )
        _update_run(
            run,
            status="running",
            phase="identity",
            heartbeat_at=now,
            lease_epoch=epoch,
            attempt=run.attempt + 1,
            error_code="",
        )
        return run, connection, token, epoch


def _assert_lease(connection, run, token, epoch):
    if (
        connection.active_run_id != run.pk
        or connection.lease_token != token
        or connection.lease_epoch != epoch
        or run.lease_epoch != epoch
        or run.status != "running"
        or not connection.lease_expires_at
        or connection.lease_expires_at <= django_timezone.now()
    ):
        raise AgioneOpsError("LEASE_LOST", status_code=409)


def _checkpoint(run_id, token, epoch, phase, processed=0, total=None):
    run = SyncRun.objects.get(pk=run_id)
    with transaction.atomic():
        connection = SourceConnection.objects.select_for_update().get(
            pk=run.connection_id
        )
        run = SyncRun.objects.select_for_update().get(pk=run_id)
        _assert_lease(connection, run, token, epoch)
        _authorize_run(run, connection)
        now = django_timezone.now()
        _update_connection(
            connection,
            lease_expires_at=now + timedelta(seconds=LEASE_SECONDS),
        )
        _update_run(
            run,
            phase=phase,
            heartbeat_at=now,
            processed_count=processed,
            total_count=total,
        )
    _project(run_id)


def _directory_ids(rows):
    if not isinstance(rows, list):
        raise AgioneOpsError("SOURCE_SHAPE_CHANGED")
    ids = []
    for row in rows:
        value = row.get("id") if isinstance(row, dict) else None
        if not isinstance(value, str) or not value or len(value) > 160:
            raise AgioneOpsError("SOURCE_RECORD_ID_MISSING")
        ids.append(value)
    if len(ids) != len(set(ids)):
        raise AgioneOpsError("SOURCE_DUPLICATE_DIRECTORY")
    return set(ids)


def _normalize_call(row, start, end):
    if not isinstance(row, dict):
        raise AgioneOpsError("SOURCE_SHAPE_CHANGED")
    normalized = {}
    for key in ("upstream_record_id", "customer_id", "model_id"):
        value = row.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 160:
            raise AgioneOpsError("SOURCE_RECORD_ID_MISSING")
        normalized[key] = value
    at = row.get("occurred_at")
    if not isinstance(at, datetime) or django_timezone.is_naive(at):
        raise AgioneOpsError("SOURCE_TIME_INVALID")
    if not start <= at < end:
        raise AgioneOpsError("SOURCE_WINDOW_MISMATCH")
    normalized["occurred_at"] = at.astimezone(datetime_timezone.utc)
    normalized["status"] = (
        row.get("status")
        if row.get("status") in {"success", "failure"}
        else "unknown"
    )
    for key in ("input_tokens", "output_tokens"):
        value = row.get(key)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            raise AgioneOpsError("SOURCE_TOKEN_INVALID")
        normalized[key] = value
    return normalized


def _collect(run, connection, client, token, epoch):
    if not _identity_matches(connection, client.identity()):
        raise AgioneOpsError("SOURCE_IDENTITY_MISMATCH", status_code=409)
    _checkpoint(run.pk, token, epoch, "directory")
    customers = _directory_ids(client.customers())
    models = _directory_ids(client.models())
    _checkpoint(run.pk, token, epoch, "calls")
    accepted = []
    keys = set()
    total = None
    excluded = 0
    complete = False
    pages_read = 0
    for page in range(1, MAX_PAGES + 1):
        _checkpoint(run.pk, token, epoch, "calls", len(keys), total)
        payload = client.page_calls(run.window_start, run.window_end, page)
        if not isinstance(payload, dict) or payload.get("page") != page:
            raise AgioneOpsError("SOURCE_PAGE_INVALID")
        if not _identity_matches(connection, payload.get("identity")):
            raise AgioneOpsError("SOURCE_IDENTITY_MISMATCH", status_code=409)
        source_total = payload.get("total")
        rows = payload.get("items")
        if (
            isinstance(source_total, bool)
            or not isinstance(source_total, int)
            or source_total < 0
            or source_total > MAX_PAGES * PAGE_SIZE
            or not isinstance(rows, list)
            or len(rows) > PAGE_SIZE
        ):
            raise AgioneOpsError("SOURCE_SHAPE_CHANGED")
        if total is None:
            total = source_total
        elif total != source_total:
            raise AgioneOpsError("SOURCE_CHANGED_DURING_PAGING")
        for raw in rows:
            row = _normalize_call(raw, run.window_start, run.window_end)
            key = row["upstream_record_id"]
            if key in keys:
                raise AgioneOpsError("SOURCE_DUPLICATE_PAGE")
            keys.add(key)
            if row["customer_id"] not in customers:
                excluded += 1
                continue
            if row["model_id"] not in models:
                raise AgioneOpsError("SOURCE_MODEL_UNKNOWN")
            accepted.append(row)
        pages_read = page
        if len(keys) > total:
            raise AgioneOpsError("SOURCE_INCOMPLETE_PAGING")
        next_page = payload.get("next_page")
        if len(keys) == total:
            if next_page is not None:
                raise AgioneOpsError("SOURCE_INCOMPLETE_PAGING")
            complete = True
            break
        if not rows or next_page != page + 1:
            raise AgioneOpsError("SOURCE_INCOMPLETE_PAGING")
    if not complete:
        raise AgioneOpsError("SOURCE_PAGE_LIMIT")
    if not _identity_matches(connection, client.identity()):
        raise AgioneOpsError("SOURCE_IDENTITY_MISMATCH", status_code=409)
    _checkpoint(run.pk, token, epoch, "publishing", len(keys), total)
    coverage = {
        "sourceKind": "synthetic",
        "pagingComplete": True,
        "sourceTotal": total,
        "includedRequests": len(accepted),
        "excludedUnknownCustomers": excluded,
        "authorizedCustomers": len(customers),
        "knownModels": len(models),
        "pagesRead": pages_read,
        "collectedAt": django_timezone.now().isoformat(),
    }
    return accepted, coverage


def _publish(run, connection, token, epoch, rows, coverage):
    with transaction.atomic():
        connection = SourceConnection.objects.select_for_update().get(
            pk=connection.pk
        )
        run = SyncRun.objects.select_for_update().get(pk=run.pk)
        _assert_lease(connection, run, token, epoch)
        _authorize_run(run, connection)
        version = DatasetVersion.objects.create(
            connection=connection,
            run=run,
            window_start=run.window_start,
            window_end=run.window_end,
            timezone=run.timezone,
            coverage=coverage,
        )
        for row in rows:
            canonical = {
                **row,
                "occurred_at": row["occurred_at"].isoformat(),
            }
            digest = hashlib.sha256(
                json.dumps(canonical, sort_keys=True).encode("utf-8")
            ).hexdigest()
            fact, _created = CallFact.objects.get_or_create(
                connection=connection,
                upstream_record_id=row["upstream_record_id"],
                content_hash=digest,
                defaults={
                    key: value
                    for key, value in row.items()
                    if key != "upstream_record_id"
                },
            )
            VersionCall.objects.create(
                version=version,
                fact=fact,
                upstream_record_id=row["upstream_record_id"],
            )
        connection.refresh_from_db()
        _assert_lease(connection, run, token, epoch)
        _authorize_run(run, connection)
        _update_run(
            run,
            status="succeeded",
            phase="succeeded",
            finished_at=django_timezone.now(),
            heartbeat_at=django_timezone.now(),
            error_code="",
        )
        _release(connection)
    _project(run.pk)
    return {"status": "succeeded", "dataVersion": str(version.pk)}


def _finish_failure(run, connection, token, epoch, error):
    code = getattr(error, "code", "ACCESS_REVOKED")
    allowed_retry_codes = {
        "SOURCE_TIMEOUT", "SOURCE_RATE_LIMITED", "SOURCE_UNAVAILABLE",
    }
    if connection.source_kind == "native":
        from agione_ops.native_sync import RETRY_CODES

        allowed_retry_codes = RETRY_CODES
    retryable = getattr(error, "retryable", False) and code in (
        allowed_retry_codes
    )
    with transaction.atomic():
        connection = SourceConnection.objects.select_for_update().get(
            pk=connection.pk
        )
        run = SyncRun.objects.select_for_update().get(pk=run.pk)
        if (
            connection.active_run_id != run.pk
            or connection.lease_token != token
            or connection.lease_epoch != epoch
            or run.lease_epoch != epoch
        ):
            return {"status": "skipped", "errorCode": "LEASE_LOST"}
        if retryable and run.attempt < MAX_ATTEMPTS:
            delay = min(2**run.attempt, 30)
            _update_run(
                run, status="retrying", phase="retrying", error_code=code
            )
            _update_connection(
                connection,
                lease_token=None,
                lease_expires_at=django_timezone.now()
                + timedelta(seconds=LEASE_SECONDS + delay),
            )
            result = {"status": "retrying", "retryAfter": delay}
        else:
            revoked = code in {
                "NATIVE_DISABLED",
                "ACCESS_REVOKED",
                "CONFIGURATION_CHANGED",
                "CONNECTION_NOT_VERIFIED",
                "SYNTHETIC_DISABLED",
                "REAL_SOURCE_FORBIDDEN",
                "REAL_CREDENTIALS_FORBIDDEN",
            }
            status = "revoked" if revoked else "failed"
            _terminal(run, connection, status, code)
            result = {"status": status, "errorCode": code}
    _project(run.pk)
    return result


def execute_sync(run_id):
    """Consume a UUID-only task without transport or global recovery sweeps."""

    try:
        run_id = uuid.UUID(str(run_id))
    except (ValueError, TypeError, AttributeError):
        return {"status": "skipped", "errorCode": "RUN_NOT_FOUND"}
    source_kind = SyncRun.objects.filter(pk=run_id).values_list(
        "connection__source_kind", flat=True,
    ).first()
    if source_kind == "native":
        from agione_ops.native_sync import execute_native_sync

        return execute_native_sync(run_id)
    claimed = _claim(run_id)
    if claimed is None:
        run = SyncRun.objects.filter(pk=run_id).first()
        _project(run_id)
        return {"status": run.status if run else "not_found"}
    run, connection, token, epoch = claimed
    try:
        client = get_client(connection)
        rows, coverage = _collect(run, connection, client, token, epoch)
        return _publish(run, connection, token, epoch, rows, coverage)
    except APIException as error:
        return _finish_failure(run, connection, token, epoch, error)
    except Exception:
        return _finish_failure(
            run,
            connection,
            token,
            epoch,
            AgioneOpsError("SYNC_FAILED", status_code=500),
        )
