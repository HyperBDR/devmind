from __future__ import annotations

from django.db.models import Q, QuerySet
from django.db.models.functions import Lower, Trim
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from quotation.models import (
    DocumentAsset,
    DocumentLifecycleState,
    Quotation,
    QuotationSourceType,
    QuotationUploadPermission,
    QuotationViewPermission,
    QuotationViewPermissionTarget,
)
from quotation.permissions import (
    can_delete_any_quotation_document,
    can_view_all_quotations,
    is_quotation_platform_admin,
    user_display_email,
)


class DocumentAction:
    """Supported quotation document authorization actions."""

    VIEW = "view"
    DOWNLOAD = "download"
    UPLOAD = "upload"
    IMPORT = "import"
    DELETE = "delete"
    SHARE = "share"
    CHECK_REMOTE = "check_remote"
    PARSE = "parse"


class UploadAuthorizationError(ValueError):
    """Raised when a queued upload no longer has directory access."""


def forbidden_response() -> Response:
    return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)


def upload_forbidden_response() -> Response:
    """Return the stable response for a denied directory upload."""
    return Response(
        {"detail": "Upload access to this directory is required."},
        status=status.HTTP_403_FORBIDDEN,
    )


def active_upload_permissions(user):
    """Return active, unexpired directory upload grants for one user."""
    if not getattr(user, "is_authenticated", False):
        return QuotationUploadPermission.objects.none()
    now = timezone.now()
    return QuotationUploadPermission.objects.filter(
        user=user,
        is_active=True,
        revoked_at__isnull=True,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))


def can_upload_to_folder(user, folder_token: str) -> bool:
    """Return whether a user may upload to this exact directory."""
    token = str(folder_token or "").strip()
    if not token or not getattr(user, "is_authenticated", False):
        return False
    if is_quotation_platform_admin(user):
        return True
    return (
        active_upload_permissions(user)
        .filter(
            folder_token=token,
        )
        .exists()
    )


def _normalized_owner(value) -> str:
    """Normalize a Sales Owner or username for an exact comparison."""
    return str(value or "").strip().casefold()


def _feishu_folder_name(asset: DocumentAsset) -> str:
    """Return the name of the folder containing a parsed Feishu file."""
    folder_path = asset.feishu_folder_path
    if not isinstance(folder_path, list) or not folder_path:
        return ""
    last_folder = folder_path[-1]
    if isinstance(last_folder, dict):
        return str(last_folder.get("name") or "")
    return str(last_folder or "")


def _folder_owned_quotation_ids(user) -> set[str]:
    """Return imported quote IDs whose fallback folder matches the user."""
    username = _normalized_owner(getattr(user, "username", ""))
    if not username:
        return set()
    assets = DocumentAsset.objects.filter(
        source="feishu",
        quotation__isnull=False,
        quotation__issuer_contact_name="",
    ).only("quotation_id", "feishu_folder_path")
    return {
        asset.quotation_id
        for asset in assets
        if _normalized_owner(_feishu_folder_name(asset)) == username
    }


def _active_view_permissions(user):
    """Return active administrator-granted view permissions for a user."""
    now = timezone.now()
    return QuotationViewPermission.objects.filter(
        user=user,
        is_active=True,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))


def _granted_quotation_ids(user) -> set[str]:
    """Return quotations reachable through explicit view grants."""
    permissions = list(
        _active_view_permissions(user).only(
            "target_type",
            "folder_token",
            "document_id",
        )
    )
    if not permissions:
        return set()
    document_ids = {
        permission.document_id
        for permission in permissions
        if permission.target_type == QuotationViewPermissionTarget.DOCUMENT
        and permission.document_id
    }
    folder_tokens = {
        permission.folder_token
        for permission in permissions
        if permission.target_type == QuotationViewPermissionTarget.FOLDER
        and permission.folder_token
    }
    granted_ids = set(
        DocumentAsset.objects.filter(
            id__in=document_ids,
            quotation__isnull=False,
        ).values_list("quotation_id", flat=True)
    )
    for asset in DocumentAsset.objects.filter(
        source="feishu",
        quotation__isnull=False,
    ).only("quotation_id", "feishu_folder_token", "feishu_folder_path"):
        path_tokens = {
            str(item.get("token") or "")
            for item in asset.feishu_folder_path or []
            if isinstance(item, dict)
        }
        path_tokens.add(str(asset.feishu_folder_token or ""))
        if path_tokens & folder_tokens:
            granted_ids.add(asset.quotation_id)
    return granted_ids


def _granted_document_ids(user) -> set[str]:
    """Return document IDs reachable through explicit view grants."""
    permissions = list(
        _active_view_permissions(user).only(
            "target_type",
            "folder_token",
            "document_id",
        )
    )
    if not permissions:
        return set()
    ids = set(
        permission.document_id
        for permission in permissions
        if permission.target_type == QuotationViewPermissionTarget.DOCUMENT
        and permission.document_id
    )
    folder_tokens = {
        permission.folder_token
        for permission in permissions
        if permission.target_type == QuotationViewPermissionTarget.FOLDER
        and permission.folder_token
    }
    for asset in DocumentAsset.objects.filter(
        source="feishu",
    ).only("id", "feishu_folder_token", "feishu_folder_path"):
        path_tokens = {
            str(item.get("token") or "")
            for item in asset.feishu_folder_path or []
            if isinstance(item, dict)
        }
        path_tokens.add(str(asset.feishu_folder_token or ""))
        if path_tokens & folder_tokens:
            ids.add(asset.id)
    return ids


def _quotation_matches_user(user, quotation: Quotation) -> bool:
    """Return whether a non-admin user may access one quotation."""
    username = _normalized_owner(getattr(user, "username", ""))
    sales_owner = _normalized_owner(quotation.issuer_contact_name)
    if quotation.source_type == QuotationSourceType.DOCUMENT_IMPORT:
        if _normalized_owner(quotation.created_by_email) == _normalized_owner(
            user_display_email(user)
        ):
            return True
        if sales_owner:
            return sales_owner == username
        return any(
            _normalized_owner(_feishu_folder_name(asset)) == username
            for asset in quotation.documents.filter(source="feishu")
        )
    return _normalized_owner(quotation.created_by_email) == _normalized_owner(
        user_display_email(user)
    )


def can_access_quotation(
    user,
    quotation: Quotation | None,
    action: str = DocumentAction.VIEW,
) -> bool:
    if quotation is None or quotation.archived_at is not None:
        return False
    if is_quotation_platform_admin(user):
        return True
    if quotation.pk in _granted_quotation_ids(user):
        return True
    return _quotation_matches_user(user, quotation)


def filter_accessible_quotations(
    user,
    qs: QuerySet[Quotation],
    action: str = DocumentAction.VIEW,
):
    qs = qs.filter(archived_at__isnull=True)
    if is_quotation_platform_admin(user):
        return qs
    username = _normalized_owner(getattr(user, "username", ""))
    email = _normalized_owner(user_display_email(user))
    folder_ids = _folder_owned_quotation_ids(user)
    owner_filter = Lower(Trim("issuer_contact_name"))
    creator_filter = Lower(Trim("created_by_email"))
    granted_ids = _granted_quotation_ids(user)
    return (
        qs.annotate(
            normalized_sales_owner=owner_filter,
            normalized_creator=creator_filter,
        )
        .filter(
            Q(normalized_sales_owner=username)
            | Q(id__in=folder_ids)
            | Q(id__in=granted_ids)
            | Q(documents__created_by_email__iexact=email)
            | Q(
                source_type=QuotationSourceType.MANUAL,
                normalized_creator=email,
            )
        )
        .distinct()
    )


def get_accessible_quotation(
    user,
    quotation_id: str | None,
    action: str = DocumentAction.VIEW,
):
    if not quotation_id:
        return None, None
    quotation = Quotation.objects.filter(pk=quotation_id).first()
    if quotation is None:
        return None, Response({"detail": "quotation not found"}, status=404)
    if not can_access_quotation(user, quotation, action):
        if can_view_all_quotations(user) and action in {
            DocumentAction.VIEW,
            DocumentAction.UPLOAD,
        }:
            return quotation, None
        return None, forbidden_response()
    return quotation, None


def filter_accessible_documents(
    user,
    qs: QuerySet[DocumentAsset],
    action: str = DocumentAction.VIEW,
):
    if can_view_all_quotations(user):
        return qs
    email = user_display_email(user)
    quotation_ids = filter_accessible_quotations(
        user,
        Quotation.objects.all(),
    ).values("id")
    granted_document_ids = _granted_document_ids(user)
    return qs.filter(
        Q(id__in=granted_document_ids)
        | Q(quotation_id__in=quotation_ids)
        | Q(created_by_email__iexact=email)
    )


def can_access_document(
    user,
    asset: DocumentAsset | None,
    action: str = DocumentAction.VIEW,
) -> bool:
    if asset is None:
        return False
    return filter_accessible_documents(
        user, DocumentAsset.objects.filter(pk=asset.pk), action
    ).exists()


def get_accessible_document(
    user,
    document_id: str | None,
    action: str = DocumentAction.VIEW,
):
    if not document_id:
        return None, None
    asset = (
        DocumentAsset.objects.select_related("quotation")
        .filter(pk=document_id)
        .first()
    )
    if asset is None:
        return None, Response({"detail": "document not found"}, status=404)
    if not can_access_document(user, asset, action):
        return None, forbidden_response()
    if (
        asset.lifecycle_state == DocumentLifecycleState.ARCHIVED
        and action not in {DocumentAction.VIEW, DocumentAction.DELETE}
    ):
        return None, Response(
            {"detail": "document is archived"},
            status=status.HTTP_409_CONFLICT,
        )
    return asset, None


def can_delete_document(user, asset: DocumentAsset | None) -> bool:
    if not can_access_document(user, asset, DocumentAction.DELETE):
        return False
    owner = (asset.created_by_email or "").lower()
    if owner and owner == user_display_email(user):
        return True
    return can_delete_any_quotation_document(user)
