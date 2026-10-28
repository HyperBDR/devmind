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
