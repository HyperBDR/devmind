"""Read-only basic business queries over one published immutable version."""

from collections import defaultdict
from datetime import timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from rest_framework.exceptions import NotFound

from agione_ops.client import AgioneOpsError
from agione_ops.models import DatasetVersion, VersionCall
from agione_ops.permissions import get_connection_for


def _summary(rows):
    """Keep unknown states in the rate denominator and token gaps explicit."""

    count = len(rows)
    success = sum(row.status == "success" for row in rows)
    failure = sum(row.status == "failure" for row in rows)
    result = {
        "requests": count,
        "success": success,
        "failure": failure,
        "unknown": count - success - failure,
        "successRate": 100 * success / count if count else None,
        "rateUnit": "percent",
        "activeCustomers": len({row.customer_id for row in rows}),
        "activeModels": len({row.model_id for row in rows}),
    }
    for name, field in (
        ("inputTokens", "input_tokens"),
        ("outputTokens", "output_tokens"),
    ):
        values = [getattr(row, field) for row in rows]
        valid = [value for value in values if value is not None]
        result[name] = sum(valid) if valid else None
        result[f"{name}SampleCount"] = len(valid)
        result[f"{name}Coverage"] = len(valid) / count if count else None
    totals = [
        row.input_tokens + row.output_tokens
        for row in rows
        if row.input_tokens is not None and row.output_tokens is not None
    ]
    result["totalTokens"] = sum(totals) if totals else None
    result["totalTokensSampleCount"] = len(totals)
    result["totalTokensCoverage"] = len(totals) / count if count else None
    return result


def _window(start, end, zone):
    """Serialize an exclusive UTC window with its explicit display zone."""

    return {
        "start": start.isoformat(),
        "endExclusive": end.isoformat(),
        "timezone": zone,
    }


def query_dashboard(
    connection,
    user,
    version_id=None,
    window_start=None,
    window_end=None,
):
    """Read only local published data after current connection authorization."""

    connection = get_connection_for(
        user, connection.pk, action="view_business"
    )
    if connection.source_kind == "demo_snapshot":
        raise AgioneOpsError("SOURCE_KIND_FORBIDDEN", status_code=403)
    if connection.source_kind == "native":
        from agione_ops.snapshot_queries import dashboard_frame

        return dashboard_frame(
            connection, user, version_id, window_start, window_end,
        )
    if (window_start is None) != (window_end is None):
        raise AgioneOpsError("WINDOW_PAIR_REQUIRED")
    if window_start is not None:
        from agione_ops.sync import validate_window

        validate_window(window_start, window_end, "Asia/Shanghai")
    versions = DatasetVersion.objects.filter(
        connection=connection, run__status="succeeded"
    )
    if version_id is not None:
        try:
            selected_id = UUID(str(version_id))
        except (ValueError, TypeError, AttributeError):
            raise NotFound()
        version = versions.filter(pk=selected_id).first()
        if version is None:
            raise NotFound()
        if window_start is not None and (
            window_start != version.window_start
            or window_end != version.window_end
        ):
            raise AgioneOpsError("WINDOW_VERSION_MISMATCH", status_code=409)
    else:
        if window_start is not None:
            versions = versions.filter(
                window_start=window_start, window_end=window_end
            )
        version = versions.order_by("-published_at", "-id").first()
    comparison = {
        "state": "not_collected",
        "reason": "PREVIOUS_NOT_COLLECTED",
        "window": None,
        "summary": None,
    }
    if version is None:
        return {
            "state": "not_collected",
            "dataVersion": None,
            "summary": None,
            "trend": [],
            "modelDistribution": [],
            "coverage": None,
            "comparison": comparison,
        }
    rows = [
        link.fact
        for link in VersionCall.objects.filter(version=version).select_related(
            "fact"
        )
    ]
    by_day = defaultdict(list)
    by_model = defaultdict(list)
    zone = ZoneInfo(version.timezone)
    for row in rows:
        by_day[row.occurred_at.astimezone(zone).date()].append(row)
        by_model[row.model_id].append(row)
    trend = []
    at = version.window_start.astimezone(zone).date()
    last = (
        (version.window_end - timedelta(microseconds=1))
        .astimezone(zone)
        .date()
    )
    while at <= last:
        trend.append({"date": at.isoformat(), **_summary(by_day[at])})
        at += timedelta(days=1)
    duration = version.window_end - version.window_start
    comparison["window"] = _window(
        version.window_start - duration,
        version.window_start,
        version.timezone,
    )
    return {
        "state": "ready",
        "dataVersion": str(version.pk),
        "connectionId": str(connection.pk),
        "window": _window(
            version.window_start, version.window_end, version.timezone
        ),
        "publishedAt": version.published_at.isoformat(),
        "scope": {"type": "authorized_connection"},
        "coverage": version.coverage,
        "summary": _summary(rows),
        "trend": trend,
        "modelDistribution": [
            {"modelId": model, **_summary(by_model[model])}
            for model in sorted(by_model)
        ],
        "comparison": comparison,
    }
