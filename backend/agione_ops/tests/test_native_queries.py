"""Native business operations must stay direct, scoped and nonpersistent."""

import json
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from agione_ops.client import AgioneOpsError
from agione_ops.native_analytics import normalize_log, summary
from agione_ops.native_finance import aggregate_finance, finance_for_window
from agione_ops import native_queries as module

CID = "90071992547409931234"
OTHER = "90071992547409939999"
MID = "90071992547409930001"
START = "2026-10-01T00:00:00+08:00"
END = "2026-10-02T00:00:00+08:00"
STAMP = int(datetime(2026, 10, 1, 2, tzinfo=timezone.utc).timestamp() * 1000)


def test_finance_request_retries_transient_errors_only(monkeypatch):
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise AgioneOpsError("SOURCE_TIMEOUT", status_code=504)
        return "ok"

    assert module.retry_finance_request(flaky) == "ok"
    assert len(calls) == 3
    calls.clear()

    def forbidden():
        calls.append(1)
        raise AgioneOpsError("SOURCE_FORBIDDEN", status_code=403)

    with pytest.raises(AgioneOpsError):
        module.retry_finance_request(forbidden)
    assert len(calls) == 1
    calls.clear()

    def timed_out():
        calls.append(1)
        raise AgioneOpsError("SOURCE_TIMEOUT", status_code=504)

    with pytest.raises(AgioneOpsError):
        module.retry_finance_request(timed_out)
    assert len(calls) == 3


def test_finance_checkpoint_contains_only_normalized_customer_data():
    accounts = [{"id": "700", "tenantId": CID,
                 "accountPurpose": "USER_AVAILABLE", "currency": "Credit",
                 "balance": "12", "private": "SECRET"}]
    overview = {"tenantId": CID, "currentCycle": "2026-10",
                "cycleConsumedCredit": "2", "private": "SECRET",
                "trend": [{"date": "2026-10-01", "consumedCredit": "2",
                           "topUpCredit": "1", "private": "SECRET"}]}
    previous = {"tenantId": CID, "trend": [{"date": "2026-09-30",
                "consumedCredit": "1", "topUpCredit": "0"}]}
    saved = module.finance_checkpoint(
        CID, accounts, overview, previous, {"orders": [],
        "successfulCount": 0, "paidTotals": []}, "2026-10", "2026-09",
        "2026-10-01T00:00:00+00:00",
    )
    assert "SECRET" not in json.dumps(saved)
    assert saved[1][0]["balance"] == "12"
    assert saved[2]["trend"][0]["consumedCredit"] == "2"
    assert saved[3]["trend"][0]["consumedCredit"] == "1"


def test_batch_balance_requires_complete_fresh_directory():
    from datetime import timedelta
    from agione_ops.native_queries import batch_balance

    now = datetime(2026, 11, 1, 8, tzinfo=timezone.utc)
    rows = [{"tenantId": CID, "snapshotSyncTime": int(now.timestamp() * 1000),
             "balances": [{"currency": "Credit", "balance": "-3.25"}]}]
    result = batch_balance(rows, {CID}, now)
    assert result["balanceDistributions"][0]["negativeCustomers"] == 1
    assert result["oldestReadAt"] == now.isoformat()
    assert result["periodSummaries"] == []
    assert result["partial"] is True
    window = finance_for_window(result, now - timedelta(days=1), now)
    assert window["balanceSnapshotOnly"] is True
    assert window["periodSummaries"] == []
    assert batch_balance(rows, {CID, OTHER}, now) is None
    stale = [{**rows[0], "snapshotSyncTime": int(
        (now - timedelta(hours=4)).timestamp() * 1000
    )}]
    assert batch_balance(stale, {CID}, now) is None
    assert batch_balance([{**rows[0], "balances": []}], {CID}, now) is None


def test_automatic_finance_cache_is_scoped_and_manual_bypasses(
    monkeypatch, settings,
):
    from django.core.cache import cache

    settings.CACHES = {"default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "agione-finance-cache-test",
    }}
    cache.clear()
    operator = SimpleNamespace(
        pk="operator", platform="pro", principal_kind="operator",
        config_version=1, credential_version=1, endpoint="https://example.test",
    )
    user = SimpleNamespace(pk=1)
    calls = []
    monkeypatch.setattr(
        "agione_ops.tenant_directory.classification_version",
        lambda *args: "version",
    )
    monkeypatch.setattr(module, "connections_for", lambda *args: SimpleNamespace(
        filter=lambda **kwargs: [operator],
    ))
    monkeypatch.setattr(module, "_legacy_live_operation", lambda *args, **kwargs: (
        calls.append(1) or {"data": {"available": True, "partial": False}}
    ))
    clock = [datetime(2026, 10, 31, 15, 59, tzinfo=timezone.utc)]
    monkeypatch.setattr(module.timezone, "now", lambda: clock[0])
    module.collect_native_finance(operator, user, reuse_cache=True)
    module.collect_native_finance(operator, user, reuse_cache=True)
    assert len(calls) == 1
    module.collect_native_finance(operator, SimpleNamespace(pk=2), reuse_cache=True)
    operator.credential_version = 2
    module.collect_native_finance(operator, user, reuse_cache=True)
    module.collect_native_finance(operator, user)
    assert len(calls) == 4
    clock[0] = datetime(2026, 10, 31, 16, 1, tzinfo=timezone.utc)
    module.collect_native_finance(operator, user, reuse_cache=True)
    assert len(calls) == 5


@pytest.fixture
def live(monkeypatch, settings):
    settings.AGIONE_OPS_NATIVE_ENABLED = True
    state = {
        "denied": set(),
        "calls": [],
        "clients": [],
        "mutation": None,
        "identity_mismatch": False,
        "directory_total": None,
        "financial_owner": CID,
        "operator": True,
    }
    connections = {}
    for role in ("provider", "operator"):
        connections[role] = SimpleNamespace(
            pk=role,
            id=role,
            platform="pro",
            principal_kind=role,
            source_kind="native",
            endpoint="https://allowed.example",
            expected_tenant_id="111" if role == "provider" else "222",
            config_version=1,
            credential_version=1,
            enabled=True,
        )
    state["connections"] = connections
    monkeypatch.setattr(
        "agione_ops.tenant_directory.operator_overrides", lambda operator: {},
    )
    state["rows"] = [
        {
            "id": "90071992547409930002",
            "customerTenantId": CID,
            "modelId": MID,
            "userId": "90071992547409930003",
            "createTime": STAMP,
            "status": 1,
            "promptTokens": 10,
            "completionTokens": 5,
            "totalTokens": 15,
            "prompt": "PRIVATE",
            "raw": {"Authorization": "PRIVATE"},
        },
        {
            "id": "90071992547409930004",
            "customerTenantId": CID,
            "modelId": MID,
            "userId": "90071992547409930003",
            "createTime": STAMP + 1000,
            "status": 0,
            "failureType": 3,
        },
        {
            "id": "90071992547409930005",
            "customerTenantId": OTHER,
            "modelId": MID,
            "createTime": STAMP,
            "status": 1,
            "promptTokens": 99999,
            "customerName": "PRIVATE",
        },
    ]

    def permission(user, pk, action):
        assert action == "view_business"
        if pk in state["denied"]:
            raise AgioneOpsError("not_found", status_code=404)
        return connections[pk]

    class Allowed:
        def filter(self, **kwargs):
            return [
                x
                for x in connections.values()
                if all(getattr(x, k) == v for k, v in kwargs.items())
                and x.pk not in state["denied"]
                and (state["operator"] or x.principal_kind != "operator")
            ]

    monkeypatch.setattr(module, "get_connection_for", permission)
    monkeypatch.setattr(module, "connections_for", lambda *a: Allowed())

    class Client:
        def __init__(self, connection):
            self.connection, self.closed = connection, False
            state["clients"].append(self)

        def identity(self):
            c = self.connection
            state["calls"].append((c.pk, "identity", None))
            return {
                "tenant_id": (
                    "wrong"
                    if state["identity_mismatch"]
                    else c.expected_tenant_id
                ),
                "platform": c.platform,
                "principal_kind": c.principal_kind,
                "role_verified": True,
                "role_state": "verified",
            }

        def get(self, path, params=None):
            state["calls"].append((self.connection.pk, path, params))
            if state["mutation"]:
                state["mutation"](path)
            if path.endswith("op-customer-overviews"):
                if state.get("batch_error"):
                    raise AgioneOpsError("SOURCE_REJECTED", status_code=502)
                rows = state.get("batch", [])
                return {"data": deepcopy(rows), "total": len(rows)}
            if path.startswith("/coperation/tenant/"):
                key = (
                    "tenantId"
                    if self.connection.principal_kind == "operator"
                    else "customerTenantId"
                )
                page = params["pageIndex"]
                rows = (
                    [
                        {
                            key: CID,
                            "customerName": "Business Organization",
                            "organizationName": "Business Organization",
                            "contact": "PRIVATE",
                        }
                    ]
                    if page == 1
                    else []
                )
                return {
                    "data": rows,
                    "total": (
                        state["directory_total"]
                        if state["directory_total"] is not None
                        else len(rows)
                    ),
                }
            if path.endswith("models/options"):
                return [{"id": MID, "modelName": "Model", "apiKey": "PRIVATE"}]
            if path.endswith("call-logs"):
                page = params["current"]
                size = params["size"]
                start = (page - 1) * size
                return {
                    "records": deepcopy(state["rows"][start : start + size]),
                    "total": len(state["rows"]),
                }
            if path.endswith("/accounts"):
                return [
                    {
                        "id": "700",
                        "tenantId": state["financial_owner"],
                        "accountPurpose": "USER_AVAILABLE",
                        "currency": "Credit",
                        "balance": "-3.25",
                        "private": "PRIVATE",
                    }
                ]
            if path.endswith("/overview"):
                if params.get("range") == "lastMonth" and "previous" in state:
                    return deepcopy(state["previous"])
                return {
                    "tenantId": CID,
                    "currentCycle": "2026-10",
                    "cycleConsumedCredit": "5.50",
                    "cycleTopUpCredit": None,
                    "cycleAdjustmentCredit": None,
                    "cycleRoundOffCredit": None,
                }
            raise AssertionError(path)

        def page(self, path, params=None, **kwargs):
            assert path == "/financial/account/recharge/pageQuery"
            return {"items": deepcopy(state.get("recharges", []))}

        def close(self):
            self.closed = True

    def query(operation="analysis", payload=None, **extra):
        return module._legacy_live_operation(
            connections["provider"],
            object(),
            {
                "operation": operation,
                "window": {"start": START, "endExclusive": END},
                "payload": payload or {},
                **extra,
            },
            client_factory=Client,
        )

    state["query"] = query
    return state


def test_native_analysis_is_fresh_complete_and_excludes_unknown_customers(
    live,
):
    result = live["query"]()
    assert result["data"]["summary"]["requestCount"] == 2
    assert result["data"]["rows"][0]["groupKey"] == {"customerTenantId": CID}
    assert result["coverage"]["quarantinedRecordCount"] == 1
    assert result["coverage"]["pagingComplete"] is True
    assert result["provenance"]["transport"] == "direct_upstream"
    assert "dataVersion" not in result
    assert "PRIVATE" not in json.dumps(result)
    assert OTHER not in json.dumps(result)
    first = len(live["calls"])
    live["rows"][0]["promptTokens"] = 22
    newer = live["query"]()
    assert len(live["calls"]) > first
    assert newer["data"]["summary"]["inputTokens"] == 22
    assert all(x.closed for x in live["clients"])


def test_provider_own_tenant_is_in_scope_even_when_directory_omits_it(live):
    live["connections"]["provider"].expected_tenant_id = OTHER
    result = live["query"]("dashboard")
    assert result["data"]["summary"]["requestCount"] == 3
    assert result["coverage"]["directoryTotal"] == 1
    assert result["coverage"]["quarantinedRecordCount"] == 0


@pytest.mark.parametrize(
    "operation",
    [
        "dashboard",
        "schema",
        "analysis",
        "trend",
        "customers",
        "profile",
        "requests",
        "evidence",
    ],
)
def test_all_named_operations_have_live_business_dto(live, operation):
    payload = {
        "profile": {"customerId": CID},
        "evidence": {"evidenceId": "90071992547409930002"},
    }.get(operation, {})
    result = live["query"](operation, payload)
    assert result["operation"] == operation
    assert result["capabilities"]["directUpstream"] is True
    assert result["coverage"]["mode"] == "live"
    assert result["data"] is not None
    assert "PRIVATE" not in json.dumps(result)


def test_dashboard_does_not_block_on_independent_finance(live):
    result = live["query"]("dashboard")
    assert "finance" not in result["data"]
    assert not any("/financial/" in path for _, path, _ in live["calls"])


def test_operator_finance_reads_directory_once(live):
    live["query"]("dashboard")
    factory = type(live["clients"][0])
    live["calls"].clear()
    result = module._legacy_live_operation(
        live["connections"]["operator"], object(),
        {"operation": "finance", "window": {
            "start": START, "endExclusive": END,
        }, "payload": {}},
        client_factory=factory,
    )
    assert result["data"]["available"]
    assert sum(path.endswith("op-customers")
               for _, path, _ in live["calls"]) == 1


def test_finance_fast_balance_and_batch_error_fallback(live):
    from django.utils import timezone as django_timezone

    live["query"]("dashboard")
    factory = type(live["clients"][0])
    live["batch"] = [{
        "tenantId": CID,
        "snapshotSyncTime": int(django_timezone.now().timestamp() * 1000),
        "balances": [{"currency": "Credit", "balance": "12"}],
    }]
    query = {"operation": "finance", "window": {
        "start": START, "endExclusive": END,
    }, "payload": {}}
    early = []
    full = module._legacy_live_operation(
        live["connections"]["operator"], object(), query,
        client_factory=factory, on_balance=early.append,
    )["data"]
    assert early[0]["balances"][0]["value"] == "12"
    assert full["balances"][0]["value"] == "-3.25"
    assert full["partial"] is False
    live["batch_error"] = True
    early.clear()
    full = module._legacy_live_operation(
        live["connections"]["operator"], object(), query,
        client_factory=factory, on_balance=early.append,
    )["data"]
    assert not early
    assert full["balances"][0]["value"] == "-3.25"


def test_finance_retry_reuses_completed_customer_only_for_same_task(live, settings):
    from django.core.cache import cache

    settings.CACHES = {"default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "agione-finance-resume-test",
    }}
    cache.clear()
    live["query"]("dashboard")
    factory = type(live["clients"][0])
    query = {"operation": "finance", "window": {
        "start": START, "endExclusive": END,
    }, "payload": {}}
    args = (live["connections"]["operator"], SimpleNamespace(pk=123), query)
    live["calls"].clear()
    first = module._legacy_live_operation(
        *args, client_factory=factory, checkpoint_scope="task-a",
    )["data"]
    second = module._legacy_live_operation(
        *args, client_factory=factory, checkpoint_scope="task-a",
    )["data"]
    assert first["balances"] == second["balances"]
    assert sum(path.endswith("/accounts") for _, path, _ in live["calls"]) == 1
    module._legacy_live_operation(
        *args, client_factory=factory, checkpoint_scope="task-b",
    )
    assert sum(path.endswith("/accounts") for _, path, _ in live["calls"]) == 2


def test_finance_timings_are_aggregated_without_customer_ids(
    live, settings, caplog,
):
    import logging

    settings.AGIONE_OPS_FINANCE_CONCURRENCY = 1
    with caplog.at_level(logging.INFO, logger=module.__name__):
        live["query"]("finance")
    message = next(
        record.getMessage() for record in caplog.records
        if "AGIOne finance request timing" in record.getMessage()
    )
    assert "workers=1" in message
    assert "accounts" in message and "recharge" in message
    assert CID not in message


def test_automatic_finance_reuses_valid_previous_month_only(live, settings):
    from datetime import timedelta
    from django.core.cache import cache
    from django.utils import timezone as django_timezone

    settings.CACHES = {"default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "agione-history-test",
    }}
    cache.clear()
    live["query"]("dashboard")
    factory = type(live["clients"][0])
    previous = django_timezone.localdate().replace(day=1) - timedelta(days=1)
    live["previous"] = {
        "tenantId": CID,
        "trend": [{"date": previous.isoformat(),
                   "consumedCredit": "4.50", "topUpCredit": "1"}],
    }
    query = {"operation": "finance", "window": {
        "start": START, "endExclusive": END,
    }, "payload": {}}
    operator = live["connections"]["operator"]
    user = SimpleNamespace(pk=123)
    live["calls"].clear()
    first = module._legacy_live_operation(
        operator, user, query, client_factory=factory, historical_cache=True,
    )["data"]
    second = module._legacy_live_operation(
        operator, user, query, client_factory=factory, historical_cache=True,
    )["data"]
    assert first["trend"] == second["trend"]
    assert sum(bool(params and params.get("range") == "lastMonth")
               for _, _, params in live["calls"]) == 1
    module._legacy_live_operation(operator, user, query, client_factory=factory)
    assert sum(bool(params and params.get("range") == "lastMonth")
               for _, _, params in live["calls"]) == 2


def test_manual_finance_populates_history_without_using_stale_history(
    live, settings,
):
    from datetime import timedelta
    from django.core.cache import cache
    from django.utils import timezone as django_timezone

    settings.CACHES = {"default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "agione-manual-history-test",
    }}
    cache.clear()
    live["query"]("dashboard")
    factory = type(live["clients"][0])
    previous = django_timezone.localdate().replace(day=1) - timedelta(days=1)
    live["previous"] = {"tenantId": CID, "trend": [{
        "date": previous.isoformat(), "consumedCredit": "4.50",
        "topUpCredit": "1",
    }]}
    query = {"operation": "finance", "window": {
        "start": START, "endExclusive": END,
    }, "payload": {}}
    args = (live["connections"]["operator"], SimpleNamespace(pk=123), query)
    live["calls"].clear()
    module._legacy_live_operation(*args, client_factory=factory,
                                  history_write=True)
    automatic = module._legacy_live_operation(
        *args, client_factory=factory, historical_cache=True,
        history_write=True,
    )["data"]
    assert automatic["trend"][0]["value"] == "4.50"
    assert sum(bool(params and params.get("range") == "lastMonth")
               for _, _, params in live["calls"]) == 1
    live["previous"]["trend"][0]["consumedCredit"] = "8.50"
    manual = module._legacy_live_operation(
        *args, client_factory=factory, history_write=True,
    )["data"]
    assert manual["trend"][0]["value"] == "8.50"
    assert sum(bool(params and params.get("range") == "lastMonth")
               for _, _, params in live["calls"]) == 2
    updated = module._legacy_live_operation(
        *args, client_factory=factory, historical_cache=True,
    )["data"]
    assert updated["trend"][0]["value"] == "8.50"
    other = (args[0], SimpleNamespace(pk=456), query)
    module._legacy_live_operation(*other, client_factory=factory,
                                  historical_cache=True)
    assert sum(bool(params and params.get("range") == "lastMonth")
               for _, _, params in live["calls"]) == 3


def test_large_log_windows_read_all_pages_with_isolated_clients(live):
    template = live["rows"][0]
    live["rows"] = [
        {**template, "id": str(90071992547409930000 + index)}
        for index in range(1001)
    ]
    result = live["query"]("dashboard")
    assert result["data"]["summary"]["requestCount"] == 1001
    assert result["coverage"]["sourceRecordCount"] == 1001
    assert result["coverage"]["pagesRead"] == 4
    assert len(live["clients"]) == 3


def test_usage_missing_is_unknown_not_zero_and_latency_is_not_fabricated(live):
    result = live["query"]("requests")
    failed = next(
        x for x in result["data"]["items"] if x["result"] == "FAILURE"
    )
    assert failed["input_tokens"] is None
    assert failed["latencyState"] == "UNIT_UNCONFIRMED"
    assert "raw" not in failed
    assert result["data"]["summary"]["inputTokensCoverage"] == 0.5


def test_schema_uses_original_options_items_ids_and_paging(live):
    result = live["query"]("schema", {"optionDimension": "customerTenantId"})
    assert result["data"]["options"]["items"] == [
        {"id": CID, "label": "Business Organization", "requestCount": 2},
        {"id": "111", "label": "111", "requestCount": 0},
    ]


@pytest.mark.parametrize(
    "operation,payload",
    [
        ("profile", {"customerId": OTHER}),
        ("evidence", {"evidenceId": "90071992547409930005"}),
        ("finance", {"customerId": OTHER}),
    ],
)
def test_other_customer_cannot_escape_scope(live, operation, payload):
    with pytest.raises(AgioneOpsError):
        live["query"](operation, payload)


def test_customer_selection_must_be_nonempty_confirmed_subset(live):
    for ids in ([], [OTHER]):
        with pytest.raises(AgioneOpsError):
            live["query"](customerIds=ids)


def test_finance_requires_separate_operator_grant(live):
    live["operator"] = False
    result = live["query"]("finance")
    assert result["data"]["reason"] == "OPERATOR_VIEW_REQUIRED"
    assert not any("/financial/" in path for _, path, _ in live["calls"])


def test_finance_presents_new_fields_without_raw_accounts(live):
    result = live["query"]("finance")["data"]
    assert result["balanceDistributions"][0]["negativeTotal"] == "3.25"
    assert result["balanceDistributions"][0]["negativeCustomers"] == 1
    assert result["periodSummaries"][0]["consumed"] == "5.50"
    assert result["periodSummaries"][0]["topUp"] is None
    assert result["partial"] is False
    assert "accounts" not in result
    assert "PRIVATE" not in json.dumps(result)


def test_recharge_totals_require_customer_ownership(live):
    live["recharges"] = [
        {"orderNo": "1", "tenantId": CID, "status": 3,
         "payAmt": "0", "payCurrency": "USD", "payChannel": "SystemGift",
         "payTime": 1789703422000, "adminEmail": "PRIVATE"},
        {"orderNo": "2", "tenantId": CID, "status": 3,
         "payAmt": "12.50", "payCurrency": "USD", "payTime": 1789703423000},
    ]
    data = live["query"]("finance")["data"]["customerFinance"][CID]["recharge"]
    assert data["successfulCount"] == 2
    assert data["paidTotals"] == [{"currency": "USD", "amount": "12.50"}]
    assert "PRIVATE" not in json.dumps(data)
    live["recharges"][0]["tenantId"] = OTHER
    customer = live["query"]("finance")["data"]["customerFinance"][CID]
    assert customer["recharge"] is None
    assert customer["rechargeError"] == "SOURCE_SHAPE_CHANGED"


def test_finance_date_filter_uses_complete_daily_values_only():
    records = [
        ("100", [], {"currentCycle": "2026-10", "trend": [
            {"date": "2026-10-01", "consumedCredit": "1.25", "topUpCredit": "10"},
            {"date": "2026-10-02", "consumedCredit": "2"},
        ]}),
        ("200", [], {"currentCycle": "2026-10", "trend": [
            {"date": "2026-10-01", "consumedCredit": "3", "topUpCredit": "5.50"},
            {"date": "2026-10-02", "consumedCredit": "4.50"},
        ]}),
    ]
    finance = aggregate_finance(records, 2, "2026-10", START)
    start = datetime.fromisoformat("2026-10-01T00:00:00+08:00")
    end = datetime.fromisoformat("2026-10-02T00:00:00+08:00")
    selected = finance_for_window(finance, start, end)["periodSummaries"][0]
    assert selected["consumed"] == "4.25"
    assert selected["topUp"] == "15.50"
    assert selected["adjustment"] is None
    missing = finance_for_window(
        finance, start, datetime.fromisoformat("2026-10-04T00:00:00+08:00")
    )["periodSummaries"][0]
    assert missing["consumed"] is None
    records[1][2]["trend"].pop()
    assert aggregate_finance(records, 2, "2026-10", START)["trend"] == []


def test_finance_reads_previous_month_using_trend_dates(live):
    from datetime import timedelta

    from django.utils import timezone
    from zoneinfo import ZoneInfo

    today = timezone.now().astimezone(ZoneInfo("Asia/Shanghai")).date()
    previous = today.replace(day=1) - timedelta(days=1)
    live["previous"] = {
        "tenantId": CID,
        "currentCycle": today.strftime("%Y-%m"),
        "trend": [{"date": previous.isoformat(), "consumedCredit": "4.50",
                   "topUpCredit": "10"}],
    }
    result = live["query"]("finance")["data"]
    assert result["trend"] == [{"date": previous.isoformat(),
                                "value": "4.50", "topUp": "10"}]
    start = datetime.fromisoformat(f"{previous.isoformat()}T00:00:00+08:00")
    selected = finance_for_window(result, start, start + timedelta(days=1))
    assert selected["periodSummaries"][0]["consumed"] == "4.50"
    assert selected["periodSummaries"][0]["topUp"] == "10"


def test_finance_customer_ownership_is_verified(live):
    live["financial_owner"] = OTHER
    with pytest.raises(AgioneOpsError) as error:
        live["query"]("finance")
    assert error.value.code == "SOURCE_CUSTOMER_MISMATCH"


def test_acl_revocation_during_io_suppresses_response(live):
    def revoke(path):
        if path.endswith("call-logs"):
            live["denied"].add("provider")

    live["mutation"] = revoke
    with pytest.raises(AgioneOpsError):
        live["query"]()
    assert all(x.closed for x in live["clients"])


def test_config_or_credential_epoch_change_during_io_suppresses_response(live):
    def rotate(path):
        if path.endswith("call-logs"):
            live["connections"]["provider"].credential_version += 1

    live["mutation"] = rotate
    with pytest.raises(AgioneOpsError) as error:
        live["query"]()
    assert error.value.code == "CONNECTION_CHANGED"


def test_identity_mismatch_closes_transport_before_business(live):
    live["identity_mismatch"] = True
    with pytest.raises(AgioneOpsError) as error:
        live["query"]()
    assert error.value.code == "SOURCE_IDENTITY_MISMATCH"
    assert all(x.closed for x in live["clients"])
    assert len(live["calls"]) == 1


def test_incomplete_directory_never_returns_fake_complete_data(live):
    live["directory_total"] = 2
    with pytest.raises(AgioneOpsError) as error:
        live["query"]()
    assert error.value.code in {
        "SOURCE_CHANGED_DURING_PAGING",
        "SOURCE_INCOMPLETE_PAGING",
    }


def test_bounded_total_and_duplicate_pages_fail_closed(live):
    live["directory_total"] = 20001
    with pytest.raises(AgioneOpsError) as error:
        live["query"]()
    assert error.value.code == "SOURCE_PAGE_LIMIT"


def test_old_snapshot_versions_are_not_accepted(live):
    with pytest.raises(AgioneOpsError) as error:
        live["query"](dataVersion="old-version")
    assert error.value.code == "LIVE_VERSION_NOT_SUPPORTED"


def test_pure_finance_pagination_exposes_partial_not_full_coverage():
    result = aggregate_finance(
        [
            (
                CID,
                [
                    {
                        "id": "1",
                        "tenantId": CID,
                        "accountPurpose": "USER_AVAILABLE",
                        "currency": "Credit",
                        "balance": "100",
                    }
                ],
                {"tenantId": CID},
            )
        ],
        148,
        "2026-10",
        START,
    )
    assert result["partial"] is True
    assert result["nextOffset"] == 1
    assert result["totalCustomers"] == 148
    assert result["balanceDistributions"][0]["healthyCustomers"] == 1


def test_empty_and_unknown_usage_are_distinguished():
    row = normalize_log(
        {"id": "1", "customerTenantId": CID, "createTime": STAMP, "status": 1},
        module.parse_time(START),
        module.parse_time(END),
    )
    assert summary([row])["totalTokens"] is None
    assert summary([])["requestCount"] == 0
    assert summary([])["successRate"] is None


def test_customer_analytics_groups_rows_once():
    from agione_ops.native_analytics import LiveAnalytics

    class CountedRow(dict):
        reads = 0

        def __getitem__(self, key):
            if key == "customer_id":
                type(self).reads += 1
            return super().__getitem__(key)

    rows = [CountedRow(normalize_log({
        "id": str(1000 + i), "customerTenantId": str(10 + i % 10),
        "createTime": STAMP, "status": 1,
    }, module.parse_time(START), module.parse_time(END))) for i in range(100)]
    customers = {str(10 + i): {"name": str(i)} for i in range(10)}
    engine = LiveAnalytics(customers, {}, rows, None, None, {})
    CountedRow.reads = 0
    results = engine.customer_rows()
    assert sum(row["summary"]["requestCount"] for row in results) == 100
    assert CountedRow.reads < 500


def test_dashboard_observations_use_complete_scoped_windows():
    from agione_ops.native_analytics import LiveAnalytics
    from agione_ops.native_snapshot_queries import apply_dashboard_observations

    start = module.parse_time("2026-10-20T00:00:00+08:00")
    end = module.parse_time("2026-10-27T00:00:00+08:00")
    old = module.parse_time("2026-10-13T00:00:00+08:00")
    customers = {CID: {"name": "Test"}}
    def record(identifier, at):
        return normalize_log({"id": identifier, "customerTenantId": CID,
                              "occurred_at": at, "status": 1}, old, end)
    current = LiveAnalytics(customers, {}, [record("1", "2026-10-20T12:00:00+08:00")], start, end, {})
    prior = LiveAnalytics(customers, {}, [record(str(i), "2026-10-14T12:00:00+08:00") for i in range(2, 6)], old, start, {})
    data = current.dashboard()
    apply_dashboard_observations(data, current, prior, {"pagingComplete": True})
    row = data["customers"][0]
    assert row["changePercent"] == -75
    assert row["inactivity"]["daysWithoutCalls"] == 6
    assert data["comparison"]["summary"]["requestCount"] == 4
    filtered = LiveAnalytics(customers, {}, current.rows, start, end,
                             {"filters": {"statuses": ["FAILURE"]}})
    data = filtered.dashboard()
    apply_dashboard_observations(data, filtered, None, {"pagingComplete": True})
    assert data["customers"][0]["inactivity"]["state"] == "FILTER_NOT_APPLICABLE"
    assert data["comparison"]["state"] == "UNAVAILABLE"


def test_balance_tiers_use_40_and_80_boundaries():
    from agione_ops.native_finance import aggregate_finance

    values = ['-1', '0', '39.99', '40', '79.99', '80', '100']
    records = [(str(200 + i), [{
        'id': str(1000 + i), 'accountPurpose': 'USER_AVAILABLE',
        'currency': 'Credit', 'balance': value,
    }], {}) for i, value in enumerate(values)]
    result = aggregate_finance(records, len(records), '2026-10', START)
    tier = result['balanceDistributions'][0]
    assert tier['threshold'] == '40'
    assert tier['healthyCustomers'] == 2
    assert tier['normalCustomers'] == 2
    assert tier['lowCustomers'] == 1
    assert tier['zeroCustomers'] == 1
    assert tier['negativeCustomers'] == 1
    assert tier['belowThresholdCustomers'] == 3


def test_legacy_balance_snapshot_is_reclassified_only_with_complete_accounts():
    from agione_ops.native_finance import current_balance_policy

    old = {'balanceDistributions': [{
        'unit': 'Credit', 'threshold': '100', 'healthyCustomers': 0,
        'lowCustomers': 2, 'zeroCustomers': 0, 'negativeCustomers': 0,
        'belowThresholdCustomers': 2, 'negativeTotal': '0',
    }], 'customerFinance': {
        '1': {'accounts': [{'accountPurpose': 'USER_AVAILABLE',
                            'currency': 'Credit', 'balance': '40'}]},
        '2': {'accounts': [{'accountPurpose': 'USER_AVAILABLE',
                            'currency': 'Credit', 'balance': '80'}]},
    }}
    result = current_balance_policy(old)['balanceDistributions'][0]
    assert result['threshold'] == '40'
    assert result['normalCustomers'] == result['healthyCustomers'] == 1
    assert old['balanceDistributions'][0]['threshold'] == '100'
    old['customerFinance'].pop('2')
    assert current_balance_policy(old)['balanceDistributions'] == []


def test_finance_excludes_internal_tenant_before_aggregation(live, monkeypatch):
    """Internal tenant balances and activity do not enter finance totals."""
    original = module.LiveSource.pages

    def pages(source, path, params=None, **kwargs):
        rows = original(source, path, params, **kwargs)
        if path.endswith("op-customers"):
            for row in rows:
                row["adminEmail"] = "internal@oneprocloud.cn"
        return rows

    monkeypatch.setattr(module.LiveSource, "pages", pages)
    result = live["query"]("finance")["data"]
    assert result["totalCustomers"] == 0
    assert result["balanceDistributions"] == []
    assert result["periodSummaries"] == []
    assert result["customerFinance"] == {}
    assert not any("/financial/api/finance/v1/admin/customers/" in path
                   for _, path, _ in live["calls"])


def test_tenant_name_uses_safe_admin_username_only_when_name_missing():
    from agione_ops.native_analytics import tenant_display_name

    assert tenant_display_name({"customerName": "客户", "adminUsername": "owner"}, "12") == "客户"
    assert tenant_display_name({"adminUsername": "owner"}, "12") == "owner"
    assert tenant_display_name({"adminUsername": "owner@example.com"}, "12") == "12"
    assert tenant_display_name(
        {"adminUsername": "owner@example.com"}, "12", allow_email=True,
    ) == "owner@example.com"
    assert tenant_display_name(
        {"adminUsername": "password@example.com"}, "12", allow_email=True,
    ) == "12"
    assert tenant_display_name({}, "12") == "12"


def test_calling_user_label_prefers_captured_name_and_falls_back_to_id():
    from agione_ops.native_analytics import LiveAnalytics

    engine = LiveAnalytics({}, {}, [], datetime.fromisoformat(START),
                           datetime.fromisoformat(END), {})
    engine.user_names = {"123:456": "Onepro"}
    assert engine.label("userId", "123:456") == "Onepro"
    assert engine.label("userId", "123:789") == "123:789"


def test_request_evidence_shows_known_caller_and_model_names():
    from agione_ops.native_analytics import LiveAnalytics

    row = {"customer_id": "123", "user_id": "456", "model_id": "789", "subject_type": "USER"}
    engine = LiveAnalytics({"123": {"name": "客户"}}, {"789": "模型"}, [], datetime.fromisoformat(START), datetime.fromisoformat(END), {})
    engine.user_names = {"123:456": "provider_onepro"}
    evidence = engine.evidence(row)
    assert evidence["userName"] == "provider_onepro"
    assert evidence["modelName"] == "模型"
    engine.user_names = {}
    assert engine.evidence(row)["userName"] == "456"


def test_hourly_distribution_uses_scoped_shanghai_time_and_distinct_customers():
    from agione_ops.native_analytics import LiveAnalytics

    start = datetime.fromisoformat("2026-10-01T00:00:00+08:00")
    end = datetime.fromisoformat("2026-10-03T00:00:00+08:00")
    def row(identifier, customer, at, model):
        return {
            "record_id": identifier, "customer_id": customer,
            "model_id": model, "user_id": None, "project_id": None,
            "subject_type": "USER", "occurred_at": at,
            "result": "SUCCESS", "failureKey": "NOT_APPLICABLE",
            "input_tokens": None, "output_tokens": None,
            "total_tokens": None,
        }
    rows = [
        row("1", "1", "2026-10-01T02:05:00+00:00", "7"),
        row("2", "1", "2026-10-02T10:20:00+08:00", "7"),
        row("3", "2", "2026-10-02T10:30:00+08:00", "7"),
        row("4", "2", "2026-10-02T11:30:00+08:00", "8"),
    ]
    engine = LiveAnalytics({"1": {"name": "A"}, "2": {"name": "B"}},
                           {}, rows, start, end,
                           {"filters": {"model_ids": ["7"]}})
    result = engine.hourly_distribution()
    assert result["dayCount"] == 2
    assert len(result["points"]) == 24
    assert result["points"][10] == {
        "hour": 10, "requestCount": 3, "activeCustomers": 2,
    }
    assert result["points"][11]["requestCount"] == 0
