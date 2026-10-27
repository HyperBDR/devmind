"""Pure business calculations over this request's freshly fetched records."""

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from agione_ops.client import AgioneOpsError

DIMENSIONS = (
    "date",
    "customerTenantId",
    "modelId",
    "userId",
    "status",
    "failureType",
)
METRICS = (
    "requestCount",
    "successCount",
    "failureCount",
    "successRate",
    "inputTokens",
    "outputTokens",
    "totalTokens",
    "p95LatencyMs",
    "distinctCustomers",
    "distinctUsers",
    "distinctModels",
)


def fail(code="SOURCE_SHAPE_CHANGED", status=502):
    """Use stable errors without publishing upstream text or payloads."""
    raise AgioneOpsError(code, status_code=status)


def entity(value, optional=False):
    """Preserve large source identifiers as strings, never floats."""
    if optional and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        fail()
    value = str(value)
    if not re.fullmatch(r"[0-9]{1,40}", value):
        fail()
    return value


def business_text(value, fallback=None):
    """Only short organization/model labels, never contact or raw prose."""
    if not isinstance(value, str) or len(value) > 160:
        return fallback
    if re.search(
        r"[<>\x00-\x1f@]|https?://|bearer\s|password|secret|api.key",
        value,
        re.I,
    ):
        return fallback
    if re.search(r"(?:\+?\d[\s-]?){11,}", value) and not value.isdecimal():
        return fallback
    return value.strip() or fallback


def token(value):
    """Unknown usage stays unknown; bool and nonintegral usage are invalid."""
    return value if type(value) is int and 0 <= value <= 10**15 else None


def parse_time(value):
    """Accept only explicit timezone-aware dates."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            fail("LIVE_WINDOW_INVALID", 400)
    else:
        fail("LIVE_WINDOW_INVALID", 400)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        fail("LIVE_WINDOW_INVALID", 400)
    return parsed


def normalize_log(raw, start, end):
    """Select technical fields before any business calculation."""
    if not isinstance(raw, dict):
        fail()
    rid = entity(raw.get("id", raw.get("record_id")))
    if "createTime" in raw:
        stamp = raw["createTime"]
        if type(stamp) not in (int, float):
            fail("SOURCE_TIME_SHAPE")
        try:
            at = datetime.fromtimestamp(stamp / 1000, ZoneInfo("UTC"))
        except (ValueError, OverflowError, OSError):
            fail("SOURCE_TIME_SHAPE")
    else:
        at = parse_time(raw.get("occurred_at"))
    if not start <= at < end:
        return None
    result = raw.get("result")
    if not isinstance(result, str) or result not in {
        "SUCCESS",
        "FAILURE",
        "UNKNOWN",
    }:
        result = (
            {0: "FAILURE", 1: "SUCCESS"}.get(raw.get("status"), "UNKNOWN")
            if type(raw.get("status")) is int
            else "UNKNOWN"
        )
    failure = raw.get("failureType")
    failure = str(failure) if type(failure) in (str, int) else None
    if failure and not re.fullmatch(r"[A-Za-z0-9_:-]{1,60}", failure):
        failure = None
    return {
        "record_id": rid,
        "customer_id": entity(
            raw.get("customerTenantId", raw.get("customer_id")), optional=True
        ),
        "model_id": entity(
            raw.get("modelId", raw.get("model_id")), optional=True
        ),
        "user_id": entity(
            raw.get("userId", raw.get("user_id")), optional=True
        ),
        "project_id": entity(raw.get("projectId"), optional=True),
        "subject_type": (
            "PROJECT" if raw.get("keyType") == "PROJECT" else "USER"
        ),
        "occurred_at": at.isoformat(),
        "result": result,
        "input_tokens": token(
            raw.get("promptTokens", raw.get("input_tokens"))
        ),
        "output_tokens": token(
            raw.get("completionTokens", raw.get("output_tokens"))
        ),
        "total_tokens": token(raw.get("totalTokens", raw.get("total_tokens"))),
        "failureKey": (
            "NOT_APPLICABLE"
            if result == "SUCCESS"
            else "source:" + failure if failure else "UNKNOWN"
        ),
        "latencyState": "UNIT_UNCONFIRMED",
    }


def user_key(row):
    """Disambiguate members by customer and optional project identity."""
    prefix = row["customer_id"] + ":"
    if row["subject_type"] == "PROJECT":
        return prefix + "PROJECT:" + (row["project_id"] or "UNKNOWN")
    return prefix + (row["user_id"] or "UNKNOWN")


def summary(rows):
    """Return reconciled source rates and explicit usage sample coverage."""
    count = len(rows)
    success = sum(x["result"] == "SUCCESS" for x in rows)
    failures = sum(x["result"] == "FAILURE" for x in rows)
    balance = sum(x["failureKey"] == "source:3" for x in rows)
    unmapped = sum(
        x["result"] == "FAILURE" and x["failureKey"] != "source:3"
        for x in rows
    )
    result = {
        "requestCount": count,
        "successCount": success,
        "failureCount": failures,
        "unknownCount": count - success - failures,
        "successRate": 100 * success / count if count else None,
        "failureRate": 100 * failures / count if count else None,
        "rateUnit": "percent",
        "balanceFailureCount": balance,
        "technicalFailureCount": None if unmapped else 0,
        "knownTechnicalFailureCount": 0,
        "unmappedFailureCount": unmapped,
        "failureClassificationComplete": not unmapped,
        "distinctCustomers": len({x["customer_id"] for x in rows}),
        "distinctUsers": len(
            {user_key(x) for x in rows if x["user_id"] or x["project_id"]}
        ),
        "distinctModels": len({x["model_id"] for x in rows if x["model_id"]}),
        "p95LatencyMs": None,
        "ttftMs": None,
        "latencyState": "UNIT_UNCONFIRMED",
        "successfulLatencySamples": 0,
        "unknownAssociations": {
            key: sum(x[key] is None for x in rows)
            for key in ("customer_id", "user_id", "model_id")
        },
    }
    for key, field in (
        ("inputTokens", "input_tokens"),
        ("outputTokens", "output_tokens"),
        ("totalTokens", "total_tokens"),
    ):
        values = [x[field] for x in rows if x[field] is not None]
        result[key] = sum(values) if values or not count else None
        result[key + "SampleCount"] = len(values)
        result[key + "Coverage"] = len(values) / count if count else None
    pairs = [
        (x["input_tokens"], x["output_tokens"])
        for x in rows
        if x["input_tokens"] is not None and x["output_tokens"] is not None
    ]
    total = sum(a + b for a, b in pairs)
    result.update(
        inputOutputPairSampleCount=len(pairs),
        pairedInputTokens=sum(a for a, _ in pairs) if pairs else None,
        pairedOutputTokens=sum(b for _, b in pairs) if pairs else None,
        knownInputShare=sum(a for a, _ in pairs) / total if total else None,
    )
    return result


class LiveAnalytics:
    """No persistent datasets: scope and rows exist only in this invocation."""

    def __init__(self, customers, models, rows, start, end, query):
        self.customers, self.models, self.rows = customers, models, rows
        self.start, self.end, self.query = start, end, query
        self.payload = query.get("payload", {})
        self.filters = query.get("filters", {})
        self.selected = query.get("customer_ids", query.get("customerIds"))
        if self.selected is not None and (
            not self.selected or set(self.selected) - customers.keys()
        ):
            fail("SCOPE_FORBIDDEN", 403)
        self.global_rows = [x for x in rows if self.matches(x)]
        self.customer_global_rows = {}
        for row in self.global_rows:
            self.customer_global_rows.setdefault(
                row["customer_id"], []
            ).append(row)
        ids = self.payload.get("user_ids", self.payload.get("userIds", []))
        self.local_rows = [
            x
            for x in self.global_rows
            if not ids or user_key(x) in ids or x["user_id"] in ids
        ]

    def matches(self, row):
        filters = self.filters
        return (
            not self.selected or row["customer_id"] in self.selected
        ) and all(
            not filters.get(snake, filters.get(camel, []))
            or value in filters.get(snake, filters.get(camel, []))
            for snake, camel, value in (
                ("model_ids", "modelIds", row["model_id"]),
                ("statuses", "statuses", row["result"]),
                ("failure_types", "failureTypes", row["failureKey"]),
            )
        )

    def dimension(self, row, key):
        return {
            "date": lambda: parse_time(row["occurred_at"])
            .astimezone(ZoneInfo("Asia/Shanghai"))
            .date()
            .isoformat(),
            "customerTenantId": lambda: row["customer_id"],
            "modelId": lambda: row["model_id"] or "UNKNOWN",
            "userId": lambda: user_key(row),
            "status": lambda: row["result"],
            "failureType": lambda: row["failureKey"],
        }[key]()

    def label(self, key, value):
        if key == "customerTenantId":
            return self.customers.get(value, {}).get("name", value)
        if key == "modelId":
            return self.models.get(value, value)
        return {"SUCCESS": "成功", "FAILURE": "失败", "UNKNOWN": "未知"}.get(
            value, value
        )

    def groups(self, rows, dimensions):
        if not 1 <= len(dimensions) <= 2 or any(
            x not in DIMENSIONS for x in dimensions
        ):
            fail("INVALID_DIMENSION", 400)
        buckets = defaultdict(list)
        for row in rows:
            buckets[
                tuple(self.dimension(row, key) for key in dimensions)
            ].append(row)
        return [
            {
                "groupKey": dict(zip(dimensions, values)),
                "label": " / ".join(
                    self.label(key, value)
                    for key, value in zip(dimensions, values)
                ),
                "metrics": summary(records),
                "requestShare": len(records) / len(rows),
                "shareUnit": "fraction",
            }
            for values, records in buckets.items()
        ]

    def page(self, rows):
        page = self.payload.get("page", 1)
        size = self.payload.get("page_size", self.payload.get("pageSize", 20))
        if (
            type(page) is not int
            or page < 1
            or type(size) is not int
            or not 1 <= size <= 200
        ):
            fail("INVALID_PAGINATION", 400)
        return {
            "items": rows[(page - 1) * size : page * size],
            "total": len(rows),
            "page": page,
            "pageSize": size,
        }

    def trend(self, rows=None, series_by=None, granularity="day"):
        rows = self.local_rows if rows is None else rows
        if series_by is not None and series_by not in DIMENSIONS:
            fail("INVALID_DIMENSION", 400)
        if granularity not in {"hour", "day"}:
            fail("INVALID_GRANULARITY", 400)
        zone = ZoneInfo("Asia/Shanghai")
        step = (
            timedelta(hours=1) if granularity == "hour" else timedelta(days=1)
        )

        def bucket(value):
            value = value.astimezone(zone).replace(
                minute=0, second=0, microsecond=0
            )
            return value if granularity == "hour" else value.replace(hour=0)

        groups = defaultdict(list)
        keys = (
            {self.dimension(x, series_by) for x in rows}
            if series_by
            else {"all"}
        )
        for row in rows:
            key = self.dimension(row, series_by) if series_by else "all"
            groups[key, bucket(parse_time(row["occurred_at"]))].append(row)
        result = []
        for key in sorted(keys):
            points, at = [], bucket(self.start)
            while at < self.end:
                points.append(
                    {
                        "bucketStart": max(at, self.start).isoformat(),
                        "bucketEndExclusive": min(
                            at + step, self.end
                        ).isoformat(),
                        **summary(groups[key, at]),
                    }
                )
                at += step
            result.append(
                {
                    "seriesKey": key,
                    "label": (
                        self.label(series_by, key) if series_by else "全部"
                    ),
                    "points": points,
                }
            )
        return result

    def analysis(self):
        dims = self.payload.get(
            "group_by", self.payload.get("groupBy", ["customerTenantId"])
        )
        metrics = self.payload.get("metrics", ["requestCount"])
        if not metrics or any(x not in METRICS for x in metrics):
            fail("INVALID_METRIC", 400)
        rows = self.groups(self.local_rows, dims)
        metric = metrics[0]
        rows.sort(
            key=lambda x: (
                x["metrics"].get(metric) is None,
                -(x["metrics"].get(metric) or 0),
                json.dumps(x["groupKey"], sort_keys=True),
            )
        )
        page = self.page(rows)
        return {
            "globalSummary": summary(self.global_rows),
            "summary": summary(self.local_rows),
            "rows": page.pop("items"),
            **page,
            "topRows": rows[:8],
            "metrics": metrics,
            "sortMetric": metric,
            "reconciliation": {
                "groupedRequestCount": sum(
                    x["metrics"]["requestCount"] for x in rows
                ),
                "requestCount": len(self.local_rows),
            },
        }

    def customer_row(self, cid):
        rows = self.customer_global_rows.get(cid, [])
        stats = summary(rows)
        all_results = not self.filters.get(
            "failure_types", self.filters.get("failureTypes", [])
        ) and set(self.filters.get("statuses", [])) in (
            set(), {"SUCCESS", "FAILURE", "UNKNOWN"}
        )
        signals = (
            ["blocked"]
            if all_results and len(rows) >= 3
            and not stats["successCount"]
            and not stats["unknownCount"]
            else [
                (
                    "no_requests"
                    if not rows
                    else "trial" if len(rows) < 30 else "stable"
                )
            ]
        )
        return {
            "customerTenantId": cid,
            "name": self.customers[cid]["name"],
            "summary": stats,
            "signals": signals,
            "inactivity": {
                "state": "UNAVAILABLE",
                "daysWithoutCalls": None,
                "reason": "实时查询未证明完整历史，无调用不能推断流失",
            },
            "comparisonState": "UNAVAILABLE",
            "previous": None,
            "changePercent": None,
            "comparisonReason": "前期尚未读取",
            "blockedApplicability": (
                "APPLICABLE" if all_results and not stats["unknownCount"]
                else "RESULT_FILTER_OR_UNKNOWN_STATUS"
            ),
            "slowResponseState": "UNIT_UNCONFIRMED",
            "workItem": {
                "version": None,
                "followupStage": "PENDING",
                "isCompleted": False,
                "isOverdue": False,
                "isDueToday": False,
            },
        }

    def customer_rows(self):
        rows = [
            self.customer_row(cid)
            for cid in self.customers
            if not self.selected or cid in self.selected
        ]
        search = self.payload.get("search", "").casefold()
        signal = self.payload.get("signal")
        return sorted(
            [
                x
                for x in rows
                if search
                in (x["name"] + " " + x["customerTenantId"]).casefold()
                and (not signal or signal in x["signals"])
            ],
            key=lambda x: (
                -x["summary"]["requestCount"],
                x["customerTenantId"],
            ),
        )

    def evidence(self, row):
        return {
            key: value
            for key, value in {
                **row,
                "customerName": self.customers[row["customer_id"]]["name"],
                "financialLinkState": "UNAVAILABLE",
            }.items()
            if key not in {"project_id", "subject_type"}
        }

    def requests(self):
        group = self.payload.get("group_key", self.payload.get("groupKey", {}))
        if any(key not in DIMENSIONS for key in group) or len(group) > 2:
            fail("INVALID_DIMENSION", 400)
        rows = [
            x
            for x in self.local_rows
            if all(
                self.dimension(x, key) == value for key, value in group.items()
            )
        ]
        rows.sort(
            key=lambda x: (x["occurred_at"], x["record_id"]), reverse=True
        )
        return {
            **self.page([self.evidence(x) for x in rows]),
            "summary": summary(rows),
        }

    def dashboard(self):
        customers = self.customer_rows()
        blocked = [x for x in customers if "blocked" in x["signals"]]
        return {
            "summary": summary(self.global_rows),
            "customers": customers,
            "lead": blocked[0] if blocked else None,
            "worklist": blocked,
            "blocked": blocked,
            "decline": [],
            "inactive": [],
            "technicalFailures": [],
            "queueCounts": {
                "pending": len(blocked),
                "today": 0,
                "overdue": 0,
                "completed": 0,
            },
            "comparison": {
                "state": "UNAVAILABLE",
                "reason": "前期尚未读取",
                "basis": "DIRECT_UPSTREAM",
                "summary": None,
            },
            "trend": self.trend(self.global_rows),
            "models": self.groups(self.global_rows, ["modelId"]),
            "failureBreakdown": self.groups(
                [x for x in self.global_rows if x["result"] == "FAILURE"],
                ["failureType"],
            ),
            "affectedCustomers": [
                x for x in customers if x["summary"]["failureCount"]
            ],
            "activation": {
                "state": "NOT_READY",
                "data": None,
                "reason": "上游未提供注册与现金口径",
            },
        }

    def profile(self, cid):
        if (
            cid not in self.customers
            or self.selected
            and cid not in self.selected
        ):
            fail("CUSTOMER_NOT_FOUND", 404)
        rows = self.customer_global_rows.get(cid, [])
        stats = summary(rows)
        members = self.groups(rows, ["userId"])
        for member in members:
            member["subjectType"] = (
                "PROJECT"
                if ":PROJECT:" in member["groupKey"]["userId"]
                else "USER"
            )
        models = self.groups(rows, ["modelId"])
        signal = self.customer_row(cid)
        last = max((x["occurred_at"] for x in rows), default=None)
        return {
            "customerTenantId": cid,
            "name": self.customers[cid]["name"],
            "identity": {
                "organizationName": self.customers[cid].get(
                    "organizationName"
                ),
                "tags": [],
                "fieldSources": {"organizationName": "provider", "tags": None},
                "industry": None,
                "application": None,
                "channel": None,
            },
            "summary": stats,
            "signals": signal,
            "rhythm": {
                "trend": self.trend(rows),
                "hourlyTrend": (
                    self.trend(rows, granularity="hour")
                    if self.end - self.start <= timedelta(days=7)
                    else None
                ),
                "previousTrend": None,
                "previousHourlyTrend": None,
                "asOf": self.end.isoformat(),
                "lastObservedAt": last,
                "activeDays": len({self.dimension(x, "date") for x in rows}),
                "daysSinceLastObserved": (
                    (self.end - parse_time(last)).total_seconds() / 86400
                    if last
                    else None
                ),
                "comparisonReason": "前期尚未读取",
            },
            "members": members,
            "models": models,
            "participation": {
                "activeUserCount": stats["distinctUsers"],
                "topKnownMemberShare": max(
                    (x["requestShare"] for x in members), default=None
                ),
                "applicationCount": None,
            },
            "topModelShare": max(
                (x["requestShare"] for x in models), default=None
            ),
            "experience": stats,
            "value": {
                "finance": None,
                "financeState": {"state": "UNAVAILABLE"},
                "cash": None,
                "grossMargin": None,
                "retention": None,
            },
            "workItem": signal["workItem"],
            "followups": [],
        }

    def schema(self):
        dimension = self.payload.get(
            "option_dimension",
            self.payload.get("optionDimension", "customerTenantId"),
        )
        if dimension not in DIMENSIONS:
            fail("INVALID_DIMENSION", 400)
        if dimension == "customerTenantId":
            options = [
                {"value": cid, "label": row["name"]}
                for cid, row in self.customers.items()
                if not self.selected or cid in self.selected
            ]
        elif dimension == "modelId":
            options = [
                {"value": mid, "label": label}
                for mid, label in self.models.items()
            ]
        else:
            values = sorted(
                {self.dimension(x, dimension) for x in self.global_rows}
            )
            options = [
                {"value": value, "label": self.label(dimension, value)}
                for value in values
            ]
        search = self.payload.get("search", "").casefold()
        options = [
            x
            for x in options
            if search in (x["label"] + " " + x["value"]).casefold()
        ]
        counts = defaultdict(int)
        for row in self.global_rows:
            counts[self.dimension(row, dimension)] += 1
        options = [
            {
                "id": row["value"],
                "label": row["label"],
                "requestCount": counts[row["value"]],
            }
            for row in options
        ]
        options.sort(key=lambda row: (-row["requestCount"], row["id"]))
        return {
            "dimensions": list(DIMENSIONS),
            "metrics": list(METRICS),
            "unavailableMetrics": {"p95LatencyMs": "UNIT_UNCONFIRMED"},
            "unsupportedDimensions": ["application", "industry", "channel"],
            "options": self.page(options),
        }
