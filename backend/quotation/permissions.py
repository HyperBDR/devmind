from django.contrib.auth.models import User
from rest_framework.permissions import BasePermission

from accounts.access import (
    get_effective_feature_keys,
    get_effective_roles,
)
from quotation.models import (
    QuotationMembership,
    QuotationMembershipRole,
)


def ensure_default_quotation_membership(user: User) -> None:
    """Create the default quotation role for an eligible first-time user."""
    if not getattr(user, "is_authenticated", False):
        return
    if getattr(user, "is_staff", False) or getattr(
        user,
        "is_superuser",
        False,
    ):
        return
    if "quotation_management" not in get_effective_feature_keys(user):
        return
    if QuotationMembership.objects.filter(user=user).exists():
        return
    QuotationMembership.objects.create(
        user=user,
        role=QuotationMembershipRole.USER,
    )


class HasQuotationPlatformAccess(BasePermission):
    """Require the first-layer Quote Desk platform permission."""

    message = "Quotation platform access is required."

    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, "is_authenticated", False):
            return False
        allowed = "quotation_management" in get_effective_feature_keys(user)
        if allowed:
            ensure_default_quotation_membership(user)
        return allowed


def is_quotation_platform_admin(user: User) -> bool:
    """Return whether a user is an admin of the quotation platform."""
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False) or getattr(
        user,
        "is_superuser",
        False,
    ):
        return True
    return QuotationMembership.objects.filter(
        user=user,
        role=QuotationMembershipRole.ADMIN,
        is_active=True,
    ).exists()


def get_quotation_platform_role(user: User) -> str | None:
    """Return the user's internal quotation role.

    Users who already have the first-layer quotation platform feature are
    ordinary quotation users until an administrator assigns the admin role.
    This keeps first-time setup from creating an account with no quotation
    role while still leaving users without the first-layer feature untouched.
    """
    if not getattr(user, "is_authenticated", False):
        return None
    if getattr(user, "is_staff", False) or getattr(
        user,
        "is_superuser",
        False,
    ):
        return QuotationMembershipRole.ADMIN
    membership = QuotationMembership.objects.filter(
        user=user,
        is_active=True,
    ).only("role").first()
    if membership:
        return membership.role
    if QuotationMembership.objects.filter(user=user).exists():
        return None
    ensure_default_quotation_membership(user)
    return QuotationMembershipRole.USER


def is_quotation_platform_user(user: User) -> bool:
    """Return whether a user has an internal quotation role."""
    return get_quotation_platform_role(user) is not None


def is_quotation_admin(user: User) -> bool:
    """Return whether a user has an explicit administrative identity."""
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False) or getattr(
        user,
        "is_superuser",
        False,
    ):
        return True
    profile = getattr(user, "profile", None)
    if str(getattr(profile, "role", "") or "").lower() == "admin":
        return True
    role_names = {
        role.name.strip().lower().replace(" ", "_")
        for role in get_effective_roles(user)
    }
    return "admin" in role_names


def user_role(user: User) -> str:
    if getattr(user, "is_superuser", False) or getattr(
        user, "is_staff", False
    ):
        return "admin"

    profile = getattr(user, "profile", None)
    legacy_role = getattr(profile, "role", "")
    if legacy_role:
        return str(legacy_role).lower()

    role_names = {
        role.name.strip().lower().replace(" ", "_")
        for role in get_effective_roles(user)
    }
    for role in ("admin", "sales_director", "presales", "sales"):
        if role in role_names:
            return role

    feature_keys = set(get_effective_feature_keys(user))
    if "admin_console" in feature_keys:
        return "admin"
    if "sales_work_orders" in feature_keys:
        return "sales_director"
    return "sales"


def can_view_all_quotations(user: User) -> bool:
    """Return whether legacy document access grants a global view."""
    if getattr(user, "is_superuser", False) or getattr(
        user, "is_staff", False
    ):
        return True
    profile = getattr(user, "profile", None)
    legacy_role = str(getattr(profile, "role", "") or "").lower()
    if legacy_role in {"admin", "sales_director", "presales"}:
        return True
    role_names = {
        role.name.strip().lower().replace(" ", "_")
        for role in get_effective_roles(user)
    }
    return bool(role_names & {"admin", "sales_director", "presales"})


def can_delete_any_quotation_document(user: User) -> bool:
    if getattr(user, "is_superuser", False) or getattr(
        user, "is_staff", False
    ):
        return True
    profile = getattr(user, "profile", None)
    legacy_role = str(getattr(profile, "role", "") or "").lower()
    if legacy_role in {"admin", "sales_director"}:
        return True
    role_names = {
        role.name.strip().lower().replace(" ", "_")
        for role in get_effective_roles(user)
    }
    return bool(role_names & {"admin", "sales_director"})


def user_display_email(user: User) -> str:
    return (user.email or user.username or "").lower()
