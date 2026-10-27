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


def dashboard_frame(
    connection, user, version_id=None, window_start=None, window_end=None,
):
    """Return overview and the complete DTO so focus needs one business read."""
    connection = get_connection_for(user, connection.pk, "view_business")
    composite = False
    if connection.source_kind == "native" and version_id is None:
        from agione_ops.native_sync_models import NativePublishedSnapshot

        snapshots = NativePublishedSnapshot.objects.filter(
            version__connection=connection, version__run__status="succeeded",
            version__run__config_version=connection.config_version,
            version__run__credential_version=connection.credential_version,
        )
        if window_start is not None and window_end is not None:
            snapshots = snapshots.filter(
                version__window_start__lte=window_start,
                version__window_end__gte=window_end,
            )
        published = snapshots.order_by("-version__published_at").values_list(
            "version_id", flat=True
        ).first()
        if published is None and window_start is not None and window_end is not None:
            published = NativePublishedSnapshot.objects.filter(
                version__connection=connection,
                version__run__status="succeeded",
                version__run__config_version=connection.config_version,
                version__run__credential_version=connection.credential_version,
                version__window_start__lt=window_end,
                version__window_end__gt=window_start,
            ).order_by("-version__published_at", "-version_id").values_list(
                "version_id", flat=True,
            ).first()
            composite = published is not None
        if published is None:
            if window_start is not None:
                return {
                    "state": "not_collected", "dataVersion": None,
                    "summary": None, "window": None,
                    "provenance": {"kind": "native_snapshot"},
                    "capabilities": {},
                }
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
    query = {"operation": "dashboard", "data_version": version, "payload": {}}
    if composite:
        query["window"] = {"start": window_start, "end_exclusive": window_end,
                           "timezone": "Asia/Shanghai"}
    try:
        response = query_operation(connection, user, query)
    except AgioneOpsError as error:
        if error.code != "SNAPSHOT_WINDOW_NOT_COLLECTED":
            raise
        return {"state": "not_collected", "dataVersion": None,
                "summary": None, "window": None,
                "provenance": {"kind": "native_snapshot"}, "capabilities": {}}
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
