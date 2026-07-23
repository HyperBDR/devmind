"""Tests for Data Ops executive overview metrics."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from data_ops.models import (
    Contract,
    DomesticLedger,
    OverseaProject,
    Project,
    ProjectInit,
    ProjectScope,
)
from data_ops.services.metrics.overview import (
    get_data_quality,
    get_domestic_ledger_kanban,
    get_executive_overview,
    get_opportunities,
    get_oversea_project_kanban,
    get_project_init_kanban,
    get_risks,
    get_summary,
    get_top_customers,
    get_top_sales,
    get_trends,
)
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _source_fields(record_id: str) -> dict:
    return {
        "source_record_id": record_id,
        "source_app_token": "app-token",
        "source_table_id": "table-id",
    }


def test_top_customers_combines_customer_business_metrics():
    Contract.objects.create(
        **_source_fields("contract-1"),
        contract_number="C-001",
        customer_name="Acme",
    )
    Contract.objects.create(
        **_source_fields("contract-2"),
        contract_number="C-002",
        customer_name="Acme",
    )
    Contract.objects.create(
        **_source_fields("contract-3"),
        contract_number="C-003",
        customer_name="Beta",
    )
    DomesticLedger.objects.create(
        **_source_fields("ledger-1"),
        ledger_type="收入",
        customer_name="Acme",
        currency="CNY",
        sales_person="Angela Wang",
        payment_received=Decimal("100"),
        outstanding=Decimal("25"),
    )
    DomesticLedger.objects.create(
        **_source_fields("ledger-2"),
        ledger_type="收入",
        customer_name="Acme",
        currency="CNY",
        sales_person="Judy Zhou",
        payment_received=Decimal("50"),
        outstanding=Decimal("5"),
    )
    DomesticLedger.objects.create(
        **_source_fields("ledger-3"),
        ledger_type="收入",
        customer_name="Beta",
        currency="CNY",
        sales_person="Betsy Zhao",
        payment_received=Decimal("80"),
        outstanding=Decimal("40"),
    )

    result = get_top_customers()

    assert result["top_received"][0] == {
        "customer_name": "Acme",
        "currency": "CNY",
        "sales_person": "Angela Wang、Judy Zhou",
        "received_amount": 150.0,
        "outstanding_amount": 30.0,
        "contract_count": 2,
        "risk_level": "medium",
    }
    assert result["top_outstanding"][0] == {
        "customer_name": "Beta",
        "currency": "CNY",
        "sales_person": "Betsy Zhao",
        "received_amount": 80.0,
        "outstanding_amount": 40.0,
        "contract_count": 1,
        "risk_level": "medium",
    }


def test_top_customers_does_not_flag_negative_outstanding_as_risk():
    DomesticLedger.objects.create(
        **_source_fields("ledger-credit"),
        ledger_type="收入",
        customer_name="Credit Customer",
        currency="CNY",
        payment_received=Decimal("100"),
        outstanding=Decimal("-10"),
    )

    result = get_top_customers()

    assert result["top_received"][0]["risk_level"] == "low"


def test_blank_currency_defaults_to_cny_and_merges_with_explicit_cny():
    DomesticLedger.objects.create(
        **_source_fields("ledger-default-currency"),
        ledger_type="收入",
        customer_name="Acme",
        payment_received=Decimal("100"),
        outstanding=Decimal("20"),
    )
    DomesticLedger.objects.create(
        **_source_fields("ledger-explicit-cny"),
        ledger_type="收入",
        customer_name="Acme",
        currency="CNY",
        payment_received=Decimal("50"),
        outstanding=Decimal("5"),
    )
    DomesticLedger.objects.create(
        **_source_fields("ledger-explicit-usd"),
        ledger_type="收入",
        customer_name="Acme",
        currency="USD",
        payment_received=Decimal("10"),
        outstanding=Decimal("1"),
    )

    summary = get_summary()
    customers = get_top_customers()

    assert summary["total_received_amount_by_currency"] == [
        {"currency": "CNY", "amount": 150.0},
        {"currency": "USD", "amount": 10.0},
    ]
    assert customers["top_received"][0]["currency"] == "CNY"
    assert customers["top_received"][0]["received_amount"] == 150.0


def test_data_quality_marks_mixed_currencies_as_limited():
    Contract.objects.create(
        **_source_fields("contract-cny"),
        currency="CNY",
        total_amount=Decimal("100"),
    )
    Contract.objects.create(
        **_source_fields("contract-usd"),
        currency="USD",
        total_amount=Decimal("10"),
    )

    result = get_data_quality()

    assert result["overall_status"] == "warning"
    assert result["analysis_status"] == "limited"
    assert result["sync_status"] == "ok"
    assert result["issues"][0]["id"] == "mixed-currency"


def test_executive_overview_calculates_ratios_and_month_over_month():
    today = timezone.localdate()
    current_month = today.replace(day=1)
    previous_month_end = current_month - timedelta(days=1)
    previous_month = previous_month_end.replace(day=1)
    Contract.objects.create(
        **_source_fields("contract-current"),
        signing_date=current_month,
        currency="CNY",
        total_amount=Decimal("120"),
    )
    Contract.objects.create(
        **_source_fields("contract-previous"),
        signing_date=previous_month,
        currency="CNY",
        total_amount=Decimal("100"),
    )
    DomesticLedger.objects.create(
        **_source_fields("income-current"),
        ledger_type="收入",
        receipt_time=current_month,
        currency="CNY",
        payment_received=Decimal("200"),
        outstanding=Decimal("30"),
    )
    DomesticLedger.objects.create(
        **_source_fields("income-previous"),
        ledger_type="收入",
        receipt_time=previous_month,
        currency="CNY",
        payment_received=Decimal("100"),
        outstanding=Decimal("20"),
    )
    DomesticLedger.objects.create(
        **_source_fields("expense-current"),
        ledger_type="支出",
        signing_date=current_month,
        currency="CNY",
        payment_amount=Decimal("50"),
    )
    DomesticLedger.objects.create(
        **_source_fields("expense-previous"),
        ledger_type="支出",
        signing_date=previous_month,
        currency="CNY",
        payment_amount=Decimal("25"),
    )

    result = get_executive_overview()

    assert result["kpis"]["expense_received_ratio"] == 25.0
    assert result["mom"]["monthly_signed_amount"] == 20.0
    assert result["mom"]["monthly_received_amount"] == 100.0
    assert result["mom"]["monthly_expense_amount"] == 100.0
    assert result["mom"]["expense_received_ratio"] == 0.0
    assert result["mom"]["monthly_outstanding_amount"] is None
    assert result["meta"]["previous_month"] == previous_month.strftime("%Y-%m")


def test_trends_calculate_net_quarterly_and_yearly_amounts():
    Contract.objects.create(
        **_source_fields("contract-january"),
        signing_date=date(2025, 1, 10),
        currency="CNY",
        total_amount=Decimal("100"),
    )
    Contract.objects.create(
        **_source_fields("contract-april"),
        signing_date=date(2025, 4, 10),
        currency="CNY",
        total_amount=Decimal("50"),
    )
    for suffix, ledger_date, received, expense in (
        ("january", date(2025, 1, 10), "80", "30"),
        ("april", date(2025, 4, 10), "20", "5"),
    ):
        DomesticLedger.objects.create(
            **_source_fields(f"income-{suffix}"),
            ledger_type="收入",
            receipt_time=ledger_date,
            currency="CNY",
            payment_received=Decimal(received),
        )
        DomesticLedger.objects.create(
            **_source_fields(f"expense-{suffix}"),
            ledger_type="支出",
            signing_date=ledger_date,
            currency="CNY",
            payment_amount=Decimal(expense),
        )

    result = get_trends()

    assert result["monthly_net"] == [
        {"month": "2025-01", "currency": "CNY", "amount": 50.0},
        {"month": "2025-04", "currency": "CNY", "amount": 15.0},
    ]
    assert result["quarterly_signed"] == [
        {"quarter": "2025-Q1", "currency": "CNY", "amount": 100.0},
        {"quarter": "2025-Q2", "currency": "CNY", "amount": 50.0},
    ]
    assert result["yearly_net"] == [
        {"year": "2025", "currency": "CNY", "amount": 65.0},
    ]


def test_top_sales_combines_amounts_customers_and_high_potential_projects():
    DomesticLedger.objects.create(
        **_source_fields("sales-income-1"),
        ledger_type="收入",
        customer_name="Acme",
        sales_person="Angela Wang",
        currency="CNY",
        payment_received=Decimal("100"),
        outstanding=Decimal("30"),
    )
    DomesticLedger.objects.create(
        **_source_fields("sales-income-2"),
        ledger_type="收入",
        customer_name="Beta",
        sales_person="Angela Wang",
        currency="CNY",
        payment_received=Decimal("50"),
    )
    Project.objects.create(
        **_source_fields("high-potential-project"),
        project_scope=ProjectScope.DOMESTIC,
        sales_person="Angela Wang",
        is_high_potential=True,
    )

    result = get_top_sales()

    expected = {
        "sales_person": "Angela Wang",
        "owner_open_ids": [],
        "owner_canonical": "Angela Wang",
        "owner_aliases": ["Angela Wang"],
        "owner_display": "Angela Wang",
        "currency": "CNY",
        "received_amount": 150.0,
        "outstanding_amount": 30.0,
        "customer_count": 2,
        "high_potential_count": 1,
        "risk_level": "medium",
    }
    assert result["top_received"][0] == expected
    assert result["top_outstanding"][0] == expected


def test_risks_use_due_dates_and_include_key_customer_risks():
    today = timezone.localdate()
    DomesticLedger.objects.create(
        **_source_fields("overdue-ledger"),
        ledger_type="收入",
        customer_name="Acme",
        sales_person="Angela Wang",
        currency="CNY",
        payment_received=Decimal("100"),
        outstanding=Decimal("30"),
        expected_payment_date=today - timedelta(days=1),
    )
    DomesticLedger.objects.create(
        **_source_fields("future-ledger"),
        ledger_type="收入",
        customer_name="Beta",
        sales_person="Judy Zhou",
        currency="CNY",
        payment_received=Decimal("50"),
        outstanding=Decimal("20"),
        expected_payment_date=today + timedelta(days=10),
    )

    result = get_risks()

    by_customer = {
        item["customer_name"]: item for item in result["high_outstanding_items"]
    }
    assert by_customer["Acme"]["risk_level"] == "high"
    assert by_customer["Beta"]["risk_level"] == "medium"
    assert result["summary"]["key_customer_risk_count"] == 2
    assert {item["customer_name"] for item in result["key_customer_risks"]} == {
        "Acme",
        "Beta",
    }


def test_legacy_kanban_endpoints_return_real_groups_and_filters():
    ProjectInit.objects.create(
        **_source_fields("project-init"),
        domestic_international="国内",
        sales_person="Angela Wang",
        currency="CNY",
        signing_party_type="直客",
    )
    OverseaProject.objects.create(
        **_source_fields("oversea-project"),
        country="Singapore",
        project_owner="Judy Zhou",
        currency="USD",
        product_type="License",
        order_status="Delivered",
    )
    DomesticLedger.objects.create(
        **_source_fields("kanban-ledger"),
        ledger_type="收入",
        sales_person="Angela Wang",
        signing_entity="OnePro",
        payment_status="部分回款",
        currency="CNY",
        total_contract_amount=Decimal("100"),
        payment_received=Decimal("60"),
        outstanding=Decimal("40"),
        year="2026",
    )

    project_init = get_project_init_kanban()
    oversea = get_oversea_project_kanban()
    ledger = get_domestic_ledger_kanban()

    assert project_init["filters"] == {
        "domestic_international": ["国内"],
        "sales_person": ["Angela Wang"],
        "currency": ["CNY"],
        "signing_party_type": ["直客"],
    }
    assert oversea["filters"]["country"] == ["Singapore"]
    assert oversea["filters"]["project_owner"] == ["Judy Zhou"]
    assert oversea["filters"]["currency"] == ["USD"]
    assert ledger["groups"] == [
        {
            "payment_status": "部分回款",
            "currency": "CNY",
            "record_count": 1,
            "total_contract_amount": 100.0,
            "payment_received": 60.0,
            "outstanding": 40.0,
        }
    ]
    assert ledger["filters"] == {
        "sales_person": ["Angela Wang"],
        "signing_entity": ["OnePro"],
        "payment_status": ["部分回款"],
        "currency": ["CNY"],
        "year": ["2026"],
    }


def test_summary_counts_are_not_capped_by_display_limits():
    today = timezone.localdate()
    Contract.objects.bulk_create(
        [
            Contract(
                **_source_fields(f"renewal-{index}"),
                service_end=today + timedelta(days=10),
            )
            for index in range(25)
        ]
    )
    DomesticLedger.objects.bulk_create(
        [
            DomesticLedger(
                **_source_fields(f"outstanding-{index}"),
                ledger_type="收入",
                outstanding=Decimal("1"),
            )
            for index in range(25)
        ]
    )
    ProjectInit.objects.bulk_create(
        [
            ProjectInit(
                **_source_fields(f"opportunity-{index}"),
                estimated_amount=Decimal("600000"),
            )
            for index in range(105)
        ]
    )
    ProjectInit.objects.bulk_create(
        [
            ProjectInit(
                **_source_fields(f"ordinary-project-{index}"),
                estimated_amount=Decimal("100"),
            )
            for index in range(400)
        ]
    )

    risks = get_risks()
    opportunities = get_opportunities()
    kanban = get_project_init_kanban()

    assert risks["summary"]["renewal_alert_count"] == 25
    assert len(risks["renewal_alerts"]) == 20
    assert risks["summary"]["high_outstanding_count"] == 25
    assert len(risks["high_outstanding_items"]) == 20
    assert opportunities["summary"]["high_potential_count"] == 105
    assert len(opportunities["items"]) == 100
    assert opportunities["summary"]["high_potential_total_amount"] == (63_000_000.0)
    assert kanban["total"] == 505
    assert len(kanban["cards"]) == 500
