"""Thin authenticated APIs for the local synthetic AGIOne workflow."""

import logging
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from djangorestframework_camel_case.parser import CamelCaseJSONParser
from djangorestframework_camel_case.util import camelize
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from agione_ops.client import AgioneOpsError
from agione_ops.encryption import (
    CredentialConfigurationError,
    CredentialDecryptionError,
)
from agione_ops.models import (
    ConnectionGrant, NotificationDelivery, SourceConnection, SyncRun,
)
from agione_ops.permissions import (
    authorize_run,
    connections_for,
    get_connection_for,
    has_action,
    require_action,
)
from agione_ops.serializers import (
    ConnectionSerializer,
    DashboardQuerySerializer,
    EmptySerializer,
    GrantSerializer,
    SelfServiceConnectionSerializer,
    SyncRequestSerializer,
)
from core.settings.renders import CustomJSONRenderer

logger = logging.getLogger(__name__)


def run_payload(run):
    """Expose progress and safe codes, not credentials or request payloads."""

    version = getattr(run, "published_version", None)
    return {
        "run_id": str(run.pk),
        "connection_id": str(run.connection_id),
        "status": run.status,
        "phase": run.phase,
        "processed_count": run.processed_count,
        "total_count": run.total_count,
        "heartbeat_at": run.heartbeat_at,
        "attempt": run.attempt,
        "error_code": run.error_code or None,
        "data_version": str(version.pk) if version else None,
        "status_url": reverse(
            "agione-ops-sync-run-detail",
            kwargs={"connection_id": run.connection_id, "run_id": run.pk},
        ),
    }


class LocalAPIView(APIView):
    """Reuse session/JWT authentication and the project's response envelope."""

    permission_classes = [IsAuthenticated]
    parser_classes = [CamelCaseJSONParser]
    renderer_classes = [CustomJSONRenderer]

    def dispatch(self, request, *args, **kwargs):
        from agione_ops import observability

        measured = request.path.rstrip("/").endswith((
            "snapshot/query", "live/query", "dashboard/query",
        ))
        if not measured:
            return super().dispatch(request, *args, **kwargs)
        observation, token = observability.begin(
            kwargs.get("connection_id"), request.headers.get("X-Request-ID")
        )
        response = None
        try:
            response = super().dispatch(request, *args, **kwargs)
            response["X-Request-ID"] = observation.request_id
            return response
        except BaseException as exc:
            observability.error(exc)
            raise
        finally:
            observation.emit(response.status_code if response else 500)
            observability.end(token)

    def handle_exception(self, exc):
        from agione_ops import observability

        observability.error(exc)
        if isinstance(
            exc, (CredentialConfigurationError, CredentialDecryptionError)
        ):
            return Response(
                {"error_code": "credential_unavailable"},
                status=503,
            )
        if isinstance(exc, DjangoValidationError):
            return Response(
                {"error_code": "invalid_configuration"}, status=400
            )
        if isinstance(exc, APIException):
            response = super().handle_exception(exc)
            error_code = getattr(exc, "code", None)
            if isinstance(error_code, str):
                response.data = {
                    "error_code": error_code,
                    "detail": exc.detail,
                }
            return response
        from django.core.exceptions import PermissionDenied
        from django.http import Http404

        if isinstance(exc, (PermissionDenied, Http404)):
            return super().handle_exception(exc)
        observation = observability.current()
        logger.error(
            "AGIOne safe failure request_id=%s stage=%s code=%s",
            observation.request_id if observation else "untracked",
            observation.failed_stage if observation else "dispatch",
            observability.safe_code(getattr(exc, "code", None)),
        )
        return Response({"error_code": "internal_error"}, status=500)

    def finalize_response(self, request, response, *args, **kwargs):
        if isinstance(response, Response):
            success = 200 <= response.status_code < 300
            response.data = {
                "code": 0 if success else response.status_code,
                "message": "success" if success else "failed",
                "data": camelize(response.data),
            }
        return super().finalize_response(request, response, *args, **kwargs)


class NotificationRulesAPIView(LocalAPIView):
    """Read and validate notification settings for the authorized viewer."""

    def get(self, request, connection_id):
        from agentcore_notifier.adapters.django.models import (
            NotificationChannel,
        )
        from agione_ops.models import NotificationRules
        from agione_ops.notification_rules import NotificationRulesSerializer
        from agione_ops.native_sync_models import (
            NativeAccountScope,
            NativeFinanceProjection,
            NativeFinanceRun,
        )

        connection = get_connection_for(request.user, connection_id)
        row = NotificationRules.objects.filter(
            connection=connection, user=request.user,
        ).first()
        serializer = NotificationRulesSerializer(
            data=row.config if row else {},
        )
        serializer.is_valid(raise_exception=True)
        channels = NotificationChannel.objects.filter(
            is_active=True, channel_type=NotificationChannel.TYPE_WEBHOOK,
        ).filter(Q(user__isnull=True) | Q(user=request.user))
        latest_delivery = row.deliveries.first() if row else None
        from zoneinfo import ZoneInfo

        today = timezone.now().astimezone(ZoneInfo("Asia/Shanghai")).date()
        report_delivery = row.deliveries.filter(
            payload__trigger="scheduled", payload__scheduled_date=str(today),
            kind="alert",
        ).first() if row else None
        report_status = "not_run"
        if row and row.config.get("enabled"):
            report_status = (row.last_report_status
                             if row.last_report_date == today else "not_run")
        if report_delivery:
            report_status = report_delivery.status
        finance = NativeFinanceProjection.objects.filter(
            connection=connection,
            user=request.user,
        ).first()
        tenants = NativeAccountScope.objects.filter(
            connection=connection,
            user=request.user,
        ).first()
        recent_runs = [
            {**run_payload(run), "created_at": run.created_at,
             "finished_at": run.finished_at,
             "trigger": ("automatic" if run.idempotency_key.startswith("agione-auto-")
                         else "scheduled" if run.idempotency_key.startswith("agione-scheduled-")
                         else "manual")}
            for run in SyncRun.objects.filter(
                connection=connection, initiated_by=request.user,
            ).order_by("-created_at")[:5]
        ]
        recent_runs.extend({
            "run_id": f"finance-{item.pk}", "trigger": "finance",
            "status": item.status, "phase": "finance",
            "created_at": item.started_at or item.created_at,
            "finished_at": item.finished_at, "heartbeat_at": None,
            "attempt": item.attempt, "error_code": item.error_code,
        } for item in NativeFinanceRun.objects.filter(
            connection=connection, user=request.user,
        ).order_by("-created_at")[:5])
        recent_runs.sort(key=lambda item: item["created_at"], reverse=True)
        return Response({
            **serializer.validated_data,
            "recent_runs": recent_runs[:5],
            "configured": row is not None,
            "inspection_gap": row.inspection_gap if row else None,
            "inspection_gap_history": list(
                row.gap_acknowledgements.values(
                    "gap_start", "gap_end", "acknowledged_at",
                    "skipped_until", "acknowledged_by_id",
                )[:20]
            ) if row else [],
            "last_analysis": row.last_analysis if row else None,
            "delivery_status": {
                "status": latest_delivery.status,
                "kind": latest_delivery.kind,
                "attempts": latest_delivery.attempts,
                "created_at": latest_delivery.created_at,
                "sent_at": latest_delivery.sent_at,
            } if latest_delivery else None,
            "daily_report": {
                "date": today.isoformat(), "status": report_status,
                "attempts": row.last_report_attempts if row and row.last_report_date == today else 0,
                "updated_at": (
                    report_delivery.sent_at or report_delivery.created_at
                    if report_delivery else
                    row.last_report_updated_at if row and row.last_report_date == today
                    else None
                ),
            },
            "refresh_status": {
                "calls": {
                    "status": row.last_auto_status if row else "idle",
                    "last_started_at": (
                        row.last_auto_started_at if row else None
                    ),
                    "last_success_at": (
                        row.last_auto_success_at if row else None
                    ),
                    "next_at": row.next_auto_refresh_at if row else None,
                    "error_code": (
                        row.last_auto_error_code if row else ""
                    ),
                },
                "finance": {
                    "status": finance.status if finance else "not_run",
                    "updated_at": finance.updated_at if finance else None,
                    "error_code": finance.error_code if finance else "",
                },
                "tenants": {
                    "status": tenants.status if tenants else "not_run",
                    "updated_at": tenants.updated_at if tenants else None,
                    "error_code": tenants.error_code if tenants else "",
                },
                "inspection": {
                    "status": (
                        (row.last_analysis or {}).get("status", "not_run")
                        if row else "not_run"
                    ),
                    "updated_at": row.last_inspection_at if row else None,
                },
            },
            "channels": [{"id": str(item.uuid), "name": item.name}
                         for item in channels.order_by("name")],
        })

    def put(self, request, connection_id):
        from agentcore_notifier.adapters.django.models import (
            NotificationChannel,
        )
        from agione_ops.models import NotificationRules
        from agione_ops.notification_rules import NotificationRulesSerializer
        from django.utils import timezone

        connection = get_connection_for(
            request.user, connection_id, "run_sync",
        )
        serializer = NotificationRulesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = serializer.validated_data
        if config.get("channel_id"):
            channel = NotificationChannel.objects.filter(
                uuid=config["channel_id"], is_active=True,
                channel_type=NotificationChannel.TYPE_WEBHOOK,
            ).filter(Q(user__isnull=True) | Q(user=request.user)).first()
            if not channel:
                raise ValidationError("通知渠道不可用或未授权。")
        row = NotificationRules.objects.filter(
            connection=connection,
            user=request.user,
        ).first()
        defaults = {"config": config}
        if row and (
            row.config.get("schedule_time", "01:20")
            != config["schedule_time"]
            or not row.config.get("enabled") and config.get("enabled")
        ):
            defaults["last_scheduled_at"] = None
        auto_changed = (
            row is None
            or row.config.get("auto_refresh_enabled", False)
            != config["auto_refresh_enabled"]
            or int(row.config.get("auto_refresh_hours", 3))
            != int(config["auto_refresh_hours"])
        )
        if not config["auto_refresh_enabled"]:
            defaults.update({
                "next_auto_refresh_at": None,
                "last_auto_status": "disabled",
                "last_auto_error_code": "",
            })
        elif auto_changed:
            defaults.update({
                "next_auto_refresh_at": timezone.now(),
                "last_auto_status": "scheduled",
                "last_auto_error_code": "",
            })
        NotificationRules.objects.update_or_create(
            connection=connection,
            user=request.user,
            defaults=defaults,
        )
        return Response(config)


class InspectionGapAcknowledgeAPIView(LocalAPIView):
    """Acknowledge the current gap only for its authorized owner."""

    def post(self, request, connection_id):
        from agione_ops.notification_rules import acknowledge_inspection_gap

        connection = get_connection_for(request.user, connection_id, "run_sync")
        gap = acknowledge_inspection_gap(
            connection, request.user, request.data.get("start"),
            request.data.get("end"),
        )
        return Response({"inspection_gap": gap})


class ConnectionListCreateAPIView(LocalAPIView):
    """List authorized connection metadata or explicitly configure a source."""

    def get(self, request):
        can_manage = has_action(request.user, "manage_connections")
        can_view = has_action(request.user, "view_business")
        can_sync = has_action(request.user, "run_sync")
        if can_manage:
            queryset = connections_for(request.user, "manage_connections")
        else:
            if not (can_view or can_sync):
                require_action(request.user, "view_business")
            grants = ConnectionGrant.objects.filter(user=request.user)
            scope = Q()
            if can_view:
                scope |= Q(can_view=True)
            if can_sync:
                scope |= Q(can_sync=True)
            queryset = SourceConnection.objects.filter(
                pk__in=grants.filter(scope).values("connection_id")
            )
        queryset = queryset.filter(removed_at__isnull=True)
        paginator = LimitOffsetPagination()
        paginator.default_limit = 50
        paginator.max_limit = 100
        rows = paginator.paginate_queryset(queryset, request, view=self)
        manage_ids = set(ConnectionGrant.objects.filter(
            user=request.user, can_view=True, can_sync=True,
            connection_id__in=[row.pk for row in rows],
        ).values_list("connection_id", flat=True))
        return Response(
            {
                "results": ConnectionSerializer(
                    rows, many=True, context={
                        "request": request,
                        "self_manage_actions": can_view and can_sync,
                        "self_manage_grant_ids": manage_ids,
                    }
                ).data,
                "count": paginator.count,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "capabilities": {
                    "canManageConnections": can_manage,
                    "nativeEnabled": getattr(
                        settings, "AGIONE_OPS_NATIVE_ENABLED", False
                    ),
                    "canSelfManageConnections": (
                        getattr(settings, "AGIONE_OPS_NATIVE_ENABLED", False)
                        and can_view and can_sync
                    ),
                },
            }
        )

    def post(self, request):
        require_action(request.user, "manage_connections")
        serializer = ConnectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        connection = serializer.save(created_by=request.user)
        return Response(
            ConnectionSerializer(
                connection, context={"request": request}
            ).data,
            status=201,
        )


def _probe_personal_connection(
    user, platform, access_key, secret_key, principal_kind=None,
):
    """Verify write-only credentials before creating a personal connection."""
    from agione_ops.native_client import NativeClient

    endpoint = getattr(
        settings, "AGIONE_OPS_SELF_SERVICE_ENDPOINTS", {}
    ).get(platform)
    if not endpoint:
        raise AgioneOpsError("SELF_SERVICE_ENDPOINT_UNAVAILABLE", status_code=503)
    candidate = SourceConnection(
        name="AGIOne personal connection",
        platform=platform,
        principal_kind="provider",
        source_kind="native",
        endpoint=endpoint,
        expected_tenant_id="pending",
        enabled=True,
        created_by=user,
    )
    candidate.set_credentials({
        "auth_mode": "aksk",
        "api_prefix": "/hyperone",
        "access_key": access_key,
        "secret_key": secret_key,
    })
    with NativeClient(candidate) as client:
        return (
            endpoint, candidate.get_credentials(),
            client.discover_identity(principal_kind),
        )


class SelfServiceConnectionListCreateAPIView(LocalAPIView):
    """Create a verified connection owned and usable by the current user."""

    def post(self, request):
        require_action(request.user, "view_business")
        require_action(request.user, "run_sync")
        serializer = SelfServiceConnectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        endpoint, credentials, identity = _probe_personal_connection(
            request.user,
            values["platform"],
            values["access_key"],
            values["secret_key"],
            values.get("principal_kind"),
        )
        with transaction.atomic():
            existing = SourceConnection.objects.filter(
                created_by=request.user,
                source_kind="native",
                platform=values["platform"],
                principal_kind=identity["principal_kind"],
                expected_tenant_id=identity["tenant_id"],
            )
            if existing.filter(enabled=True).exists():
                raise AgioneOpsError(
                    "SELF_SERVICE_CONNECTION_EXISTS", status_code=409
                )
            if existing.filter(removed_at__isnull=True).exists():
                raise AgioneOpsError(
                    "SELF_SERVICE_CONNECTION_DISABLED", status_code=409
                )
            label = "Pro" if values["platform"] == "pro" else "CC"
            role = identity["principal_kind"].title()
            connection = existing.select_for_update().first()
            if connection is None:
                connection = SourceConnection(
                    name=f"AGIOne {label} · {role}",
                    platform=values["platform"],
                    principal_kind=identity["principal_kind"],
                    source_kind="native",
                    endpoint=endpoint,
                    expected_tenant_id=identity["tenant_id"],
                    verified_tenant_id=identity["tenant_id"],
                    verified_at=timezone.now(),
                    enabled=True,
                    created_by=request.user,
                )
            else:
                connection.endpoint = endpoint
                connection.enabled = True
                connection.removed_at = None
            connection.set_credentials(credentials)
            connection.save()
            if connection.verified_at is None:
                connection.verified_tenant_id = identity["tenant_id"]
                connection.verified_at = timezone.now()
                connection.save(update_fields=["verified_tenant_id", "verified_at"])
            ConnectionGrant.objects.get_or_create(
                connection=connection,
                user=request.user,
                defaults={"can_view": True, "can_sync": True},
            )
        connection.refresh_from_db()
        from agione_ops.tasks import start_initial_native_sync

        start_initial_native_sync(connection, request.user)
        data = ConnectionSerializer(
            connection, context={"request": request}
        ).data
        data["role_verified"] = identity.get("role_verified") is True
        return Response(data, status=201)


class SelfServiceConnectionDetailAPIView(LocalAPIView):
    """Rotate or disable credentials on a user-owned personal connection."""

    def _owned(self, request, connection_id, *, lock=False):
        require_action(request.user, "view_business")
        require_action(request.user, "run_sync")
        grants = ConnectionGrant.objects.filter(
            user=request.user, can_view=True, can_sync=True,
        ).values("connection_id")
        if lock:
            connection = get_object_or_404(
                SourceConnection.objects.select_for_update(),
                pk=connection_id, created_by=request.user,
                source_kind="native", removed_at__isnull=True,
            )
            get_object_or_404(grants, connection_id=connection.pk)
            return connection
        queryset = SourceConnection.objects.filter(pk__in=grants)
        return get_object_or_404(
            queryset,
            pk=connection_id,
            created_by=request.user,
            source_kind="native",
            removed_at__isnull=True,
        )

    def patch(self, request, connection_id):
        connection = self._owned(request, connection_id)
        serializer = SelfServiceConnectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        if values["platform"] != connection.platform:
            raise ValidationError("连接平台不能修改。")
        _endpoint, credentials, identity = _probe_personal_connection(
            request.user,
            connection.platform,
            values["access_key"],
            values["secret_key"],
            connection.principal_kind,
        )
        if (
            identity["tenant_id"] != connection.expected_tenant_id
            or identity["principal_kind"] != connection.principal_kind
        ):
            raise AgioneOpsError("SOURCE_IDENTITY_MISMATCH", status_code=403)
        with transaction.atomic():
            connection = self._owned(request, connection_id, lock=True)
            connection.set_credentials(credentials)
            connection.save(update_fields=["credential_ciphertext", "key_id"])
            connection.verified_tenant_id = identity["tenant_id"]
            connection.verified_at = timezone.now()
            connection.enabled = True
            connection.save(update_fields=[
                "verified_tenant_id", "verified_at", "enabled"
            ])
        connection.refresh_from_db()
        return Response(
            ConnectionSerializer(
                connection, context={"request": request}
            ).data
        )

    def delete(self, request, connection_id):
        with transaction.atomic():
            connection = self._owned(request, connection_id, lock=True)
            connection.enabled = False
            connection.save(update_fields=["enabled"])
        return Response(status=204)


class SelfServiceConnectionRemoveAPIView(SelfServiceConnectionDetailAPIView):
    """Remove a personal connection while retaining its history."""

    http_method_names = ["post", "options"]

    def post(self, request, connection_id):
        EmptySerializer(data=request.data).is_valid(raise_exception=True)
        with transaction.atomic():
            connection = self._owned(request, connection_id, lock=True)
            from agione_ops.sync import interrupt_connection_run

            interrupt_connection_run(connection)
            connection.enabled = False
            connection.removed_at = timezone.now()
            connection.credential_ciphertext = ""
            connection.key_id = ""
            connection.save(update_fields=[
                "enabled", "removed_at", "credential_ciphertext", "key_id",
            ])
            NotificationDelivery.objects.filter(
                rules__connection=connection, status__in=["pending", "retrying"],
            ).update(status="silenced", error_message="连接已删除。")
        return Response(status=204)


class ConnectionDetailAPIView(LocalAPIView):
    """Update configuration only; there is deliberately no destructive API."""

    def patch(self, request, connection_id):
        require_action(request.user, "manage_connections")
        with transaction.atomic():
            connection = get_object_or_404(
                SourceConnection.objects.select_for_update(),
                pk=connection_id, removed_at__isnull=True,
            )
            serializer = ConnectionSerializer(
                connection,
                data=request.data,
                partial=True,
            )
            serializer.is_valid(raise_exception=True)
            connection = serializer.save()
        return Response(ConnectionSerializer(connection).data)


class ConnectionGrantAPIView(LocalAPIView):
    """Explicit grants never arise from staff status or a legacy role."""

    def put(self, request, connection_id, user_id):
        require_action(request.user, "manage_connections")
        serializer = GrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            connection = get_object_or_404(
                SourceConnection.objects.select_for_update(),
                pk=connection_id,
            )
            user = get_object_or_404(
                get_user_model(), pk=user_id, is_active=True
            )
            grant, _ = ConnectionGrant.objects.get_or_create(
                connection=connection,
                user=user,
            )
            for key, value in serializer.validated_data.items():
                setattr(grant, key, value)
            grant.save()
        return Response(
            {
                "user_id": user.pk,
                "can_view": grant.can_view,
                "can_sync": grant.can_sync,
            }
        )


class TenantClassificationListAPIView(LocalAPIView):
    """List classifications from the authorized Operator directory."""

    def get(self, request, connection_id):
        from agione_ops.native_account_scope import tenant_classification
        from agione_ops.tenant_directory import (
            classification_version, tenant_directory,
        )

        connection = get_connection_for(request.user, connection_id)
        search = request.query_params.get("search", "").strip().casefold()
        classification_filter = request.query_params.get("classification", "")
        source_filter = request.query_params.get("source", "")
        if classification_filter not in {"", "internal", "external", "unknown"}:
            raise ValidationError({"classification": "Invalid classification."})
        if source_filter not in {"", "automatic", "manual"}:
            raise ValidationError({"source": "Invalid source."})
        try:
            limit = int(request.query_params.get("limit", 50))
            offset = int(request.query_params.get("offset", 0))
        except (TypeError, ValueError):
            raise ValidationError({"pagination": "Invalid limit or offset."})
        if not 1 <= limit <= 100 or offset < 0:
            raise ValidationError({"pagination": "Invalid limit or offset."})
        version = classification_version(connection, request.user)
        refresh = request.query_params.get("refresh", "0")
        if refresh not in {"0", "1"}:
            raise ValidationError({"refresh": "Invalid refresh value."})
        _, rows, types, overrides = tenant_directory(
            connection, request.user, use_cache=True, refresh=refresh == "1",
        )
        if version != classification_version(connection, request.user):
            raise AgioneOpsError("CLASSIFICATION_CHANGED", status_code=409)
        result = []
        for row in rows:
            tenant_id = str(row["tenantId"])
            classification, source = tenant_classification(
                tenant_id, types, overrides,
            )
            name = row["customerName"]
            if search and search not in tenant_id.casefold() and (
                search not in name.casefold()
            ):
                continue
            if classification_filter and classification != classification_filter:
                continue
            if source_filter and source != source_filter:
                continue
            result.append({
                "tenant_id": tenant_id,
                "name": name,
                "classification": classification,
                "source": source,
                "included": classification != "internal",
            })
        result.sort(key=lambda row: (row["name"].casefold(), row["tenant_id"]))
        return Response({
            "results": result[offset:offset + limit], "count": len(result),
            "limit": limit, "offset": offset,
            "version": version,
        })

    def post(self, request, connection_id):
        from agione_ops.models import (
            TenantClassification, TenantClassificationChange,
        )
        from agione_ops.native_finance_refresh import _operator
        from agione_ops.native_sync_models import NativeFinanceProjection
        from agione_ops.native_account_scope import tenant_classification
        from agione_ops.tenant_directory import (
            classification_version, operator_overrides, tenant_directory,
        )

        require_action(request.user, "manage_connections")
        connection = get_connection_for(request.user, connection_id)
        tenant_id = request.data.get("tenant_id")
        choice = request.data.get("classification")
        expected = request.data.get("version")
        if not isinstance(tenant_id, str) or not re.fullmatch(r"[0-9]{1,40}", tenant_id):
            raise ValidationError({"tenant_id": "Invalid tenant ID."})
        if choice not in {"internal", "external", "automatic"}:
            raise ValidationError({"classification": "Invalid classification."})
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValidationError({"version": "Invalid version."})
        operator, rows, types, _ = tenant_directory(
            connection, request.user, use_cache=True, refresh=False,
        )
        if tenant_id not in {str(row["tenantId"]) for row in rows}:
            from rest_framework.exceptions import NotFound

            raise NotFound("Tenant not found.")
        with transaction.atomic():
            locked = SourceConnection.objects.select_for_update().get(pk=operator.pk)
            require_action(request.user, "manage_connections")
            connection = get_connection_for(request.user, connection_id)
            current_operator = _operator(connection, request.user)
            if (not current_operator or current_operator.pk != operator.pk
                    or locked.config_version != operator.config_version
                    or locked.credential_version != operator.credential_version):
                raise AgioneOpsError("CONNECTION_CHANGED", status_code=409)
            if classification_version(connection, request.user) != expected:
                raise AgioneOpsError("CLASSIFICATION_CHANGED", status_code=409)
            if choice == "automatic":
                TenantClassification.objects.filter(
                    operator=operator, tenant_id=tenant_id,
                ).delete()
            else:
                TenantClassification.objects.update_or_create(
                    operator=operator, tenant_id=tenant_id,
                    defaults={"classification": choice, "updated_by": request.user},
                )
            TenantClassificationChange.objects.create(
                operator=operator, tenant_id=tenant_id,
                classification=choice, actor=request.user,
            )
            version = classification_version(connection, request.user)
            projections = NativeFinanceProjection.objects.filter(
                operator=operator,
            )
            projections.update(status="stale", error_code="CLASSIFICATION_CHANGED")
            from agione_ops.tasks import refresh_classification_finance

            transaction.on_commit(
                lambda: refresh_classification_finance.delay(operator.pk)
            )
        classification, source = tenant_classification(
            tenant_id,
            types,
            operator_overrides(operator),
        )
        return Response({
            "version": version,
            "tenant_id": tenant_id,
            "classification": classification,
            "source": source,
            "included": classification != "internal",
            "finance_state": "queued",
        })


class LiveOperationAPIView(LocalAPIView):
    """Read a published local native snapshot without implicit acquisition."""

    def post(self, request, connection_id):
        from agione_ops.native_queries import query_live_operation
        from agione_ops.native_serializers import LiveQuerySerializer

        connection = get_connection_for(
            request.user, connection_id, "view_business"
        )
        serializer = LiveQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from agione_ops.observability import set_fields

        set_fields(
            operation=serializer.validated_data.get("operation", "dashboard"),
            data_version=serializer.validated_data.get("data_version"),
        )
        return Response(query_live_operation(
            connection, request.user, serializer.validated_data
        ))


class FinanceRefreshAPIView(LocalAPIView):
    """Refresh the authorized user's existing finance projection."""

    def post(self, request, connection_id):
        from agione_ops.native_finance_refresh import finance_for, schedule_finance
        from agione_ops.native_sync_models import NativeFinanceProjection

        connection = get_connection_for(request.user, connection_id, "run_sync")
        get_connection_for(request.user, connection_id, "view_business")
        EmptySerializer(data=request.data).is_valid(raise_exception=True)
        row = NativeFinanceProjection.objects.filter(
            connection=connection, user=request.user,
        ).first()
        if row is None or finance_for(connection, request.user)[1] is None:
            raise AgioneOpsError("NATIVE_FINANCE_NOT_COLLECTED", status_code=409)
        schedule_finance(row.run_id)
        finance, _ = finance_for(connection, request.user)
        if finance.get("refreshState") not in {"queued", "running", "retrying"}:
            raise AgioneOpsError("FINANCE_REFRESH_FAILED", status_code=409)
        return Response({"state": finance["refreshState"]}, status=202)


class ConnectionVerifyAPIView(LocalAPIView):
    """Identity verification is an explicit action, never a GET side effect."""

    def post(self, request, connection_id):
        from agione_ops.sync import verify_connection

        connection = get_connection_for(
            request.user,
            connection_id,
            "manage_connections",
        )
        serializer = EmptySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if connection.source_kind == "native":
            from agione_ops.native_client import NativeClient
            epoch = (connection.config_version, connection.credential_version)
            try:
                with NativeClient(connection) as client:
                    identity = client.identity()
            finally:
                current = get_connection_for(
                    request.user, connection_id, "manage_connections"
                )
                if epoch != (current.config_version, current.credential_version):
                    from agione_ops.client import AgioneOpsError
                    raise AgioneOpsError("CONNECTION_CHANGED", status_code=409)
            from django.utils import timezone
            connection.verified_tenant_id = identity["tenant_id"]
            connection.verified_at = timezone.now()
            connection.save(update_fields=["verified_tenant_id", "verified_at"])
            from agione_ops.tasks import start_initial_native_sync

            start_initial_native_sync(connection, request.user)
            return Response({"state": "connected", "mode": "live", **identity})
        return Response(verify_connection(connection, request.user))


class SyncRunCreateAPIView(LocalAPIView):
    """Accept an idempotent request; only a run UUID enters the task queue."""

    def post(self, request, connection_id):
        from agione_ops.models import NotificationRules
        from agione_ops.notification_rules import extend_manual_window
        from agione_ops.sync import submit_sync

        connection = get_connection_for(
            request.user, connection_id, "run_sync"
        )
        serializer = SyncRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = request.headers.get("Idempotency-Key", "")
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", key):
            raise ValidationError(
                "A valid Idempotency-Key header is required."
            )
        window = serializer.validated_data["window"]
        rules = NotificationRules.objects.filter(
            connection=connection,
            user=request.user,
        ).first()
        if (
            connection.source_kind == "native"
            and rules
            and rules.config.get("enabled")
        ):
            from django.utils import timezone

            window = extend_manual_window(window, timezone.now())
        try:
            run, created = submit_sync(
                connection,
                request.user,
                window_start=window["start"],
                window_end=window["end_exclusive"],
                timezone=window["timezone"],
                idempotency_key=key,
            )
        except AgioneOpsError as exc:
            if exc.code != "CONNECTION_BUSY":
                raise
            active = SyncRun.objects.filter(
                pk=connection.active_run_id,
                connection=connection,
            ).first()
            if active is None:
                raise
            payload = run_payload(active)
            payload["errorCode"] = "CONNECTION_BUSY"
            return Response(payload, status=409)
        run.refresh_from_db()
        return Response(run_payload(run), status=202 if created else 200)


class SyncRunDetailAPIView(LocalAPIView):
    """Progress requires connection sync permission and the original owner."""

    def get(self, request, connection_id, run_id):
        get_connection_for(request.user, connection_id, "run_sync")
        run = get_object_or_404(
            SyncRun,
            pk=run_id,
            connection_id=connection_id,
        )
        authorize_run(request.user, run)
        return Response(run_payload(run))


class SnapshotOperationAPIView(LocalAPIView):
    """Expose closed read-only operations, not a generic source URL proxy."""

    def post(self, request, connection_id):
        from agione_ops.snapshot_queries import query_operation
        from agione_ops.snapshot_serializers import (
            SnapshotOperationSerializer,
        )

        connection = get_connection_for(
            request.user, connection_id, "view_business"
        )
        serializer = SnapshotOperationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from agione_ops.observability import set_fields

        set_fields(
            operation=serializer.validated_data.get("operation", "dashboard"),
            data_version=serializer.validated_data.get("data_version"),
        )
        return Response(
            query_operation(
                connection, request.user, serializer.validated_data
            )
        )


class DashboardQueryAPIView(LocalAPIView):
    """Read one published dataset without implicit acquisition or finance."""

    def post(self, request, connection_id):
        from agione_ops.queries import query_dashboard

        connection = get_connection_for(
            request.user,
            connection_id,
            "view_business",
        )
        serializer = DashboardQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from agione_ops.observability import set_fields

        set_fields(
            operation=serializer.validated_data.get("operation", "dashboard"),
            data_version=serializer.validated_data.get("data_version"),
        )
        return Response(
            query_dashboard(
                connection,
                request.user,
                version_id=serializer.validated_data.get("data_version"),
                window_start=serializer.validated_data.get("window", {}).get(
                    "start"
                ),
                window_end=serializer.validated_data.get("window", {}).get(
                    "end_exclusive"
                ),
            )
        )
