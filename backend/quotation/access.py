from __future__ import annotations

from django.db.models import Q, QuerySet
from rest_framework import status
from rest_framework.response import Response

from quotation.models import DocumentAsset, Quotation
from quotation.permissions import (
    can_delete_any_quotation_document,
    can_view_all_quotations,
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


def forbidden_response() -> Response:
    return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)


def can_access_quotation(
    user,
    quotation: Quotation | None,
    action: str = DocumentAction.VIEW,
) -> bool:
    if quotation is None:
        return False
    if can_view_all_quotations(user):
        return True
    owner = (quotation.created_by_email or "").lower()
    return bool(owner and owner == user_display_email(user))


def filter_accessible_quotations(
    user,
    qs: QuerySet[Quotation],
    action: str = DocumentAction.VIEW,
):
    if can_view_all_quotations(user):
        return qs
    return qs.filter(created_by_email__iexact=user_display_email(user))


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
    return qs.filter(
        Q(created_by_email__iexact=email)
        | Q(quotation__created_by_email__iexact=email)
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
    asset = DocumentAsset.objects.select_related("quotation").filter(
        pk=document_id
    ).first()
    if asset is None:
        return None, Response({"detail": "document not found"}, status=404)
    if not can_access_document(user, asset, action):
        return None, forbidden_response()
    return asset, None


def can_delete_document(user, asset: DocumentAsset | None) -> bool:
    if not can_access_document(user, asset, DocumentAction.DELETE):
        return False
    owner = (asset.created_by_email or "").lower()
    if owner and owner == user_display_email(user):
        return True
    return can_delete_any_quotation_document(user)
