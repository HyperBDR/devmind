from __future__ import annotations

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.audit import record_audit_event
from quotation.models import AuditEvent, QuotationUploadPermission
from quotation.permissions import is_quotation_platform_admin
from quotation.services.permission_service import (
    find_folder_asset,
    folder_label,
    folder_rows,
    parse_expires_at,
    platform_users,
)


def _require_admin(user) -> None:
    if not is_quotation_platform_admin(user):
        raise PermissionDenied(
            "Only quotation platform administrators can manage upload access."
        )


def _permission_row(permission: QuotationUploadPermission) -> dict:
    return {
        "id": permission.id,
        "user_id": permission.user_id,
        "user_name": permission.user.get_full_name()
        or permission.user.username,
        "folder_token": permission.folder_token,
        "folder_name": permission.folder_name,
        "expires_at": permission.expires_at,
        "created_at": permission.created_at,
        "granted_by": permission.granted_by.username,
    }


class QuotationUploadPermissionView(APIView):
    """List and create exact-directory upload permissions."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_admin(request.user)
        permissions = QuotationUploadPermission.objects.filter(
            is_active=True,
            revoked_at__isnull=True,
        ).select_related("user", "granted_by")
        return Response(
            {
                "users": platform_users(),
                "folders": folder_rows(),
                "permissions": [
                    _permission_row(permission) for permission in permissions
                ],
            }
        )

    def post(self, request):
        _require_admin(request.user)
        try:
            user_id = int(request.data.get("user_id"))
        except (TypeError, ValueError) as error:
            raise ValidationError(
                {"user_id": "A valid user is required."}
            ) from error
        user = User.objects.filter(id=user_id, is_active=True).first()
        if user is None:
            raise ValidationError({"user_id": "User not found."})
        folder_token = str(request.data.get("folder_token") or "").strip()
        asset = find_folder_asset(folder_token)
        if asset is None:
            raise ValidationError({"folder_token": "Folder not found."})
        expires_at = parse_expires_at(request.data.get("expires_at"))
        permission = QuotationUploadPermission.objects.filter(
            user=user,
            folder_token=folder_token,
            is_active=True,
        ).first()
        created = permission is None
        if permission is None:
            permission = QuotationUploadPermission.objects.create(
                user=user,
                folder_token=folder_token,
                folder_name=folder_label(asset, folder_token),
                granted_by=request.user,
                expires_at=expires_at,
            )
        else:
            permission.folder_name = folder_label(asset, folder_token)
            permission.granted_by = request.user
            permission.expires_at = expires_at
            permission.revoked_at = None
            permission.save(
                update_fields=[
                    "folder_name",
                    "granted_by",
                    "expires_at",
                    "revoked_at",
                    "updated_at",
                ]
            )
        record_audit_event(
            request=request,
            module="permissions",
            action="grant_upload",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="folder_upload_permission",
            target_id=str(permission.id),
            target_label=permission.folder_name,
            summary="Granted quotation directory upload access.",
            changes={
                "expires_at": expires_at.isoformat() if expires_at else None
            },
        )
        return Response(
            _permission_row(permission),
            status=201 if created else 200,
        )


class QuotationUploadPermissionDetailView(APIView):
    """Edit or revoke one exact-directory upload permission."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, permission_id: int):
        _require_admin(request.user)
        permission = self._permission(permission_id)
        if "expires_at" not in request.data:
            raise ValidationError(
                {"expires_at": "Expiration is required for this update."}
            )
        previous = permission.expires_at
        permission.expires_at = parse_expires_at(
            request.data.get("expires_at")
        )
        permission.granted_by = request.user
        permission.save(
            update_fields=[
                "expires_at",
                "granted_by",
                "updated_at",
            ]
        )
        record_audit_event(
            request=request,
            module="permissions",
            action="update_upload",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="folder_upload_permission",
            target_id=str(permission.id),
            target_label=permission.folder_name,
            summary="Updated quotation directory upload access.",
            changes={
                "expires_at": {
                    "before": previous.isoformat() if previous else None,
                    "after": (
                        permission.expires_at.isoformat()
                        if permission.expires_at
                        else None
                    ),
                }
            },
        )
        return Response(_permission_row(permission))

    def delete(self, request, permission_id: int):
        _require_admin(request.user)
        permission = self._permission(permission_id)
        permission.is_active = False
        permission.revoked_at = timezone.now()
        permission.save(
            update_fields=["is_active", "revoked_at", "updated_at"]
        )
        record_audit_event(
            request=request,
            module="permissions",
            action="revoke_upload",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="folder_upload_permission",
            target_id=str(permission.id),
            target_label=permission.folder_name,
            summary="Revoked quotation directory upload access.",
        )
        return Response(status=204)

    @staticmethod
    def _permission(permission_id: int) -> QuotationUploadPermission:
        permission = (
            QuotationUploadPermission.objects.filter(
                pk=permission_id,
                is_active=True,
                revoked_at__isnull=True,
            )
            .select_related("user", "granted_by")
            .first()
        )
        if permission is None:
            raise ValidationError("Upload permission not found.")
        return permission
