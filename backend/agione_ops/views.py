"""Thin authenticated APIs for the local synthetic AGIOne workflow."""

import logging
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse
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
from agione_ops.models import ConnectionGrant, SourceConnection, SyncRun
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


class ConnectionListCreateAPIView(LocalAPIView):
    """List authorized connection metadata or explicitly configure a source."""

    def get(self, request):
        if has_action(request.user, "manage_connections"):
            queryset = connections_for(request.user, "manage_connections")
        else:
            ids = set()
            for action in ("view_business", "run_sync"):
                if has_action(request.user, action):
                    ids.update(
                        connections_for(request.user, action).values_list(
                            "id", flat=True
                        )
                    )
            if not any(
                has_action(request.user, action)
                for action in ("view_business", "run_sync")
            ):
                require_action(request.user, "view_business")
            queryset = SourceConnection.objects.filter(pk__in=ids)
        paginator = LimitOffsetPagination()
        paginator.default_limit = 50
        paginator.max_limit = 100
        rows = paginator.paginate_queryset(queryset, request, view=self)
        return Response(
            {
                "results": ConnectionSerializer(rows, many=True).data,
                "count": paginator.count,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "capabilities": {
                    "canManageConnections": has_action(
                        request.user, "manage_connections"
                    ),
                    "nativeEnabled": getattr(
                        settings, "AGIONE_OPS_NATIVE_ENABLED", False
                    ),
                },
            }
        )

    def post(self, request):
        require_action(request.user, "manage_connections")
        serializer = ConnectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        connection = serializer.save(created_by=request.user)
        return Response(ConnectionSerializer(connection).data, status=201)


class ConnectionDetailAPIView(LocalAPIView):
    """Update configuration only; there is deliberately no destructive API."""

    def patch(self, request, connection_id):
        require_action(request.user, "manage_connections")
        with transaction.atomic():
            connection = get_object_or_404(
                SourceConnection.objects.select_for_update(),
                pk=connection_id,
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
        if finance.get("refreshState") not in {"queued", "running"}:
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
