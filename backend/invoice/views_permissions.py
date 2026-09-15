from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.access import get_effective_feature_keys
from invoice.models import InvoiceAccessGrant, InvoiceAccessRole
from invoice.permissions import ROLE_CAPABILITIES
from quotation.audit import record_audit_event
from quotation.models import AuditEvent
from quotation.permissions import is_quotation_platform_admin
from quotation.services.permission_service import parse_expires_at


def _require_admin(user) -> None:
    """Require an administrator of the existing Quote Desk workspace."""
    has_quote_access = (
        "quotation_management" in get_effective_feature_keys(user)
    )
    if not has_quote_access or not is_quotation_platform_admin(user):
        raise PermissionDenied(
            "Only Quote Desk administrators can manage Invoice access."
        )


def _user_row(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "name": user.get_full_name() or user.username,
        "email": user.email or "",
    }


def _grant_status(grant: InvoiceAccessGrant) -> str:
    if not grant.is_active or grant.revoked_at is not None:
        return "revoked"
    if grant.expires_at and grant.expires_at <= timezone.now():
        return "expired"
    return "active"


def _grant_row(grant: InvoiceAccessGrant) -> dict:
    return {
        "id": grant.id,
        "user_id": grant.user_id,
        "user_name": grant.user.get_full_name() or grant.user.username,
        "username": grant.user.username,
        "email": grant.user.email or "",
        "role": grant.role,
        "capabilities": list(ROLE_CAPABILITIES[grant.role]),
        "expires_at": grant.expires_at,
        "status": _grant_status(grant),
        "created_at": grant.created_at,
        "updated_at": grant.updated_at,
        "granted_by": grant.granted_by.get_full_name()
        or grant.granted_by.username,
    }


def _record_grant_event(
    request,
    grant: InvoiceAccessGrant,
    *,
    action: str,
    before_expiry=None,
    before_role=None,
) -> None:
    event_names = {
        "grant_invoice": "permissions.invoice_access_granted",
        "update_invoice": "permissions.invoice_access_expiry_changed",
        "update_invoice_role": (
            "permissions.invoice_access_role_changed"
        ),
        "revoke_invoice": "permissions.invoice_access_revoked",
    }
    record_audit_event(
        request=request,
        module="permissions",
        action=action,
        result=AuditEvent.RESULT_SUCCEEDED,
        target_type="invoice_access_grant",
        target_id=str(grant.id),
        target_label=grant.user.get_full_name() or grant.user.username,
        event_name=event_names[action],
        summary="Updated Invoice workspace access.",
        before_summary={
            "expires_at": (
                before_expiry.isoformat() if before_expiry else None
            ),
            "role": before_role,
        },
        after_summary={
            "user_id": grant.user_id,
            "expires_at": (
                grant.expires_at.isoformat() if grant.expires_at else None
            ),
            "status": _grant_status(grant),
            "role": grant.role,
        },
    )


def _parse_role(value, *, default=None) -> str:
    role = value if value is not None else default
    if role not in InvoiceAccessRole.values:
        raise ValidationError({"role": "Select a valid Invoice role."})
    return role


class InvoiceAccessGrantView(APIView):
    """List and grant Invoice access from Quote Desk authorization."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_admin(request.user)
        users = User.objects.filter(
            is_active=True,
            is_staff=False,
            is_superuser=False,
        ).order_by("username", "id")
        grants = (
            InvoiceAccessGrant.objects.filter(is_active=True)
            .select_related("user", "granted_by")
            .order_by("user__username", "id")
        )
        return Response(
            {
                "users": [_user_row(user) for user in users],
                "permissions": [_grant_row(grant) for grant in grants],
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
        user = User.objects.filter(
            pk=user_id,
            is_active=True,
            is_staff=False,
            is_superuser=False,
        ).first()
        if user is None:
            raise ValidationError({"user_id": "User not found."})
        expires_at = parse_expires_at(request.data.get("expires_at"))
        role = _parse_role(
            request.data.get("role"),
            default=InvoiceAccessRole.ADMIN,
        )
        grant = InvoiceAccessGrant.objects.filter(
            user=user,
            is_active=True,
        ).first()
        created = grant is None
        before_expiry = grant.expires_at if grant else None
        before_role = grant.role if grant else None
        if grant is None:
            grant = InvoiceAccessGrant.objects.create(
                user=user,
                granted_by=request.user,
                expires_at=expires_at,
                role=role,
            )
        else:
            grant.granted_by = request.user
            grant.expires_at = expires_at
            grant.role = role
            grant.revoked_at = None
            grant.save(
                update_fields=[
                    "granted_by",
                    "expires_at",
                    "role",
                    "revoked_at",
                    "updated_at",
                ]
            )
        _record_grant_event(
            request,
            grant,
            action="grant_invoice",
            before_expiry=before_expiry,
            before_role=before_role,
        )
        return Response(_grant_row(grant), status=201 if created else 200)


class InvoiceAccessGrantDetailView(APIView):
    """Update or revoke one Invoice access grant."""

    permission_classes = [IsAuthenticated]

    def _grant(self, permission_id: int) -> InvoiceAccessGrant:
        grant = InvoiceAccessGrant.objects.filter(
            pk=permission_id,
            is_active=True,
        ).select_related("user", "granted_by").first()
        if grant is None:
            raise ValidationError("Invoice access permission not found.")
        return grant

    def patch(self, request, permission_id: int):
        _require_admin(request.user)
        grant = self._grant(permission_id)
        if not {"expires_at", "role"}.intersection(request.data):
            raise ValidationError(
                "An expiration or Invoice role is required for this update."
            )
        before_expiry = grant.expires_at
        before_role = grant.role
        update_fields = ["granted_by", "updated_at"]
        if "expires_at" in request.data:
            grant.expires_at = parse_expires_at(
                request.data.get("expires_at")
            )
            update_fields.append("expires_at")
        if "role" in request.data:
            grant.role = _parse_role(request.data.get("role"))
            update_fields.append("role")
        grant.granted_by = request.user
        grant.save(update_fields=update_fields)
        action = (
            "update_invoice_role"
            if grant.role != before_role
            else "update_invoice"
        )
        _record_grant_event(
            request,
            grant,
            action=action,
            before_expiry=before_expiry,
            before_role=before_role,
        )
        return Response(_grant_row(grant))

    def delete(self, request, permission_id: int):
        _require_admin(request.user)
        grant = self._grant(permission_id)
        grant.is_active = False
        grant.revoked_at = timezone.now()
        grant.save(
            update_fields=["is_active", "revoked_at", "updated_at"]
        )
        _record_grant_event(
            request,
            grant,
            action="revoke_invoice",
            before_expiry=grant.expires_at,
        )
        return Response(status=204)
