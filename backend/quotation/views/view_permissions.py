from __future__ import annotations

from datetime import datetime

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.access import get_effective_feature_keys
from quotation.audit import record_audit_event
from quotation.models import (
    AuditEvent,
    DocumentAsset,
    QuotationViewPermission,
    QuotationViewPermissionTarget,
)
from quotation.permissions import is_quotation_platform_admin


def _require_admin(user):
    has_platform_access = (
        "quotation_management" in get_effective_feature_keys(user)
    )
    if not has_platform_access or not is_quotation_platform_admin(user):
        raise PermissionDenied(
            "Only quotation platform administrators can manage view access."
        )


def _folder_name(asset: DocumentAsset) -> str:
    path = asset.feishu_folder_path
    if isinstance(path, list) and path:
        item = path[-1]
        if isinstance(item, dict):
            return str(item.get("name") or "")
        return str(item or "")
    return ""


def _folder_rows():
    rows = {}
    assets = DocumentAsset.objects.filter(
        source="feishu",
    ).only(
        "feishu_folder_token",
        "feishu_folder_path",
    )
    for asset in assets:
        path = asset.feishu_folder_path or []
        path_items = [item for item in path if isinstance(item, dict)]
        if not path_items and asset.feishu_folder_token:
            path_items = [
                {
                    "token": asset.feishu_folder_token,
                    "name": asset.feishu_folder_token,
                }
            ]
        for item in path_items:
            token = str(item.get("token") or "")
            if not token:
                continue
            rows.setdefault(
                token,
                {
                    "token": token,
                    "name": str(item.get("name") or token),
                    "path": path,
                },
            )
    return sorted(rows.values(), key=lambda item: item["name"].casefold())


def _folder_asset(folder_token: str):
    assets = DocumentAsset.objects.filter(source="feishu").only(
        "feishu_folder_token",
        "feishu_folder_path",
    )
    for asset in assets:
        tokens = {
            str(item.get("token") or "")
            for item in asset.feishu_folder_path or []
            if isinstance(item, dict)
        }
        tokens.add(str(asset.feishu_folder_token or ""))
        if folder_token in tokens:
            return asset
    return None


def _folder_label(asset: DocumentAsset, folder_token: str) -> str:
    for item in asset.feishu_folder_path or []:
        item_token = str(item.get("token") or "") if isinstance(
            item,
            dict,
        ) else ""
        if item_token == folder_token:
            return str(item.get("name") or folder_token)
    return _folder_name(asset) or folder_token


def _document_rows():
    rows = {}
    assets = DocumentAsset.objects.filter(source="feishu").select_related(
        "quotation"
    ).order_by("-created_at")
    for asset in assets:
        key = asset.feishu_file_token or asset.id
        if key in rows:
            continue
        rows[key] = {
            "id": asset.id,
            "file_token": asset.feishu_file_token or "",
            "file_name": asset.file_name,
            "folder_token": asset.feishu_folder_token or "",
            "folder_name": _folder_name(asset),
            "quotation_id": asset.quotation_id,
            "quote_no": asset.quotation.quote_no
            if asset.quotation_id and asset.quotation
            else "",
        }
    return list(rows.values())


def _platform_users():
    users = []
    for user in User.objects.filter(is_active=True).order_by(
        "username",
        "id",
    ):
        if is_quotation_platform_admin(user):
            continue
        if (
            "quotation_management"
            not in get_effective_feature_keys(user)
        ):
            continue
        users.append(
            {
                "id": user.id,
                "username": user.username,
                "name": user.get_full_name() or user.username,
                "email": user.email or "",
            }
        )
    return users


def _parse_expires_at(value):
    """Parse an optional future expiration timestamp."""
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise ValidationError(
            {"expires_at": "Invalid expiration time."}
        ) from error
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    if parsed <= timezone.now():
        raise ValidationError(
            {"expires_at": "Expiration must be in the future."}
        )
    return parsed


def _permission_status(permission: QuotationViewPermission) -> str:
    """Return the effective lifecycle status for a view grant."""
    if not permission.is_active:
        return "revoked"
    if permission.expires_at and permission.expires_at <= timezone.now():
        return "expired"
    return "active"


def _validate_grantee(user: User | None) -> User:
    """Require an active ordinary user with first-layer access."""
    if (
        user is None
        or user.is_staff
        or user.is_superuser
        or is_quotation_platform_admin(user)
        or "quotation_management" not in get_effective_feature_keys(user)
    ):
        raise ValidationError(
            {
                "user_id": (
                    "User must have first-layer Quote Desk access and "
                    "an ordinary Quote Desk role."
                )
            }
        )
    return user


def _permission_row(permission: QuotationViewPermission):
    target_id = (
        permission.folder_token
        if permission.target_type == QuotationViewPermissionTarget.FOLDER
        else permission.document_id
    )
    return {
        "id": permission.id,
        "user_id": permission.user_id,
        "user_name": permission.user.get_full_name()
        or permission.user.username,
        "target_type": permission.target_type,
        "target_id": str(target_id or ""),
        "target_name": permission.folder_name
        or (permission.document.file_name if permission.document else ""),
        "folder_token": permission.folder_token,
        "document_id": permission.document_id,
        "expires_at": permission.expires_at,
        "status": _permission_status(permission),
        "created_at": permission.created_at,
        "updated_at": permission.updated_at,
        "granted_by": permission.granted_by.username,
    }


def _permission_target_summary(
    permission: QuotationViewPermission,
) -> dict:
    """Return stable resource details for a view-permission audit event."""
    target_id = (
        permission.folder_token
        if permission.target_type
        == QuotationViewPermissionTarget.FOLDER
        else permission.document_id
    )
    return {
        "target_type": permission.target_type,
        "target_id": str(target_id or ""),
    }


class QuotationViewPermissionView(APIView):
    """List and create administrator-granted quotation view access."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_admin(request.user)
        permissions = QuotationViewPermission.objects.filter(
            is_active=True,
        ).select_related("user", "document", "granted_by")
        return Response(
            {
                "users": _platform_users(),
                "folders": _folder_rows(),
                "documents": _document_rows(),
                "permissions": [
                    _permission_row(permission) for permission in permissions
                ],
            }
        )

    def post(self, request):
        _require_admin(request.user)
        target_type = str(request.data.get("target_type") or "").strip()
        target_id = str(request.data.get("target_id") or "").strip()
        try:
            user_id = int(request.data.get("user_id"))
        except (TypeError, ValueError) as error:
            raise ValidationError(
                {"user_id": "A valid user is required."}
            ) from error
        user = _validate_grantee(
            User.objects.filter(id=user_id, is_active=True).first()
        )
        if target_type not in {
            QuotationViewPermissionTarget.FOLDER,
            QuotationViewPermissionTarget.DOCUMENT,
        }:
            raise ValidationError({"target_type": "Unsupported target type."})
        if not target_id:
            raise ValidationError({"target_id": "A target is required."})

        defaults = {
            "target_type": target_type,
            "granted_by": request.user,
            "is_active": True,
            "expires_at": _parse_expires_at(
                request.data.get("expires_at")
            ),
        }
        if target_type == QuotationViewPermissionTarget.FOLDER:
            asset = _folder_asset(target_id)
            if asset is None:
                raise ValidationError({"target_id": "Folder not found."})
            duplicate = QuotationViewPermission.objects.filter(
                user=user,
                target_type=target_type,
                folder_token=target_id,
                is_active=True,
            ).exists()
            create_fields = {
                **defaults,
                "user": user,
                "folder_token": target_id,
                "folder_name": _folder_label(asset, target_id),
                "document": None,
            }
        else:
            document = DocumentAsset.objects.filter(
                pk=target_id,
                source="feishu",
            ).first()
            if document is None:
                raise ValidationError({"target_id": "Document not found."})
            duplicate = QuotationViewPermission.objects.filter(
                user=user,
                target_type=target_type,
                document=document,
                is_active=True,
            ).exists()
            create_fields = {
                **defaults,
                "user": user,
                "document": document,
                "folder_token": "",
                "folder_name": "",
            }
        if duplicate:
            raise ValidationError(
                "An active view permission already exists."
            )
        try:
            with transaction.atomic():
                permission = QuotationViewPermission.objects.create(
                    **create_fields
                )
        except IntegrityError as error:
            raise ValidationError(
                "An active view permission already exists."
            ) from error
        target_label = permission.folder_name or (
            permission.document.file_name if permission.document else ""
        )
        record_audit_event(
            request=request,
            module="permissions",
            action="grant_view",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="quotation_view_permission",
            target_id=str(permission.id),
            target_label=target_label,
            summary="Granted quotation view access.",
            after_summary={
                **_permission_target_summary(permission),
                "user_id": user.id,
                "expires_at": (
                    permission.expires_at.isoformat()
                    if permission.expires_at
                    else None
                ),
                "status": _permission_status(permission),
            },
        )
        return Response(_permission_row(permission), status=201)


class QuotationViewPermissionRevokeView(APIView):
    """Edit or revoke one administrator-granted view permission."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, permission_id: int):
        _require_admin(request.user)
        permission = QuotationViewPermission.objects.filter(
            pk=permission_id,
            is_active=True,
        ).select_related("user", "document", "granted_by").first()
        if permission is None:
            raise ValidationError("View permission not found.")
        if "expires_at" not in request.data:
            raise ValidationError(
                {"expires_at": "Expiration is required."}
            )
        before_expiry = permission.expires_at
        expires_at = _parse_expires_at(request.data.get("expires_at"))
        if expires_at == before_expiry:
            raise ValidationError(
                {"expires_at": "Expiration has not changed."}
            )
        permission.expires_at = expires_at
        permission.save(update_fields=["expires_at", "updated_at"])
        target_label = permission.folder_name or (
            permission.document.file_name if permission.document else ""
        )
        record_audit_event(
            request=request,
            module="permissions",
            action="change_view_expiry",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="quotation_view_permission",
            target_id=str(permission.id),
            target_label=target_label,
            summary="Changed quotation view access expiration.",
            before_summary={
                **_permission_target_summary(permission),
                "expires_at": (
                    before_expiry.isoformat() if before_expiry else None
                )
            },
            after_summary={
                **_permission_target_summary(permission),
                "expires_at": (
                    expires_at.isoformat() if expires_at else None
                )
            },
        )
        return Response(_permission_row(permission))

    def delete(self, request, permission_id: int):
        _require_admin(request.user)
        permission = QuotationViewPermission.objects.filter(
            pk=permission_id,
            is_active=True,
        ).select_related("user", "document", "granted_by").first()
        if permission is None:
            raise ValidationError("View permission not found.")
        before_status = _permission_status(permission)
        permission.is_active = False
        permission.save(update_fields=["is_active", "updated_at"])
        record_audit_event(
            request=request,
            module="permissions",
            action="revoke_view",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="quotation_view_permission",
            target_id=str(permission.id),
            target_label=permission.folder_name
            or (permission.document.file_name if permission.document else ""),
            summary="Revoked quotation view access.",
            before_summary={
                **_permission_target_summary(permission),
                "status": before_status,
                "user_id": permission.user_id,
            },
            after_summary={
                **_permission_target_summary(permission),
                "status": "revoked",
            },
        )
        return Response(status=204)
