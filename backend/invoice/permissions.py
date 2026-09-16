from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import BasePermission

from invoice.models import (
    InvoiceAccessGrant,
    InvoiceAccessRole,
    InvoiceDocument,
)
from quotation.models import (
    QuotationViewPermission,
    QuotationViewPermissionTarget,
)


class InvoiceCapability:
    VIEW = "view"
    EDIT = "edit"
    IMPORT = "import"
    ISSUE = "issue"


ROLE_CAPABILITIES = {
    InvoiceAccessRole.USER: (
        InvoiceCapability.VIEW,
        InvoiceCapability.EDIT,
        InvoiceCapability.IMPORT,
        InvoiceCapability.ISSUE,
    ),
    InvoiceAccessRole.ADMIN: (
        InvoiceCapability.VIEW,
        InvoiceCapability.EDIT,
        InvoiceCapability.IMPORT,
        InvoiceCapability.ISSUE,
    ),
}


def _is_automatic_invoice_manager(user) -> bool:
    """Return whether the global admin role implies full Invoice access."""
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False) or getattr(
        user,
        "is_superuser",
        False,
    ):
        return True
    from accounts.access import get_effective_roles, normalize_feature_keys

    if any(
        "admin_console" in normalize_feature_keys(role.visible_features)
        for role in get_effective_roles(user)
    ):
        return True
    return False


def _active_grant(user):
    """Return the user's active, unexpired Invoice grant when present."""
    if not getattr(user, "is_authenticated", False):
        return None
    return (
        InvoiceAccessGrant.objects.filter(
            user=user,
            is_active=True,
            revoked_at__isnull=True,
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
        .first()
    )


def get_invoice_access_role(user) -> str | None:
    """Return the effective Invoice role for a user."""
    if _is_automatic_invoice_manager(user):
        return InvoiceAccessRole.ADMIN
    grant = _active_grant(user)
    return grant.role if grant else None


def get_invoice_capabilities(user) -> list[str]:
    """Return ordered Invoice capabilities for the effective role."""
    role = get_invoice_access_role(user)
    return list(ROLE_CAPABILITIES.get(role, ()))


def get_invoice_access_profile(user) -> dict[str, object]:
    """Serialize the Invoice gate, role, and effective capabilities."""
    role = get_invoice_access_role(user)
    return {
        "enabled": role is not None,
        "role": role,
        "capabilities": list(ROLE_CAPABILITIES.get(role, ())),
    }


def has_invoice_access(user) -> bool:
    """Return whether a user may use the Sales and Invoice workspace."""
    return get_invoice_access_role(user) is not None


def has_invoice_capability(user, capability: str) -> bool:
    """Return whether a user has one effective Invoice capability."""
    return capability in get_invoice_capabilities(user)


def has_invoice_upload_access(user, folder_token: str) -> bool:
    """Return whether the user may upload an Invoice to one Feishu folder."""
    if get_invoice_access_role(user) == InvoiceAccessRole.ADMIN:
        return True
    from quotation.access import can_upload_to_folder

    return can_upload_to_folder(user, folder_token)


def _granted_invoice_document_ids(user):
    """Return Invoice IDs covered by active Feishu view grants."""
    now = timezone.now()
    permissions = QuotationViewPermission.objects.filter(
        user=user,
        is_active=True,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    folder_tokens = permissions.filter(
        target_type=QuotationViewPermissionTarget.FOLDER,
    ).values_list("folder_token", flat=True)
    file_tokens = permissions.filter(
        target_type=QuotationViewPermissionTarget.DOCUMENT,
        document__feishu_file_token__gt="",
    ).values_list("document__feishu_file_token", flat=True)
    invoice_document_ids = permissions.filter(
        target_type=QuotationViewPermissionTarget.DOCUMENT,
        folder_token__startswith="invoice-document:",
    ).values_list("folder_token", flat=True)
    invoice_document_ids = [
        value.removeprefix("invoice-document:")
        for value in invoice_document_ids
        if value
    ]
    return InvoiceDocument.objects.filter(
        invoice__isnull=False,
    ).filter(
        Q(feishu_folder_token__in=folder_tokens)
        | Q(feishu_file_token__in=file_tokens)
        | Q(id__in=invoice_document_ids)
    ).values_list("invoice_id", flat=True)


def invoice_visibility_filter(user) -> Q:
    """Return the invoice rows visible to a user by their Invoice role."""
    if get_invoice_access_role(user) == InvoiceAccessRole.ADMIN:
        return Q()
    names = {
        str(getattr(user, "username", "") or "").strip(),
        str(getattr(user, "email", "") or "").strip(),
        str(getattr(user, "get_full_name", lambda: "")() or "").strip(),
        str(
            getattr(getattr(user, "profile", None), "display_name", "")
            or ""
        ).strip(),
    }
    names.discard("")
    owner_filter = Q()
    for name in names:
        owner_filter |= Q(sales_owner__iexact=name)
    return (
        Q(created_by=user)
        | owner_filter
        | Q(id__in=_granted_invoice_document_ids(user))
    )


class HasInvoiceAccess(BasePermission):
    """Require an active Invoice grant or a global administrator."""

    message = "Invoice workspace access is required."

    def has_permission(self, request, view):
        return has_invoice_access(request.user)


class HasInvoiceEditAccess(BasePermission):
    """Require permission to edit Invoice drafts."""

    message = "Invoice edit permission is required."

    def has_permission(self, request, view):
        return has_invoice_capability(
            request.user,
            InvoiceCapability.EDIT,
        )


class HasInvoiceImportAccess(BasePermission):
    """Require permission to upload and parse Invoice documents."""

    message = "Invoice import permission is required."

    def has_permission(self, request, view):
        return has_invoice_capability(
            request.user,
            InvoiceCapability.IMPORT,
        )


class HasInvoiceIssueAccess(BasePermission):
    """Require permission to issue or confirm an Invoice."""

    message = "Invoice issue permission is required."

    def has_permission(self, request, view):
        return has_invoice_capability(
            request.user,
            InvoiceCapability.ISSUE,
        )
