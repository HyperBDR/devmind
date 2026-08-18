"""Shared quotation permission discovery and decision services."""

from __future__ import annotations

from datetime import datetime

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.access import get_effective_feature_keys
from quotation.models import (
    DocumentAsset,
    QuotationAccessRequest,
    QuotationAccessRequestStatus,
    QuotationAccessRequestType,
    QuotationUploadPermission,
    QuotationViewPermission,
    QuotationViewPermissionTarget,
)
from quotation.permissions import is_quotation_platform_admin


def parse_expires_at(value):
    """Parse an optional future expiration timestamp."""
    if not value:
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


def folder_name(asset: DocumentAsset) -> str:
    """Return the final display name from one stored Feishu path."""
    path = asset.feishu_folder_path
    if isinstance(path, list) and path:
        item = path[-1]
        if isinstance(item, dict):
            return str(item.get("name") or "")
        return str(item or "")
    return ""


def folder_rows() -> list[dict]:
    """Return unique known Feishu folders without enumerating remote files."""
    rows = {}
    assets = DocumentAsset.objects.filter(source="feishu").only(
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


def safe_folder_rows() -> list[dict]:
    """Return only non-sensitive folder identifiers and display names."""
    return [
        {"token": row["token"], "name": row["name"]} for row in folder_rows()
    ]


def find_folder_asset(folder_token: str):
    """Find a stored asset whose path contains the exact folder token."""
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


def folder_label(asset: DocumentAsset, folder_token: str) -> str:
    """Return a folder label matched to the exact token."""
    for item in asset.feishu_folder_path or []:
        if (
            isinstance(item, dict)
            and str(item.get("token") or "") == folder_token
        ):
            return str(item.get("name") or folder_token)
    return folder_name(asset) or folder_token


def document_rows() -> list[dict]:
    """Return known Feishu documents for administrator-only selection."""
    rows = {}
    assets = (
        DocumentAsset.objects.filter(source="feishu")
        .select_related("quotation")
        .order_by("-created_at")
    )
    for asset in assets:
        key = asset.feishu_file_token or asset.id
        if key in rows:
            continue
        rows[key] = {
            "id": asset.id,
            "file_token": asset.feishu_file_token or "",
            "file_name": asset.file_name,
            "folder_token": asset.feishu_folder_token or "",
            "folder_name": folder_name(asset),
            "quotation_id": asset.quotation_id,
            "quote_no": (
                asset.quotation.quote_no
                if asset.quotation_id and asset.quotation
                else ""
            ),
        }
    return list(rows.values())


def platform_users() -> list[dict]:
    """Return active ordinary Quote Desk users eligible for grants."""
    users = []
    for user in User.objects.filter(is_active=True).order_by(
        "username",
        "id",
    ):
        if is_quotation_platform_admin(user):
            continue
        if "quotation_management" not in get_effective_feature_keys(user):
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


def access_request_target_values(
    request_type: str,
    target_id: str,
) -> dict:
    """Resolve one submitted target without exposing an unrestricted list."""
    if request_type == QuotationAccessRequestType.DOCUMENT_VIEW:
        document = DocumentAsset.objects.filter(
            Q(pk=target_id) | Q(feishu_file_token=target_id),
            source="feishu",
        ).first()
        if document is None:
            raise ValidationError(
                {"target_id": ("Document is unavailable for access requests.")}
            )
        return {
            "document": document,
            "document_id_snapshot": document.id,
            "document_name": document.file_name,
        }
    asset = find_folder_asset(target_id)
    if asset is None:
        raise ValidationError(
            {"target_id": "Directory is unavailable for access requests."}
        )
    return {
        "folder_token": target_id,
        "folder_name": folder_label(asset, target_id),
    }


def approve_access_request(
    access_request: QuotationAccessRequest,
    reviewer,
    raw_expires_at,
):
    """Approve a locked request into the canonical permission model."""
    if access_request.status != QuotationAccessRequestStatus.PENDING:
        raise ValidationError("Only pending requests can be approved.")
    expires_at = parse_expires_at(raw_expires_at)
    access_request.reviewed_by = reviewer
    access_request.reviewed_at = timezone.now()
    access_request.expires_at = expires_at
    if access_request.request_type == QuotationAccessRequestType.FOLDER_UPLOAD:
        permission, created = _active_upload_permission(
            access_request,
            expires_at,
        )
        access_request.upload_permission = permission
    else:
        permission, created = _active_view_permission(
            access_request,
            expires_at,
        )
        access_request.view_permission = permission
    access_request.status = QuotationAccessRequestStatus.APPROVED
    access_request.save()
    return created, permission


def reject_access_request(
    access_request: QuotationAccessRequest,
    reviewer,
) -> None:
    """Reject a locked pending request."""
    if access_request.status != QuotationAccessRequestStatus.PENDING:
        raise ValidationError("Only pending requests can be rejected.")
    access_request.status = QuotationAccessRequestStatus.REJECTED
    access_request.reviewed_by = reviewer
    access_request.reviewed_at = timezone.now()
    access_request.save()


def close_access_request(
    access_request: QuotationAccessRequest,
    reviewer,
    action: str,
) -> None:
    """Revoke or expire a locked approved request and its permission."""
    if access_request.status != QuotationAccessRequestStatus.APPROVED:
        raise ValidationError(
            "Only approved requests can be revoked or expired."
        )
    now = timezone.now()
    permission = (
        access_request.upload_permission or access_request.view_permission
    )
    if permission and permission.is_active:
        permission.is_active = False
        update_fields = ["is_active", "updated_at"]
        if isinstance(permission, QuotationUploadPermission):
            permission.revoked_at = now
            update_fields.append("revoked_at")
        permission.save(update_fields=update_fields)
    access_request.reviewed_by = reviewer
    access_request.reviewed_at = now
    if action == "revoke":
        access_request.status = QuotationAccessRequestStatus.REVOKED
        access_request.revoked_at = now
    else:
        access_request.status = QuotationAccessRequestStatus.EXPIRED
        access_request.expired_at = now
    access_request.save()


def _active_view_permission(
    access_request: QuotationAccessRequest,
    expires_at,
) -> tuple[QuotationViewPermission, bool]:
    target_type = (
        QuotationViewPermissionTarget.DOCUMENT
        if access_request.request_type
        == QuotationAccessRequestType.DOCUMENT_VIEW
        else QuotationViewPermissionTarget.FOLDER
    )
    filters = {
        "user": access_request.applicant,
        "target_type": target_type,
        "is_active": True,
    }
    if target_type == QuotationViewPermissionTarget.DOCUMENT:
        filters["document"] = access_request.document
    else:
        filters["folder_token"] = access_request.folder_token
    permission = QuotationViewPermission.objects.filter(**filters).first()
    created = permission is None
    if permission is None:
        permission = QuotationViewPermission.objects.create(
            user=access_request.applicant,
            target_type=target_type,
            folder_token=(
                access_request.folder_token
                if target_type == QuotationViewPermissionTarget.FOLDER
                else ""
            ),
            folder_name=(
                access_request.folder_name
                if target_type == QuotationViewPermissionTarget.FOLDER
                else ""
            ),
            document=(
                access_request.document
                if target_type == QuotationViewPermissionTarget.DOCUMENT
                else None
            ),
            granted_by=access_request.reviewed_by,
            expires_at=expires_at,
        )
    else:
        permission.granted_by = access_request.reviewed_by
        permission.expires_at = expires_at
        permission.save(
            update_fields=["granted_by", "expires_at", "updated_at"]
        )
    return permission, created


def _active_upload_permission(
    access_request: QuotationAccessRequest,
    expires_at,
) -> tuple[QuotationUploadPermission, bool]:
    permission = QuotationUploadPermission.objects.filter(
        user=access_request.applicant,
        folder_token=access_request.folder_token,
        is_active=True,
    ).first()
    created = permission is None
    if permission is None:
        permission = QuotationUploadPermission.objects.create(
            user=access_request.applicant,
            folder_token=access_request.folder_token,
            folder_name=access_request.folder_name,
            granted_by=access_request.reviewed_by,
            expires_at=expires_at,
        )
    else:
        permission.folder_name = access_request.folder_name
        permission.granted_by = access_request.reviewed_by
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
    return permission, created
