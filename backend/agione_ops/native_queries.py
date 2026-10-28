"""DevMind-owned live operations; no Demo transport or dataset persistence."""

import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from agione_ops.client import AgioneOpsError
from agione_ops.native_analytics import (
    LiveAnalytics,
    business_text,
    entity,
    fail,
    normalize_log,
    parse_time,
    summary,
    tenant_display_name,
)
from agione_ops.native_client import NativeClient
from agione_ops.native_account_scope import external_finance_directory
from agione_ops.native_finance import (
    aggregate_finance,
    read_recharge,
    unavailable_finance,
)
from agione_ops.permissions import connections_for, get_connection_for
from agione_ops.native_snapshot_queries import (
    query_native_snapshot, validate_native_snapshot,
)

OPERATIONS = {
    "dashboard",
    "schema",
    "analysis",
    "trend",
    "customers",
    "profile",
    "requests",
    "evidence",
    "finance",
}


def _epoch(connection):
    return tuple(
        getattr(connection, field)
        for field in (
            "config_version",
            "credential_version",
            "platform",
            "principal_kind",
            "expected_tenant_id",
            "endpoint",
            "source_kind",
        )
    )


class LiveSource:
    """Reauthorize each page and source section before and after its IO."""

    def __init__(self, connection, user, factory, heartbeat=None):
        self.user, self.id = user, connection.pk
        self.heartbeat = heartbeat
        self.connection = get_connection_for(user, self.id, "view_business")
        self.factory = factory
        self.epoch = _epoch(self.connection)
        if self.connection.source_kind != "native":
            fail("SOURCE_KIND_FORBIDDEN", 403)
        self.client = factory(self.connection)
        self.client.io_guard = self.guard
        self.pages_read = 0
        try:
            self.guard()
            identity = self.call(self.client.identity)
            if not isinstance(identity, dict) or any(
                identity.get(key) != getattr(self.connection, attr)
                for key, attr in (
                    ("tenant_id", "expected_tenant_id"),
                    ("platform", "platform"),
                    ("principal_kind", "principal_kind"),
                )
            ):
                fail("SOURCE_IDENTITY_MISMATCH", 403)
            self.identity = identity
        except Exception:
            self.client.close()
            raise

    def guard(self):
        if getattr(settings, "AGIONE_OPS_NATIVE_ENABLED", False) is not True:
            fail("NATIVE_DISABLED", 503)
        current = get_connection_for(self.user, self.id, "view_business")
        if not current.enabled or _epoch(current) != self.epoch:
            fail("CONNECTION_CHANGED", 409)
        if self.heartbeat is not None:
            self.heartbeat()

    def call(self, method, *args, **kwargs):
        self.guard()
        try:
            return method(*args, **kwargs)
        finally:
            self.guard()

    def get(self, path, params=None):
        return self.call(self.client.get, path, params)

    def pages(self, path, params=None, *, directory=False, key="id"):
        field = "pageIndex" if directory else "current"
        size_field = "pageSize" if directory else "size"
        rows_field = "data" if directory else "records"
        size = 50 if directory else 500
        result, seen, expected = [], set(), None

        def validate(raw, expected_total=None):
            if not isinstance(raw, dict):
                fail()
            rows, total = raw.get(rows_field), raw.get("total")
            if (
                not isinstance(rows, list)
                or len(rows) > size
                or type(total) is not int
                or total < 0
            ):
                fail()
            if total > size * 100:
                fail("SOURCE_PAGE_LIMIT", 409)
            if expected_total is not None and expected_total != total:
                fail("SOURCE_CHANGED_DURING_PAGING", 409)
            return rows, total

        raw = self.get(path, {**(params or {}), field: 1, size_field: size})
        first_rows, expected = validate(raw)
        page_count = max(1, math.ceil(expected / size))
        pages = [(1, first_rows)]
        if not directory and page_count > 1:
            workers = min(8, page_count - 1)
            batches = [list(range(2 + index, page_count + 1, workers))
                       for index in range(workers)]

            def read_batch(numbers):
                client = self.factory(self.connection)
                client.io_guard = self.guard
                try:
                    identity = self.call(client.identity)
                    if not isinstance(identity, dict) or any(
                        identity.get(identity_key) != getattr(
                            self.connection, attribute
                        )
                        for identity_key, attribute in (
                            ("tenant_id", "expected_tenant_id"),
                            ("platform", "platform"),
                            ("principal_kind", "principal_kind"),
                        )
                    ):
                        fail("SOURCE_IDENTITY_MISMATCH", 403)
                    batch = []
                    for page in numbers:
                        raw_page = self.call(
                            client.get,
                            path,
                            {
                                **(params or {}),
                                field: page,
                                size_field: size,
                            },
                        )
                        rows, _ = validate(raw_page, expected)
                        batch.append((page, rows))
                    return batch
                finally:
                    client.close()

            with ThreadPoolExecutor(max_workers=workers) as executor:
                for batch in executor.map(read_batch, batches):
                    pages.extend(batch)
        elif directory:
            for page in range(2, page_count + 1):
                raw_page = self.get(
                    path,
                    {**(params or {}), field: page, size_field: size},
                )
                rows, _ = validate(raw_page, expected)
                pages.append((page, rows))

        self.pages_read += len(pages)
        for page, rows in sorted(pages):
            for row in rows:
                if not isinstance(row, dict):
                    fail()
                rid = entity(row.get(key))
                if rid in seen:
                    fail("SOURCE_DUPLICATE_PAGE", 409)
                seen.add(rid)
                result.append(row)
            if len(result) > expected:
                fail("SOURCE_INCOMPLETE_PAGING", 409)
            if page < page_count and not rows:
                fail("SOURCE_INCOMPLETE_PAGING", 409)
        if len(result) != expected:
            fail("SOURCE_INCOMPLETE_PAGING", 409)
        return result

    def directory(self):
        operator = self.connection.principal_kind == "operator"
        key = "tenantId" if operator else "customerTenantId"
        path = "/coperation/tenant/" + (
            "op-customers" if operator else "provider-customers"
        )
        rows = self.pages(
            path,
            {"identityCode": "EU"} if operator else {},
            directory=True,
            key=key,
        )
        return {
            entity(row[key]): {
                "name": tenant_display_name(row, entity(row[key])),
                "organizationName": business_text(row.get("organizationName")),
            }
            for row in rows
        }

    def logs(self, start, end):
        zone = ZoneInfo("Asia/Shanghai")
        at, collected, seen = start.astimezone(zone), [], set()
        excluded = 0
        while at < end:
            month_end = (at.replace(day=28) + timedelta(days=4)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            stop = min(end, month_end)
            upper = stop - timedelta(seconds=1) if stop == month_end else stop
            rows = self.pages(
                "/xapi/observability/call-logs",
                {
                    "startTime": at.strftime("%Y-%m-%d %H:%M:%S"),
                    "endTime": upper.astimezone(zone).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                },
            )
            for raw in rows:
                if (
                    stop == month_end
                    and type(raw.get("createTime")) in (int, float)
                    and raw["createTime"] % 1000
                ):
                    fail("SOURCE_TIME_PRECISION_CHANGED", 409)
                row = normalize_log(raw, at, stop)
                if row is None:
                    excluded += 1
                    continue
                if row["record_id"] in seen:
                    fail("SOURCE_DUPLICATE_PAGE", 409)
                seen.add(row["record_id"])
                collected.append(row)
            at = stop
        return collected, excluded

    def close(self):
        self.client.close()


def _window(query):
    raw = query.get("window") or {}
    if not isinstance(raw, dict):
        fail("LIVE_WINDOW_INVALID", 400)
    now = timezone.now()
    zone = ZoneInfo("Asia/Shanghai")
    default_end = now.astimezone(zone).replace(microsecond=0)
    start = parse_time(raw.get("start", default_end - timedelta(days=7)))
    end = parse_time(
        raw.get("end_exclusive", raw.get("endExclusive", default_end))
    )
    if not timedelta(0) < end - start <= timedelta(days=31) or end > now:
        fail("LIVE_WINDOW_INVALID", 400)
    if raw.get("timezone", "Asia/Shanghai") != "Asia/Shanghai":
        fail("LIVE_WINDOW_INVALID", 400)
    return start, end


def _finance(source, user, factory, payload, fetched_at, customer=None):
    selected = source.connection
    candidates = list(
        connections_for(user, "view_business").filter(
            platform=selected.platform,
            principal_kind="operator",
            source_kind="native",
            enabled=True,
            endpoint=selected.endpoint,
        )
    )
    if selected.principal_kind == "operator":
        operator = source
    elif not candidates:
        return unavailable_finance("OPERATOR_VIEW_REQUIRED")
    elif len(candidates) != 1:
        return unavailable_finance("OPERATOR_CONNECTION_AMBIGUOUS")
    else:
        operator = LiveSource(
            candidates[0], user, factory, heartbeat=source.heartbeat,
        )
    try:

        def finance_guard():
            source.guard()
            operator.guard()

        operator.client.io_guard = finance_guard
        rows = operator.pages(
            "/coperation/tenant/op-customers", {"identityCode": "EU"},
            directory=True, key="tenantId",
        )
        directory = external_finance_directory(rows)
        if customer is not None:
            if customer not in directory:
                return unavailable_finance(
                    "CUSTOMER_NOT_IN_OPERATOR_DIRECTORY"
                )
            selected_customers, offset = [customer], 0
            total = 1
        else:
            offset = payload.get("offset", 0)
            limit = payload.get("limit", 5)
            if (
                type(offset) is not int
                or offset < 0
                or type(limit) is not int
                or not 1 <= limit <= 500
            ):
                fail("INVALID_PAGINATION", 400)
            total = len(directory)
            selected_customers = sorted(directory)[offset : offset + limit]
        finance_client = operator.client
        finance_client.io_guard = finance_guard
        month = timezone.now().astimezone(ZoneInfo("Asia/Shanghai")).date()
        previous_month = (month.replace(day=1) - timedelta(days=1)).strftime(
            "%Y-%m"
        )

        def read_customer(cid):
            """Read one customer through the shared task-owned client."""
            finance_guard()
            path = "/financial/api/finance/v1/admin/customers/" + cid
            accounts = finance_client.get(path + "/accounts")
            overview = finance_client.get(
                path + "/overview", {"range": "thisMonth"}
            )
            try:
                previous = finance_client.get(
                    path + "/overview", {"range": "lastMonth"}
                )
            except AgioneOpsError as exc:
                if exc.code not in {
                    "SOURCE_TIMEOUT", "SOURCE_RATE_LIMITED",
                    "SOURCE_UNAVAILABLE", "SOURCE_UNREACHABLE",
                    "SOURCE_REJECTED",
                }:
                    raise
                previous = None
            try:
                recharge = read_recharge(finance_client, cid)
                recharge_error = None
            except AgioneOpsError as exc:
                recharge = None
                recharge_error = exc.code if re.fullmatch(
                    r"[A-Z_0-9]{1,80}", str(exc.code)
                ) else "SOURCE_UNAVAILABLE"
            finance_guard()
            return cid, accounts, overview, previous, recharge, recharge_error

        workers = min(5, len(selected_customers))
        if workers:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                readings = list(executor.map(read_customer, selected_customers))
        else:
            readings = []
        if timezone.now().astimezone(ZoneInfo("Asia/Shanghai")).strftime(
            "%Y-%m"
        ) != month.strftime("%Y-%m"):
            fail("SOURCE_REJECTED", 409)
        records = [(cid, accounts, overview)
                   for cid, accounts, overview, _, _, _ in readings]
        result = aggregate_finance(
            records,
            total,
            month.strftime("%Y-%m"),
            fetched_at,
            offset,
        )
        if all(isinstance(previous, dict) for _, _, _, previous, _, _ in readings):
            historical = aggregate_finance(
                [(cid, [], {
                    **{key: previous[key] for key in (
                        "tenantId", "cusTenantId", "customerTenantId"
                    ) if key in previous},
                    "currentCycle": previous_month,
                    "trend": previous.get("trend"),
                }) for cid, _, _, previous, _, _ in readings],
                total, previous_month, fetched_at, offset,
            )
            result["trend"] = historical["trend"] + result["trend"]
            if result["trend"]:
                result["trendCustomers"] = total
                result["trendTotal"] = str(sum(
                    (Decimal(row["value"]) for row in result["trend"]),
                    Decimal(),
                ))
                result["trendReason"] = ""
        for cid, _, _, _, recharge, recharge_error in readings:
            customer_data = result["customerFinance"].get(cid)
            if customer_data is not None:
                customer_data["recharge"] = recharge
                customer_data["rechargeError"] = recharge_error
        finance_guard()
        return result
    finally:
        if operator is not source:
            operator.close()


def _overview(stats, directory_count, fetched_at):
    """Match existing page-level metrics without manufacturing a version."""
    return {
        "summary": stats,
        "metrics": stats,
        "directory": {
            "total": directory_count,
            "confirmed": directory_count,
            "excludedUnconfirmed": 0,
        },
        "provenance": {"mode": "live", "fetchedAt": fetched_at},
        "readOnly": True,
        "mode": "live",
    }


def collect_native_finance(
    connection, user, *, client_factory=None, heartbeat=None,
):
    """Collect one complete authorized Operator finance projection."""
    candidates = list(
        connections_for(user, "view_business").filter(
            platform=connection.platform,
            principal_kind="operator",
            source_kind="native",
            enabled=True,
            endpoint=connection.endpoint,
        )[:2]
    )
    if connection.principal_kind == "operator":
        operator = connection
    elif not candidates:
        result = unavailable_finance("OPERATOR_VIEW_REQUIRED")
        operator = None
    elif len(candidates) != 1:
        result = unavailable_finance("OPERATOR_CONNECTION_AMBIGUOUS")
        operator = None
    else:
        operator = candidates[0]
    if operator is not None:
        result = _legacy_live_operation(
            operator,
            user,
            {
                "operation": "finance",
                "payload": {"offset": 0, "limit": 500},
            },
            client_factory=client_factory,
            heartbeat=heartbeat,
        )["data"]
    return {
        **result,
        "mode": "snapshot",
        "scopeLabel": "Operator 已授权目录财务快照，独立于调用筛选",
        "coverageBasis": "native_published_snapshot",
    }


def query_live_operation(connection, user, query, *, client_factory=None):
    """Compatibility endpoint: local publication only, never source IO."""
    from agione_ops.native_snapshot_queries import validate_native_snapshot
    from agione_ops.snapshot_queries import query_operation

    signature = validate_native_snapshot(connection, user, query)
    if signature["state"] != "ready":
        return query_native_snapshot(connection, user, query)
    pinned = {**query, "data_version": signature["dataVersion"]}
    pinned.pop("dataVersion", None)
    return query_operation(connection, user, pinned)


def _legacy_live_operation(
    connection, user, query, *, client_factory=None, heartbeat=None,
):
    """Legacy source helper retained for explicit background use only."""
    if not isinstance(query, dict) or query.get("operation") not in OPERATIONS:
        fail("OPERATION_NOT_SUPPORTED", 400)
    if "dataVersion" in query or "data_version" in query:
        fail("LIVE_VERSION_NOT_SUPPORTED", 400)
    factory = client_factory or NativeClient
    operation = query["operation"]
    payload = query.get("payload", {})
    if not isinstance(payload, dict):
        fail("INVALID_PAYLOAD", 400)
    start, end = _window(query)
    fetched_at = timezone.now().isoformat()
    source = LiveSource(connection, user, factory, heartbeat=heartbeat)
    try:
        customers = source.directory()
        directory_count = len(customers)
        if connection.principal_kind == "provider":
            own_tenant = entity(connection.expected_tenant_id)
            customers.setdefault(
                own_tenant,
                {"name": own_tenant, "organizationName": None},
            )
        if operation == "finance":
            cid = payload.get("customer_id", payload.get("customerId"))
            if cid is not None:
                cid = entity(cid)
                if cid not in customers:
                    fail("CUSTOMER_NOT_FOUND", 404)
            data = _finance(source, user, factory, payload, fetched_at, cid)
            quarantined, boundary_excluded, count = 0, 0, 0
            stats = summary([])
        else:
            raw_models = source.get("/xapi/observability/models/options")
            if not isinstance(raw_models, list) or len(raw_models) > 10000:
                fail()
            models = {}
            for row in raw_models:
                if not isinstance(row, dict):
                    fail()
                mid = entity(row.get("modelId", row.get("id")))
                models[mid] = business_text(
                    row.get("metaModelName") or row.get("modelName"), mid
                )
            rows, boundary_excluded = source.logs(start, end)
            quarantined = sum(x["customer_id"] not in customers for x in rows)
            rows = [x for x in rows if x["customer_id"] in customers]
            count = len(rows)
            engine = LiveAnalytics(customers, models, rows, start, end, query)
            stats = summary(engine.global_rows)
            if operation == "dashboard":
                data = engine.dashboard()
            elif operation == "analysis":
                data = engine.analysis()
            elif operation == "schema":
                data = engine.schema()
            elif operation == "customers":
                data = engine.page(engine.customer_rows())
                data["selectedCustomerTenantId"] = (
                    data["items"][0]["customerTenantId"]
                    if data["items"]
                    else None
                )
                data["clearProfile"] = not data["items"]
            elif operation == "trend":
                data = {
                    "summary": summary(engine.local_rows),
                    "globalSummary": stats,
                    "series": engine.trend(
                        series_by=payload.get(
                            "series_by", payload.get("seriesBy")
                        ),
                        granularity=payload.get("granularity", "day"),
                    ),
                    "previousSeries": None,
                    "comparisonReason": "前期尚未读取",
                    "comparisonBasis": "DIRECT_UPSTREAM",
                }
            elif operation == "profile":
                cid = entity(
                    payload.get("customer_id", payload.get("customerId"))
                )
                data = engine.profile(cid)
                data["value"]["finance"] = _finance(
                    source, user, factory, {}, fetched_at, cid
                )
            elif operation == "requests":
                data = engine.requests()
            else:
                rid = entity(
                    payload.get("evidence_id", payload.get("evidenceId"))
                )
                record = next(
                    (x for x in engine.local_rows if x["record_id"] == rid),
                    None,
                )
                if record is None:
                    fail("EVIDENCE_NOT_FOUND", 404)
                data = {"record": engine.evidence(record)}
        source.guard()
        finance = data if operation == "finance" else data.get("finance", {})
        finance_partial = bool(finance.get("partial"))
        result = {
            "operation": operation,
            "data": data,
            "window": {
                "start": start.isoformat(),
                "endExclusive": end.isoformat(),
                "timezone": "Asia/Shanghai",
            },
            "coverage": {
                "mode": "live",
                "fetchedAt": fetched_at,
                "directoryTotal": directory_count,
                "confirmedDirectoryCount": directory_count,
                "pagingComplete": (
                    not finance_partial if operation == "finance" else True
                ),
                "partial": (
                    finance_partial if operation == "finance" else False
                ),
                "financePartial": finance_partial,
                "financeNextOffset": finance.get("nextOffset"),
                "sourceRecordCount": count,
                "quarantinedRecordCount": quarantined,
                "boundaryExcludedCount": boundary_excluded,
                "pagesRead": source.pages_read,
                "comparisonHistoryVerified": False,
                "latencyUnitVerified": False,
            },
            "provenance": {
                "mode": "live",
                "transport": "direct_upstream",
                "fetchedAt": fetched_at,
                "platform": connection.platform,
                "account": connection.principal_kind,
                "roleState": source.identity.get("role_state", "not_verified"),
            },
            "capabilities": {
                "directUpstream": True,
                "readOnly": True,
                "operations": sorted(OPERATIONS),
            },
        }
        if operation == "dashboard":
            result["overview"] = _overview(stats, directory_count, fetched_at)
        return result
    finally:
        source.close()
