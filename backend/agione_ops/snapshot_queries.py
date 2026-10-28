"""One authenticated entry point for local immutable query projections."""

from uuid import UUID

from rest_framework.exceptions import NotFound

from agione_ops.client import AgioneOpsError
from agione_ops.observability import set_fields
from agione_ops.permissions import get_connection_for
from agione_ops.query_cache import cached_operation


def query_operation(connection, user, query):
    """Never use a shared projection without current connection authority."""
    connection = get_connection_for(user, connection.pk, "view_business")
    if connection.source_kind == "native":
        from agione_ops.native_snapshot_queries import (
            query_native_snapshot,
            validate_native_snapshot,
        )

        compute = query_native_snapshot
        validate = validate_native_snapshot
    else:
        raise AgioneOpsError("SOURCE_KIND_FORBIDDEN", status_code=403)
    return cached_operation(connection, user, query, compute, validate)


def dashboard_frame(connection, user, version_id=None):
    """Return overview and the complete DTO so focus needs one business read."""
    connection = get_connection_for(user, connection.pk, "view_business")
    if connection.source_kind == "native" and version_id is None:
        from agione_ops.native_sync_models import NativePublishedSnapshot

        published = NativePublishedSnapshot.objects.filter(
            version__connection=connection, version__run__status="succeeded"
        ).order_by("-version__published_at").values_list(
            "version_id", flat=True
        ).first()
        if published is None:
            from agione_ops.native_snapshot_queries import query_native_snapshot

            response = query_native_snapshot(
                connection, user, {"operation": "dashboard", "payload": {}}
            )
            return {
                **response.get("overview", {}),
                "state": "not_collected", "dataVersion": None,
                "summary": None, "provenance": response.get("provenance"),
                "capabilities": response.get("capabilities", {}),
            }
        version_id = published
    try:
        version = UUID(str(version_id))
    except (ValueError, TypeError, AttributeError):
        raise NotFound("Snapshot not found.") from None
    response = query_operation(connection, user, {
        "operation": "dashboard", "data_version": version, "payload": {},
    })
    set_fields(operation="dashboard", data_version=version)
    return {
        **response["overview"],
        "state": "ready",
        "window": response.get("window"),
        "coverage": response.get("coverage"),
        "provenance": response.get("provenance", {}),
        "snapshotResponse": response,
        "capabilities": response.get("capabilities", {}),
        "publishedAt": (
            response.get("provenance", {}).get("publishedAt")
            or response.get("provenance", {}).get("collectedAt")
        ),
    }
