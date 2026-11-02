"""Background account classification for authorized native snapshots."""

import logging
import re
from django.db import transaction
from rest_framework.exceptions import APIException

from agione_ops.models import SourceConnection, SyncRun
from agione_ops.native_account_scope import (
    classify_rows, internal_tenant_types, merge_account_types,
)
from agione_ops.native_finance_refresh import _operator, _valid
from agione_ops.native_sync_models import NativeAccountScope, NativePublishedSnapshot

logger = logging.getLogger(__name__)


def scope_for(connection, user):
    """Return sanitized types only while the operator grant remains valid."""
    from agione_ops.native_sync import digest

    scope = NativeAccountScope.objects.filter(
        connection=connection, user=user,
    ).select_related("operator").first()
    if not scope:
        return {}, None
    try:
        if not _valid(scope, connection, user):
            return {}, None
    except APIException:
        return {}, None
    if not isinstance(scope.data, dict) or digest(scope.data) != scope.content_digest:
        return {}, None
    if any(not re.fullmatch(r"(?:[0-9]{1,40}|tenant):[0-9]{1,40}", str(key))
           or value not in {"internal", "external", "unknown"}
           for key, value in scope.data.items()):
        return {}, None
    return scope.data, scope.content_digest + ":" + digest(scope.names)


def schedule_account_scope(run_id):
    """Start one refresh while preserving the last authorized result."""
    from agione_ops.tasks import refresh_native_accounts

    run = SyncRun.objects.select_related("connection", "initiated_by").get(pk=run_id)
    connection, user = run.connection, run.initiated_by
    operator = _operator(connection, user)
    if not operator:
        return
    with transaction.atomic():
        SourceConnection.objects.select_for_update().get(pk=connection.pk)
        current = NativeAccountScope.objects.select_for_update().filter(
            connection=connection, user=user,
        ).first()
        old_data, old_digest = scope_for(connection, user) if current else ({}, None)
        old_digest = current.content_digest if old_digest else ""
        scope, _ = NativeAccountScope.objects.update_or_create(
            connection=connection, user=user,
            defaults={"operator": operator, "run": run, "status": "queued",
                      "error_code": "",
                      "data": old_data, "content_digest": old_digest,
                      "config_version": connection.config_version,
                      "credential_version": connection.credential_version,
                      "operator_config_version": operator.config_version,
                      "operator_credential_version": operator.credential_version},
        )
        def dispatch():
            try:
                refresh_native_accounts.delay(scope.pk, str(run.pk))
            except Exception:
                NativeAccountScope.objects.filter(
                    pk=scope.pk, run_id=run.pk, status="queued",
                ).update(
                    status="failed",
                    error_code="ACCOUNT_REFRESH_DISPATCH_FAILED",
                )
                logger.exception("Native account classification dispatch failed")

        transaction.on_commit(dispatch)


def schedule_cached_scope_analysis(run_id):
    """Reuse a valid tenant directory while analyzing a newer call snapshot."""
    from agione_ops.tasks import analyze_native_snapshot

    run = SyncRun.objects.select_related("connection", "initiated_by").get(
        pk=run_id,
    )
    connection, user = run.connection, run.initiated_by
    with transaction.atomic():
        scope = NativeAccountScope.objects.select_for_update().filter(
            connection=connection,
            user=user,
            status="ready",
        ).first()
        if not scope or not scope_for(connection, user)[1]:
            schedule_account_scope(run_id)
            return
        scope.run = run
        scope.save(update_fields=["run"])
        transaction.on_commit(
            lambda: analyze_native_snapshot.delay(scope.pk, str(run.pk))
        )


def execute_account_scope(scope_id, run_id):
    """Collect only account types; raw email and identity never enter storage."""
    from agione_ops.client import AgioneOpsError
    from agione_ops.native_analytics import business_text
    from agione_ops.native_client import NativeClient
    from agione_ops.native_queries import LiveSource
    from agione_ops.native_sync import authorize_native_run, digest
    from agione_ops.permissions import get_connection_for

    scope = NativeAccountScope.objects.select_related(
        "connection", "operator", "user", "run",
    ).filter(pk=scope_id, run_id=run_id, status="queued").first()
    if not scope:
        return
    try:
        connection = get_connection_for(scope.user, scope.connection_id, "view_business")
        authorize_native_run(scope.run, connection)
        if not _valid(scope, connection, scope.user):
            return
        snapshot = NativePublishedSnapshot.objects.get(version__run=scope.run)
        source = LiveSource(scope.operator, scope.user, NativeClient)
        try:
            names = {}

            def lookup(user_id):
                if not re.fullmatch(r"[0-9]{1,40}", user_id):
                    return None
                try:
                    identity = source.get("/admin/user/details/" + user_id)
                    if isinstance(identity, dict) and str(identity.get("userId")) == user_id:
                        tenant = str(identity.get("tenantId") or "")
                        name = business_text(identity.get("username")) or business_text(identity.get("nickname")) or business_text(identity.get("name"))
                        if name and re.fullmatch(r"[0-9]{1,40}", tenant):
                            names[f"{tenant}:{user_id}"] = name
                    return identity
                except AgioneOpsError as error:
                    if error.code in {"ACCESS_REVOKED", "CONNECTION_CHANGED", "NATIVE_DISABLED"}:
                        raise
                    return None

            directory = source.pages(
                "/coperation/tenant/op-customers", {"identityCode": "EU"},
                directory=True, key="tenantId",
            )
            tenant_types = internal_tenant_types(directory)
            types = classify_rows(snapshot.data.get("rows", []), lookup)
        finally:
            source.close()
        with transaction.atomic():
            current = NativeAccountScope.objects.select_for_update().get(pk=scope_id)
            connection = get_connection_for(scope.user, scope.connection_id, "view_business")
            authorize_native_run(scope.run, connection)
            if str(current.run_id) != str(run_id) or not _valid(current, connection, scope.user):
                return
            previous = {key: value for key, value in current.data.items()
                        if not key.startswith("tenant:")}
            merged = {**merge_account_types(previous, types), **tenant_types}
            current.data = merged
            current.names = {**current.names, **names}
            current.content_digest = digest(merged)
            current.status = "ready"
            current.error_code = ""
            current.save(update_fields=["data", "names", "content_digest", "status", "error_code", "updated_at"])
        from agione_ops.tenant_directory import cache_directory

        cache_directory(scope.operator, directory)
        from agione_ops.notification_rules import analyze_completed_snapshot

        try:
            analyze_completed_snapshot(scope_id, run_id)
        except Exception:
            from agione_ops.tasks import _mark_auto_inspection_failed

            _mark_auto_inspection_failed(run_id)
            logger.exception("AGIOne notification analysis failed")
    except Exception:
        logger.exception("AGIOne account classification failed")
        NativeAccountScope.objects.filter(pk=scope_id, run_id=run_id).update(
            status="failed",
            error_code="ACCOUNT_REFRESH_FAILED",
        )
