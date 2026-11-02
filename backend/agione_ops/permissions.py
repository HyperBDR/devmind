"""Explicit action grants and connection scope without staff shortcuts."""

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import (
    NotAuthenticated,
    NotFound,
    PermissionDenied,
)

from agione_ops.models import ConnectionGrant, SourceConnection
from agione_ops.observability import measured

ACTIONS = frozenset({"manage_connections", "view_business", "run_sync"})


def has_action(user, codename):
    """Only direct/group Django permissions count, not superuser shortcuts."""

    if (
        codename not in ACTIONS
        or not user
        or not user.is_authenticated
        or not user.is_active
    ):
        return False
    lookup = {
        "content_type__app_label": "agione_ops",
        "content_type__model": "sourceconnection",
        "codename": codename,
    }
    return (
        user.user_permissions.filter(**lookup).exists()
        or user.groups.filter(
            permissions__content_type__app_label="agione_ops",
            permissions__content_type__model="sourceconnection",
            permissions__codename=codename,
        ).exists()
    )


def require_action(user, codename):
    """Enforce a top-level action without revealing connection existence."""

    if not user or not user.is_authenticated:
        raise NotAuthenticated("Authentication required.")
    if not has_action(user, codename):
        raise PermissionDenied("AGIOne action is not authorized.")


def connections_for(user, action="view_business"):
    """Return only explicitly authorized connection rows for an action."""

    require_action(user, action)
    queryset = SourceConnection.objects.all()
    if getattr(settings, "AGIONE_OPS_NATIVE_ONLY", False):
        queryset = queryset.filter(source_kind="native")
    if action == "manage_connections":
        return queryset
    flag = "can_view" if action == "view_business" else "can_sync"
    grants = ConnectionGrant.objects.filter(user=user, **{flag: True})
    return queryset.filter(enabled=True, pk__in=grants.values("connection_id"))


@measured("acl")
def get_connection_for(user, connection_id, action="view_business"):
    """Unknown objects and missing object grants share the same 404."""

    queryset = connections_for(user, action)
    try:
        connection = queryset.filter(pk=connection_id).first()
    except (ValidationError, ValueError, TypeError):
        connection = None
    if connection is None:
        raise NotFound("Connection not found.")
    return connection


def authorize_run(user, run, require_initiator=True):
    """Progress access requires sync authority and, by default, ownership."""

    connection = get_connection_for(user, run.connection_id, "run_sync")
    if require_initiator and run.initiated_by_id != user.pk:
        raise NotFound("Run not found.")
    return connection
