from django.contrib.auth.models import User

from accounts.access import get_effective_feature_keys, get_effective_roles


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
    return user_role(user) in {"admin", "sales_director", "presales"}


def user_display_email(user: User) -> str:
    return (user.email or user.username or "").lower()
