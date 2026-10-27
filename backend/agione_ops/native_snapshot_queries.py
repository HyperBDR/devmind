"""Purely local analytics over an authorized immutable native publication."""

import uuid
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import APIException

from agione_ops.client import AgioneOpsError
from agione_ops.models import ConnectionGrant
from agione_ops.native_analytics import LiveAnalytics, entity, parse_time, summary
from agione_ops.native_finance import finance_for_window, unavailable_finance
from agione_ops.native_sync import validate_snapshot_data
from agione_ops.native_sync_models import NativePublishedSnapshot
from agione_ops.permissions import get_connection_for

OPERATIONS = frozenset({
    "dashboard", "schema", "analysis", "trend", "customers", "profile",
    "requests", "evidence", "finance",
})


def _fail(code, status=409):
    raise AgioneOpsError(code, status_code=status)


def _authorized(connection, user):
    """Never trust the request's stale active flag or Django perm cache."""
    fresh = get_user_model().objects.filter(pk=getattr(user, "pk", None)).first()
    if fresh is None or not fresh.is_active:
        _fail("ACCESS_REVOKED", 403)
    current = get_connection_for(fresh, connection.pk, "view_business")
    if current.source_kind != "native":
        _fail("SOURCE_KIND_FORBIDDEN", 403)
    return current, fresh


def validate_native_snapshot(connection, user, query, expected=None):
    """Read only small version/authority fields before a DTO cache lookup."""
    if not isinstance(query, dict) or query.get("operation") not in OPERATIONS:
        _fail("OPERATION_NOT_SUPPORTED", 400)
    current, fresh = _authorized(connection, user)
    selected = query.get("data_version", query.get("dataVersion"))
    snapshots = NativePublishedSnapshot.objects.filter(
        version__connection=current,
        version__run__status="succeeded",
    )
    if selected is not None:
        try:
            selected = uuid.UUID(str(selected))
        except (ValueError, TypeError, AttributeError):
            _fail("DATA_VERSION_NOT_FOUND", 404)
        snapshots = snapshots.filter(version_id=selected)
    row = snapshots.order_by("-version__published_at").values(
        "version_id", "content_digest", "version__window_start",
        "version__window_end", "version__published_at",
        "version__run__config_version", "version__run__credential_version",
    ).first()
    grant = ConnectionGrant.objects.get(
        connection=current, user=fresh, can_view=True,
    )
    signature = {
        "state": "not_collected", "dataVersion": None,
        "contentDigest": None, "connectionId": str(current.pk),
        "userId": str(fresh.pk), "configVersion": current.config_version,
        "credentialVersion": current.credential_version,
        "grantRevision": grant.revision,
    }
    if row is not None:
        if (
            row["version__run__config_version"] != current.config_version
            or row["version__run__credential_version"]
            != current.credential_version
        ):
            if selected is not None:
                _fail("SNAPSHOT_EPOCH_CHANGED")
        else:
            signature.update({
                "state": "ready", "dataVersion": str(row["version_id"]),
                "contentDigest": row["content_digest"],
                "windowStart": row["version__window_start"].isoformat(),
                "windowEndExclusive": row["version__window_end"].isoformat(),
                "publishedAt": row["version__published_at"].isoformat(),
            })
    elif selected is not None:
        _fail("DATA_VERSION_NOT_FOUND", 404)
    if signature["state"] == "ready" and query["operation"] == "dashboard":
        start, end = _window(query, signature)
        prior_start = start - (end - start)
        if prior_start < parse_time(signature["windowStart"]):
            previous = NativePublishedSnapshot.objects.filter(
                version__connection=current,
                version__run__status="succeeded",
                version__run__config_version=current.config_version,
                version__run__credential_version=current.credential_version,
                version__window_start__lte=prior_start,
                version__window_end__gte=start,
            ).order_by("-version__published_at").values(
                "version_id", "content_digest",
            ).first()
            if previous:
                signature["previousVersion"] = str(previous["version_id"])
                signature["previousDigest"] = previous["content_digest"]
    if expected is not None and signature != expected:
        _fail("SNAPSHOT_CHANGED")
    return signature


def _window(query, signature):
    start = parse_time(signature["windowStart"])
    end = parse_time(signature["windowEndExclusive"])
    raw = query.get("window")
    if raw is None:
        return start, end
    if not isinstance(raw, dict) or raw.get(
        "timezone", "Asia/Shanghai",
    ) != "Asia/Shanghai":
        _fail("LIVE_WINDOW_INVALID", 400)
    requested_start = parse_time(raw.get("start", start))
    requested_end = parse_time(raw.get(
        "end_exclusive", raw.get("endExclusive", end),
    ))
    if not start <= requested_start < requested_end <= end:
        _fail("SNAPSHOT_WINDOW_NOT_COLLECTED")
    return requested_start, requested_end


def _base(connection, operation, signature):
    return {
        "operation": operation, "state": signature["state"],
        "dataVersion": signature["dataVersion"], "data": None,
        "provenance": {
            "mode": "snapshot", "kind": "native_snapshot",
            "transport": "local_database", "platform": connection.platform,
            "account": connection.principal_kind,
            "publishedAt": signature.get("publishedAt"),
        },
        "capabilities": {
            "directUpstream": False, "readOnly": True,
            "operations": sorted(OPERATIONS), "refreshAsync": True,
        },
        "coverage": {
            "mode": "snapshot", "pagingComplete": False,
            "partial": False,
        },
    }


def apply_dashboard_observations(data, engine, previous, coverage):
    """Expose only observations backed by complete collected windows."""
    complete = coverage.get("pagingComplete") and not coverage.get("partial")
    filters = engine.filters
    all_results = not filters.get(
        "failure_types", filters.get("failureTypes", []),
    ) and set(filters.get("statuses", [])) in (
        set(), {"SUCCESS", "FAILURE", "UNKNOWN"},
    )
    if previous is not None and complete:
        data["comparison"] = {
            "state": "READY", "reason": None,
            "basis": "LOCAL_PUBLISHED_SNAPSHOT",
            "summary": summary(previous.global_rows),
        }
    for customer in data["customers"]:
        cid = customer["customerTenantId"]
        current_rows = engine.customer_global_rows.get(cid, [])
        prior_rows = (
            previous.customer_global_rows.get(cid, []) if previous else []
        )
        if previous is not None and complete:
            before = summary(prior_rows)
            count = before["requestCount"]
            customer["previous"] = before
            customer["comparisonState"] = "READY" if count else "NO_BASELINE"
            customer["comparisonReason"] = (
                None if count else "此客户前期无调用记录，无法计算变化比例"
            )
            customer["changePercent"] = (
                100 * (len(current_rows) - count) / count if count else None
            )
        observed = current_rows + prior_rows
        if complete and all_results and observed:
            last = max(parse_time(row["occurred_at"]) for row in observed)
            zone = ZoneInfo("Asia/Shanghai")
            days = max(0, (
                engine.end.astimezone(zone).date() - last.astimezone(zone).date()
            ).days - 1)
            customer["inactivity"] = {
                "state": "READY", "daysWithoutCalls": days,
                "lastObservedAt": last.isoformat(),
                "limitedSample": len(observed) < 3, "reason": None,
            }
        elif not all_results:
            customer["inactivity"] = {
                "state": "FILTER_NOT_APPLICABLE", "daysWithoutCalls": None,
                "reason": "仅筛选部分结果，不能判断近期无调用",
            }
    data["signalState"] = (
        "APPLICABLE" if all_results and not data["summary"]["unknownCount"]
        else "RESULT_FILTER_OR_UNKNOWN_STATUS"
    )
    states = [row["inactivity"]["state"] for row in data["customers"]]
    data["inactivityState"] = (
        "READY" if all(x == "READY" for x in states) else "PARTIAL"
    )


def query_native_snapshot(connection, user, query):
    """Compute legacy operation DTOs without constructing any source client."""
    signature = validate_native_snapshot(connection, user, query)
    operation = query["operation"]
    payload = query.get("payload", {})
    if not isinstance(payload, dict) or not isinstance(
        query.get("filters", {}), dict,
    ):
        _fail("INVALID_PAYLOAD", 400)
    result = _base(connection, operation, signature)
    if signature["state"] == "not_collected":
        result["reason"] = "NATIVE_SNAPSHOT_NOT_COLLECTED"
        validate_native_snapshot(connection, user, query, signature)
        return result
    snapshot = NativePublishedSnapshot.objects.select_related(
        "version",
    ).get(version_id=signature["dataVersion"])
    try:
        validate_snapshot_data(snapshot.data, snapshot.content_digest)
    except (ValueError, APIException, ValidationError) as error:
        raise AgioneOpsError(
            "SNAPSHOT_CONTENT_INVALID", status_code=409,
        ) from error

    start, end = _window(query, signature)
    rows = [row for row in snapshot.data["rows"] if (
        start <= parse_time(row["occurred_at"]) < end
    )]
    engine = LiveAnalytics(
        snapshot.data["customers"], snapshot.data["models"], rows,
        start, end, query,
    )
    stats = summary(engine.global_rows)
    finance = snapshot.data.get("finance", {})
    if operation in {"dashboard", "finance", "profile"} and not getattr(
        settings, "AGIONE_OPS_FINANCE_REFRESH_ON_SYNC", True,
    ):
        from agione_ops.native_finance_refresh import finance_for

        finance, _ = finance_for(connection, user)
    if finance and operation in {"dashboard", "finance"}:
        finance = finance_for_window(finance, start, end)
    if operation == "dashboard":
        data = engine.dashboard()
        prior_start = start - (end - start)
        prior_snapshot = None
        if prior_start >= parse_time(signature["windowStart"]):
            prior_snapshot = snapshot
        elif signature.get("previousVersion"):
            prior_snapshot = NativePublishedSnapshot.objects.select_related(
                "version",
            ).get(version_id=signature["previousVersion"])
            try:
                validate_snapshot_data(
                    prior_snapshot.data, signature["previousDigest"],
                )
            except (ValueError, APIException, ValidationError) as error:
                raise AgioneOpsError(
                    "SNAPSHOT_CONTENT_INVALID", status_code=409,
                ) from error
        previous = None
        if prior_snapshot and prior_snapshot.version.coverage.get(
            "pagingComplete"
        ) and not prior_snapshot.version.coverage.get("partial"):
            prior_rows = [row for row in prior_snapshot.data["rows"] if (
                prior_start <= parse_time(row["occurred_at"]) < start
            )]
            previous = LiveAnalytics(
                snapshot.data["customers"], snapshot.data["models"],
                prior_rows, prior_start, start, query,
            )
        apply_dashboard_observations(
            data, engine, previous, snapshot.version.coverage,
        )
        data["finance"] = finance or unavailable_finance(
            "NATIVE_FINANCE_NOT_COLLECTED"
        )
    elif operation == "schema":
        data = engine.schema()
    elif operation == "analysis":
        data = engine.analysis()
    elif operation == "customers":
        data = engine.page(engine.customer_rows())
        data["selectedCustomerTenantId"] = (
            data["items"][0]["customerTenantId"] if data["items"] else None
        )
        data["clearProfile"] = not data["items"]
    elif operation == "trend":
        data = {
            "summary": summary(engine.local_rows), "globalSummary": stats,
            "series": engine.trend(
                series_by=payload.get("series_by", payload.get("seriesBy")),
                granularity=payload.get("granularity", "day"),
            ),
            "previousSeries": None,
            "comparisonReason": "前期尚未采集",
            "comparisonBasis": "LOCAL_PUBLISHED_SNAPSHOT",
        }
    elif operation == "profile":
        cid = entity(payload.get("customer_id", payload.get("customerId")))
        data = engine.profile(cid)
        customer_finance = finance.get("customerFinance", {}).get(cid)
        if customer_finance is None:
            data["value"]["finance"] = unavailable_finance(
                "NATIVE_FINANCE_NOT_COLLECTED",
            )
        else:
            fetched_at = finance.get("fetchedAt")
            data["value"]["finance"] = {
                "available": True,
                "reason": None,
                "finance": {
                    **customer_finance,
                    "fetchedAt": fetched_at,
                    "summarySections": {
                        "accounts": {
                            "state": "FRESH", "read_at": fetched_at,
                        },
                        "overview": {
                            "state": "FRESH", "read_at": fetched_at,
                        },
                    },
                },
            }
    elif operation == "finance":
        data = finance or unavailable_finance("NATIVE_FINANCE_NOT_COLLECTED")
    elif operation == "requests":
        data = engine.requests()
    else:
        rid = entity(payload.get("evidence_id", payload.get("evidenceId")))
        record = next(
            (row for row in engine.local_rows if row["record_id"] == rid), None,
        )
        if record is None:
            _fail("EVIDENCE_NOT_FOUND", 404)
        data = {"record": engine.evidence(record)}
    result.update({
        "data": data,
        "window": {
            "start": start.isoformat(), "endExclusive": end.isoformat(),
            "timezone": "Asia/Shanghai",
        },
        "coverage": {
            **snapshot.version.coverage, "mode": "snapshot",
            "fetchedAt": snapshot.data["metadata"]["collectedAt"],
        },
    })
    result["provenance"].update({
        "roleState": snapshot.data["metadata"]["roleState"],
        "fetchedAt": snapshot.data["metadata"]["collectedAt"],
    })
    if operation == "dashboard":
        count = snapshot.version.coverage["directoryTotal"]
        result["overview"] = {
            "summary": stats, "metrics": stats,
            "directory": {
                "total": count, "confirmed": count,
                "excludedUnconfirmed": 0,
            },
            "readOnly": True, "mode": "snapshot",
            "dataVersion": signature["dataVersion"],
            "provenance": result["provenance"],
        }
    validate_native_snapshot(connection, user, query, signature)
    return result
