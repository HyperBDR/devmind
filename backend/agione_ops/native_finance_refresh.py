"""Independent, authorized finance refresh for native snapshots."""

import logging
import time
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import APIException

from agione_ops.models import SourceConnection, SyncRun
from agione_ops.native_account_scope import FINANCE_SCOPE_VERSION
from agione_ops.native_finance import unavailable_finance
from agione_ops.native_sync_models import (
    NativeFinanceProjection, NativeFinanceRun, NativePublishedSnapshot,
)
from agione_ops.permissions import connections_for, get_connection_for

logger = logging.getLogger(__name__)


def recover_expired_finance():
    """Record finance jobs abandoned beyond the worker's hard time limit."""
    cutoff = timezone.now() - timedelta(minutes=22)
    ids = NativeFinanceProjection.objects.filter(
        status__in=["queued", "running", "retrying"], updated_at__lt=cutoff,
    ).values_list("pk", flat=True)[:200]
    for pk in list(ids):
        with transaction.atomic():
            row = NativeFinanceProjection.objects.select_for_update().filter(
                pk=pk, status__in=["queued", "running", "retrying"],
                updated_at__lt=cutoff,
            ).first()
            if row is None:
                continue
            row.status = "failed"
            row.error_code = "FINANCE_REFRESH_TIMEOUT"
            row.save(update_fields=["status", "error_code", "updated_at"])
            NativeFinanceRun.objects.filter(
                connection_id=row.connection_id, user_id=row.user_id,
                run_id=row.run_id, status__in=["queued", "running", "retrying"],
            ).update(status="failed", error_code="FINANCE_REFRESH_TIMEOUT",
                     finished_at=timezone.now())
            from agione_ops.models import NotificationRules
            from agione_ops.notification_delivery import notify_collection_failure

            rules = NotificationRules.objects.select_related("connection").filter(
                connection_id=row.connection_id, user_id=row.user_id,
            ).first()
            notify_collection_failure(rules, "finance", "FINANCE_REFRESH_TIMEOUT")


def _operator(connection, user):
    candidates = list(connections_for(user, "view_business").filter(
        platform=connection.platform, principal_kind="operator",
        source_kind="native", enabled=True, endpoint=connection.endpoint,
    )[:2])
    if connection.principal_kind == "operator":
        return get_connection_for(user, connection.pk, "view_business")
    return candidates[0] if len(candidates) == 1 else None


def _valid(projection, connection, user):
    if (
        projection.config_version != connection.config_version
        or projection.credential_version != connection.credential_version
    ):
        return False
    operator = _operator(connection, user)
    return bool(
        operator and operator.pk == projection.operator_id
        and operator.config_version == projection.operator_config_version
        and operator.credential_version ==
        projection.operator_credential_version
    )


def finance_for(connection, user):
    """Return only the requesting user's current authorized finance result."""
    from agione_ops.native_sync import digest
    from agione_ops.tenant_directory import classification_version

    row = NativeFinanceProjection.objects.filter(
        connection=connection, user=user,
    ).select_related("operator").first()
    if not row or not _valid(row, connection, user):
        return {**unavailable_finance("NATIVE_FINANCE_NOT_COLLECTED"),
                "mode": "snapshot"}, None
    if row.data and digest(row.data) != row.content_digest:
        return {**unavailable_finance("NATIVE_FINANCE_INVALID"),
                "mode": "snapshot"}, None
    result = dict(
        row.data or unavailable_finance("NATIVE_FINANCE_NOT_COLLECTED")
    )
    current = classification_version(connection, user)
    recorded = result.get("classificationVersion")
    if recorded != current and (recorded or current != digest([{}, None])):
        result = unavailable_finance("CLASSIFICATION_CHANGED")
    if (result.get("available")
            and result.get("coverageBasis") != FINANCE_SCOPE_VERSION):
        result = unavailable_finance("NATIVE_FINANCE_NOT_COLLECTED")
    result["mode"] = "snapshot"
    expired = row.status in {"queued", "running", "retrying"} and row.updated_at <= (
        timezone.now() - timedelta(minutes=20)
    )
    result["refreshState"] = "failed" if expired else row.status
    result["refreshError"] = "FINANCE_REFRESH_TIMEOUT" if expired else (
        row.error_code or None
    )
    version = f"{row.pk}:{row.updated_at.isoformat()}:{result['refreshState']}"
    return result, version


def schedule_finance(run_id):
    """Schedule at most one active collection per connection and user."""
    from agione_ops.tasks import refresh_native_finance

    run = SyncRun.objects.select_related("connection", "initiated_by").get(
        pk=run_id,
    )
    connection, user = run.connection, run.initiated_by
    try:
        operator = _operator(connection, user)
        if not operator:
            return
        with transaction.atomic():
            SourceConnection.objects.select_for_update().get(pk=connection.pk)
            row = NativeFinanceProjection.objects.select_for_update().filter(
                connection=connection, user=user,
            ).first()
            if row and _valid(row, connection, user):
                if row.status in {"queued", "running", "retrying"} and row.updated_at > (
                    timezone.now() - timedelta(minutes=20)
                ):
                    return
                previous = row.data
                previous_digest = row.content_digest
            else:
                previous = None
                previous_digest = ""
            values = {
                "operator": operator, "run": run, "status": "queued",
                "error_code": "", "data": previous,
                "content_digest": previous_digest,
                "config_version": connection.config_version,
                "credential_version": connection.credential_version,
                "operator_config_version": operator.config_version,
                "operator_credential_version": operator.credential_version,
            }
            row, _ = NativeFinanceProjection.objects.update_or_create(
                connection=connection, user=user, defaults=values,
            )
            row_id = row.pk
            generation = uuid.uuid4().hex
            NativeFinanceRun.objects.filter(
                connection=connection, user=user,
                status__in=["queued", "running", "retrying"],
            ).update(status="interrupted", error_code="FINANCE_REFRESH_TIMEOUT",
                     finished_at=timezone.now())
            NativeFinanceRun.objects.create(
                connection=connection, user=user, run=run,
                generation=generation,
            )

            def dispatch():
                try:
                    refresh_native_finance.delay(row_id, str(run.pk), generation)
                except Exception:
                    NativeFinanceProjection.objects.filter(
                        pk=row_id, run_id=run.pk, status="queued",
                    ).update(status="failed", error_code="DISPATCH_FAILED",
                             updated_at=timezone.now())
                    NativeFinanceRun.objects.filter(generation=generation).update(
                        status="failed", error_code="DISPATCH_FAILED",
                        finished_at=timezone.now(),
                    )
                    logger.exception("Native finance dispatch failed")

            transaction.on_commit(dispatch)
    except APIException:
        logger.warning("Native finance refresh is not authorized")


def execute_finance(row_id, run_id, *, can_retry=False, checkpoint_scope=None):
    """Fence stale tasks and validate permissions around source IO."""
    from agione_ops.native_queries import collect_native_finance
    from agione_ops.native_sync import (
        authorize_native_run, digest, validate_snapshot_data,
    )

    started = time.perf_counter()

    def owns_generation():
        return not checkpoint_scope or NativeFinanceRun.objects.filter(
            generation=checkpoint_scope, run_id=run_id, status="running",
        ).exists()

    with transaction.atomic():
        row = NativeFinanceProjection.objects.select_for_update().filter(
            pk=row_id, run_id=run_id, status__in=["queued", "retrying"],
        ).select_related("connection", "operator", "run", "user").first()
        if row is None:
            return
        if checkpoint_scope and not NativeFinanceRun.objects.filter(
            generation=checkpoint_scope, run_id=run_id,
            status__in=["queued", "retrying"],
        ).exists():
            if NativeFinanceRun.objects.filter(connection=row.connection, user=row.user).exists():
                return
            NativeFinanceRun.objects.create(
                connection=row.connection, user=row.user, run_id=run_id,
                generation=checkpoint_scope,
            )
        queue_ms = max(0, round(
            (timezone.now() - row.updated_at).total_seconds() * 1000
        ))
        previous_data = row.data
        previous_digest = row.content_digest
        row.status = "running"
        row.save(update_fields=["status", "updated_at"])
        if checkpoint_scope:
            history = NativeFinanceRun.objects.filter(
                generation=checkpoint_scope, run_id=run_id,
                status__in=["queued", "retrying"],
            )
            history.filter(started_at__isnull=True).update(started_at=timezone.now())
            history.update(status="running", attempt=F("attempt") + 1)
    try:
        user = get_user_model().objects.get(pk=row.user_id, is_active=True)
        connection = get_connection_for(
            user, row.connection_id, "view_business",
        )
        authorize_native_run(row.run, connection)
        if not _valid(row, connection, user):
            raise ValueError("FINANCE_AUTHORITY_CHANGED")

        def publish_balance(data):
            from agione_ops.tenant_directory import classification_version

            snapshot = NativePublishedSnapshot.objects.get(version__run=row.run)
            sample = {**snapshot.data, "finance": data}
            validate_snapshot_data(sample, digest(sample))
            with transaction.atomic():
                ids = sorted({row.connection_id, row.operator_id}, key=str)
                list(SourceConnection.objects.select_for_update().filter(
                    pk__in=ids,
                ).order_by("pk"))
                current = NativeFinanceProjection.objects.select_for_update().get(
                    pk=row_id,
                )
                if (str(current.run_id) != str(run_id)
                        or current.status != "running" or not owns_generation()):
                    return
                active = get_connection_for(user, row.connection_id, "view_business")
                authorize_native_run(row.run, active)
                if (not _valid(current, active, user)
                        or classification_version(active, user) !=
                        data.get("classificationVersion")):
                    raise ValueError("FINANCE_AUTHORITY_CHANGED")
                current.data = data
                current.content_digest = digest(data)
                current.save(update_fields=["data", "content_digest", "updated_at"])

        data = collect_native_finance(
            connection, user,
            reuse_cache=row.run.idempotency_key.startswith("agione-auto-"),
            on_balance=publish_balance,
            checkpoint_scope=checkpoint_scope,
        )
        snapshot = NativePublishedSnapshot.objects.get(version__run=row.run)
        sample = {**snapshot.data, "finance": data}
        validate_snapshot_data(sample, digest(sample))
        with transaction.atomic():
            ids = sorted({row.connection_id, row.operator_id}, key=str)
            list(SourceConnection.objects.select_for_update().filter(
                pk__in=ids,
            ).order_by("pk"))
            current = NativeFinanceProjection.objects.select_for_update().get(
                pk=row_id,
            )
            if (
                str(current.run_id) != str(run_id)
                or current.status != "running"
                or not owns_generation()
            ):
                return
            connection = get_connection_for(
                user, row.connection_id, "view_business",
            )
            authorize_native_run(row.run, connection)
            if not _valid(current, connection, user):
                raise ValueError("FINANCE_AUTHORITY_CHANGED")
            from agione_ops.tenant_directory import classification_version

            current_version = classification_version(connection, user)
            data_version = data.get("classificationVersion")
            if data_version != current_version and (
                data_version or current_version != digest([{}, None])
            ):
                raise ValueError("CLASSIFICATION_CHANGED")
            current.data = data
            current.status = "ready"
            current.error_code = ""
            current.content_digest = digest(data)
            current.save(update_fields=[
                "data", "content_digest", "status", "error_code", "updated_at",
            ])
            if checkpoint_scope:
                NativeFinanceRun.objects.filter(
                    generation=checkpoint_scope, status="running",
                ).update(status="succeeded", error_code="", finished_at=timezone.now())
    except Exception as error:
        logger.exception("Native finance refresh failed")
        code = getattr(error, "code", "")
        transient = code in {
            "SOURCE_TIMEOUT", "SOURCE_UNREACHABLE", "SOURCE_UNAVAILABLE",
            "SOURCE_RATE_LIMITED",
        }
        retrying = transient and can_retry
        updates = {"status": "retrying" if retrying else "failed",
                   "error_code": code if transient else "FINANCE_REFRESH_FAILED",
                   "updated_at": timezone.now()}
        if previous_data and previous_digest:
            updates.update(data=previous_data, content_digest=previous_digest)
        with transaction.atomic():
            current = NativeFinanceProjection.objects.select_for_update().filter(
                pk=row_id, run_id=run_id, status="running",
            ).first()
            changed = 0
            if current and owns_generation():
                changed = NativeFinanceProjection.objects.filter(pk=row_id).update(
                    **updates,
                )
        if checkpoint_scope and changed:
            NativeFinanceRun.objects.filter(
                generation=checkpoint_scope, status="running",
            ).update(status="retrying" if retrying else "failed",
                     error_code=updates["error_code"],
                     finished_at=None if retrying else timezone.now())
        if changed and not retrying:
            try:
                from agione_ops.models import NotificationRules
                from agione_ops.notification_delivery import notify_collection_failure

                rules = NotificationRules.objects.select_related("connection").filter(
                    connection_id=row.connection_id, user_id=row.user_id,
                ).first()
                notify_collection_failure(rules, "finance", updates["error_code"])
            except Exception:
                logger.exception("Finance failure notification could not be queued")
        if retrying and changed:
            return code
    finally:
        logger.info(
            "AGIOne finance timing run=%s queue_ms=%s total_ms=%s",
            run_id, queue_ms, round((time.perf_counter() - started) * 1000),
        )
