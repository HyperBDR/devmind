from __future__ import annotations

from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.audit import record_audit_event
from quotation.models import AuditEvent
from quotation.services.feishu_client import FeishuAPIError
from quotation.services.storage_control import (
    FeishuStorageProvider,
    StorageRouter,
)

from . import common


class FeishuStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        legacy_configured = bool(
            settings.FEISHU_APP_ID
            and settings.FEISHU_APP_SECRET
            and common._has_archive_folder()
        )
        database_configured = False
        if settings.QUOTATION_STORAGE_ROUTER_ENABLED:
            try:
                StorageRouter().resolve()
                database_configured = True
            except LookupError:
                pass
        configured = legacy_configured or database_configured
        return Response(
            {
                "configured": configured,
                "connected": configured,
                "mode": (
                    "managed_connection"
                    if database_configured
                    else "system_archive_folder"
                ),
                "feishu_user_name": None,
                "feishu_open_id": None,
                "expires_at": None,
                "preferred_folder_token": None,
                "preferred_folder_name": common.ARCHIVE_FOLDER_LABEL
                if configured
                else None,
                "fallback_folder_token": None,
                "redirect_uri": None,
            }
        )


class FeishuOAuthStartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "detail": (
                    "Quotation Feishu uses a system-managed archive folder; "
                    "user OAuth is disabled."
                )
            },
            status=400,
        )


class FeishuOAuthCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(
            {
                "detail": (
                    "Quotation Feishu uses a system-managed archive folder; "
                    "user OAuth is disabled."
                )
            },
            status=400,
        )


class FeishuPreferredFolderView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        try:
            common._archive_folder_token()
        except FeishuAPIError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(
            {
                "preferred_folder_token": None,
                "preferred_folder_name": common.ARCHIVE_FOLDER_LABEL,
            }
        )


class FeishuHealthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        connection = None
        try:
            client, token, folder_token, connection, mount = (
                common._system_drive_context_details()
            )
            if connection is not None and mount is not None:
                FeishuStorageProvider(connection).health_check(mount)
            else:
                client.get_folder_meta(token, folder_token)
        except FeishuAPIError as exc:
            record_audit_event(
                request=request,
                module="storage",
                action="health_checked",
                event_name="storage.connection_health_checked",
                result=AuditEvent.RESULT_FAILED,
                target_type="storage_connection",
                target_id=connection.id if connection else "legacy-default",
                storage_connection_id=connection.id if connection else "",
                error_code=(
                    f"feishu_{exc.code}"
                    if exc.code is not None
                    else "feishu_health_failed"
                ),
            )
            return Response({"detail": str(exc)}, status=400)
        record_audit_event(
            request=request,
            module="storage",
            action="health_checked",
            event_name="storage.connection_health_checked",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="storage_connection",
            target_id=connection.id if connection else "legacy-default",
            storage_connection_id=connection.id if connection else "",
        )
        return Response(
            {
                "ok": True,
                "mode": "managed_connection"
                if connection is not None
                else "system_archive_folder",
                "connection_id": connection.id if connection else None,
            }
        )
