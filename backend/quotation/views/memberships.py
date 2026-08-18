from __future__ import annotations

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.access import get_effective_feature_keys
from quotation.audit import record_audit_event
from quotation.models import (
    AuditEvent,
    QuotationMembership,
    QuotationMembershipRole,
)
from quotation.permissions import is_quotation_platform_admin


def _require_admin(user) -> None:
    """Require a Quote Desk administrator for membership changes."""
    has_platform_access = (
        "quotation_management" in get_effective_feature_keys(user)
    )
    if not has_platform_access or not is_quotation_platform_admin(user):
        raise PermissionDenied(
            "Only quotation platform administrators can manage members."
        )


def _validate_role(value) -> str:
    """Return one supported Quote Desk role."""
    role = str(value or "").strip()
    if role not in QuotationMembershipRole.values:
        raise ValidationError({"role": "Unsupported quotation role."})
    return role


def _has_first_layer_access(user: User) -> bool:
    """Return whether a user may be managed as a Quote Desk member."""
    if not user.is_active or user.is_staff or user.is_superuser:
        return False
    return "quotation_management" in get_effective_feature_keys(user)


def _managed_user(user_id) -> User:
    """Load an eligible first-layer Quote Desk user."""
    try:
        parsed_user_id = int(user_id)
    except (TypeError, ValueError) as error:
        raise ValidationError(
            {"user_id": "A valid user is required."}
        ) from error
    user = User.objects.filter(pk=parsed_user_id).first()
    if user is None or not _has_first_layer_access(user):
        raise ValidationError(
            {
                "user_id": (
                    "User must have first-layer Quote Desk access."
                )
            }
        )
    return user


def _membership_row(
    user: User,
    membership: QuotationMembership | None,
) -> dict:
    """Serialize an eligible user and their current Quote Desk role."""
    assigned_by = membership.assigned_by if membership else None
    assigned_by_name = None
    if assigned_by:
        assigned_by_name = (
            assigned_by.get_full_name() or assigned_by.username
        )
    return {
        "id": membership.id if membership else None,
        "user_id": user.id,
        "username": user.username,
        "name": user.get_full_name() or user.username,
        "email": user.email or "",
        "role": membership.role if membership else None,
        "assigned_by": assigned_by_name,
        "created_at": membership.created_at if membership else None,
        "updated_at": membership.updated_at if membership else None,
    }


def _record_role_event(
    request,
    membership: QuotationMembership,
    *,
    action: str,
    before_role: str | None,
) -> None:
    """Write one actor-attributed role lifecycle audit event."""
    record_audit_event(
        request=request,
        module="permissions",
        action=action,
        result=AuditEvent.RESULT_SUCCEEDED,
        target_type="quotation_membership",
        target_id=str(membership.id),
        target_label=membership.user.get_full_name()
        or membership.user.username,
        summary="Updated Quote Desk membership role.",
        before_summary={"role": before_role},
        after_summary={"role": membership.role},
    )


class QuotationMembershipView(APIView):
    """List and assign roles for first-layer Quote Desk users."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_admin(request.user)
        users = User.objects.filter(
            is_active=True,
            is_staff=False,
            is_superuser=False,
        ).order_by("username", "id")
        memberships = {
            membership.user_id: membership
            for membership in QuotationMembership.objects.filter(
                is_active=True,
            ).select_related("assigned_by")
        }
        rows = [
            _membership_row(user, memberships.get(user.id))
            for user in users
            if _has_first_layer_access(user)
        ]
        return Response(
            {
                "members": rows,
                "role_options": [
                    {"value": value, "label": label}
                    for value, label in QuotationMembershipRole.choices
                ],
            }
        )

    def post(self, request):
        _require_admin(request.user)
        user = _managed_user(request.data.get("user_id"))
        role = _validate_role(request.data.get("role"))
        if QuotationMembership.objects.filter(
            user=user,
            is_active=True,
        ).exists():
            raise ValidationError(
                {"user_id": "User already has an active quotation role."}
            )
        try:
            with transaction.atomic():
                membership = QuotationMembership.objects.create(
                    user=user,
                    role=role,
                    assigned_by=request.user,
                )
        except IntegrityError as error:
            raise ValidationError(
                {"user_id": "User already has an active quotation role."}
            ) from error
        _record_role_event(
            request,
            membership,
            action="assign_role",
            before_role=None,
        )
        return Response(
            _membership_row(user, membership),
            status=201,
        )


class QuotationMembershipDetailView(APIView):
    """Change one active Quote Desk membership role."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, membership_id: int):
        _require_admin(request.user)
        membership = QuotationMembership.objects.filter(
            pk=membership_id,
            is_active=True,
        ).select_related("user", "assigned_by").first()
        if membership is None:
            raise ValidationError("Quotation membership not found.")
        if not _has_first_layer_access(membership.user):
            raise ValidationError(
                "User no longer has first-layer Quote Desk access."
            )
        role = _validate_role(request.data.get("role"))
        if role == membership.role:
            raise ValidationError({"role": "User already has this role."})
        before_role = membership.role
        membership.role = role
        membership.assigned_by = request.user
        membership.save(
            update_fields=["role", "assigned_by", "updated_at"]
        )
        _record_role_event(
            request,
            membership,
            action="change_role",
            before_role=before_role,
        )
        return Response(_membership_row(membership.user, membership))
