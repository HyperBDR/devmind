"""Permissions for the Data Ops app."""

from rest_framework.permissions import BasePermission

from accounts.access import get_effective_feature_keys


class HasDataOpsAdminAccess(BasePermission):
    """Allow Data Ops role holders to manage the app."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        feature_keys = set(get_effective_feature_keys(user))
        return "data_ops" in feature_keys
