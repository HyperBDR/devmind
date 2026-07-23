from datetime import timedelta
from decimal import Decimal

import pytest
from data_ops.models import (
    Contract,
    DomesticLedger,
    OverseaSettlement,
    Project,
    ProjectScope,
)
from data_ops.services.metrics.operations import (
    _monthly_net_trend,
    _monthly_payment_trend,
    get_pipeline_insights_data,
    get_pipeline_projects_data,
    get_pipeline_summary_data,
)
from data_ops.services.metrics.overview import get_summary, get_trends
from django.utils import timezone


@pytest.mark.django_db
def test_summary_keeps_amounts_bucketed_by_source_currency():
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="contracts",
        source_record_id="contract-cny",
        currency="CNY",
        total_amount=Decimal("100"),
    )
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="contracts",
        source_record_id="contract-usd",
        currency="USD",
        total_amount=Decimal("20"),
    )
    DomesticLedger.all_objects.create(
        source_app_token="app",
        source_table_id="ledger",
        source_record_id="ledger-cny",
        ledger_type="收入",
        currency="CNY",
        payment_received=Decimal("70"),
        outstanding=Decimal("30"),
    )
    DomesticLedger.all_objects.create(
        source_app_token="app",
        source_table_id="ledger",
        source_record_id="ledger-usd",
        ledger_type="收入",
        currency="USD",
        payment_received=Decimal("7"),
        outstanding=Decimal("3"),
    )

    summary = get_summary()

    assert summary["total_contract_amount"] is None
    assert summary["total_contract_amount_by_currency"] == [
        {"currency": "CNY", "amount": 100.0},
        {"currency": "USD", "amount": 20.0},
    ]
    assert summary["total_received_amount"] is None
    assert summary["total_received_amount_by_currency"] == [
        {"currency": "CNY", "amount": 70.0},
        {"currency": "USD", "amount": 7.0},
    ]


@pytest.mark.django_db
def test_trends_bucket_monthly_amounts_by_currency():
    today = timezone.localdate()
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="contracts",
        source_record_id="contract-cny",
        signing_date=today,
        currency="CNY",
        total_amount=Decimal("100"),
    )
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="contracts",
        source_record_id="contract-usd",
        signing_date=today,
        currency="USD",
        total_amount=Decimal("20"),
    )

    trends = get_trends()

    assert {
        "month": today.strftime("%Y-%m"),
        "currency": "CNY",
        "amount": 100.0,
    } in trends["monthly_signed"]
    assert {
        "month": today.strftime("%Y-%m"),
        "currency": "USD",
        "amount": 20.0,
    } in trends["monthly_signed"]


@pytest.mark.django_db
def test_settlement_trend_keeps_currency_buckets():
    today = timezone.localdate()
    OverseaSettlement.all_objects.create(
        source_app_token="app",
        source_table_id="settlement",
        source_record_id="settlement-cny",
        payment_date=today,
        currency="CNY",
        receivable_amount=Decimal("1000"),
        received_amount=Decimal("800"),
    )
    OverseaSettlement.all_objects.create(
        source_app_token="app",
        source_table_id="settlement",
        source_record_id="settlement-usd",
        payment_date=today,
        currency="USD",
        receivable_amount=Decimal("100"),
        received_amount=Decimal("90"),
    )

    insights = get_pipeline_insights_data()

    assert {
        "month": today.strftime("%Y-%m"),
        "currency": "CNY",
        "receivable_amount": 1000.0,
        "received_amount": 800.0,
    } in insights["settlement_receivable_trend"]
    assert {
        "month": today.strftime("%Y-%m"),
        "currency": "USD",
        "receivable_amount": 100.0,
        "received_amount": 90.0,
    } in insights["settlement_receivable_trend"]


@pytest.mark.django_db
def test_payment_trend_uses_receipt_or_expected_date_and_keeps_currency():
    today = timezone.localdate()
    next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
    DomesticLedger.all_objects.create(
        source_app_token="app",
        source_table_id="ledger",
        source_record_id="received-usd",
        ledger_type="收入",
        currency="USD",
        receipt_time=today,
        expected_payment_date=next_month,
        payment_received=Decimal("100"),
        outstanding=Decimal("0"),
    )
    DomesticLedger.all_objects.create(
        source_app_token="app",
        source_table_id="ledger",
        source_record_id="pending-cny",
        ledger_type="收入",
        currency="CNY",
        expected_payment_date=next_month,
        payment_received=Decimal("0"),
        outstanding=Decimal("800"),
    )
    DomesticLedger.all_objects.create(
        source_app_token="app",
        source_table_id="ledger",
        source_record_id="pending-default-currency",
        ledger_type="收入",
        expected_payment_date=next_month,
        payment_received=Decimal("0"),
        outstanding=Decimal("50"),
    )

    rows = _monthly_payment_trend()

    assert {
        "month": today.strftime("%Y-%m"),
        "currency": "USD",
        "payment_received": 100.0,
        "outstanding": 0.0,
    } in rows
    assert {
        "month": next_month.strftime("%Y-%m"),
        "currency": "CNY",
        "payment_received": 0.0,
        "outstanding": 850.0,
    } in rows


@pytest.mark.django_db
def test_net_trend_subtracts_expenses_from_received_by_currency():
    today = timezone.localdate()
    DomesticLedger.all_objects.create(
        source_app_token="app",
        source_table_id="ledger",
        source_record_id="net-income",
        ledger_type="收入",
        currency="CNY",
        receipt_time=today,
        payment_received=Decimal("100"),
    )
    DomesticLedger.all_objects.create(
        source_app_token="app",
        source_table_id="ledger",
        source_record_id="net-expense",
        ledger_type="支出",
        currency="CNY",
        signing_date=today,
        payment_amount=Decimal("30"),
    )

    rows = _monthly_net_trend()

    assert rows == [
        {
            "month": today.strftime("%Y-%m"),
            "currency": "CNY",
            "amount": 70.0,
        }
    ]


@pytest.mark.django_db
def test_pipeline_uses_source_display_amount_before_usd_stat_amount():
    Project.all_objects.create(
        source_app_token="app",
        source_table_id="projects",
        source_record_id="project-payment-usd",
        project_scope=ProjectScope.OVERSEAS,
        payment_amount=Decimal("1000"),
        payment_currency="USD",
        total_amount=Decimal("1200"),
        currency="EUR",
        stat_amount_usd=Decimal("700"),
    )
    Project.all_objects.create(
        source_app_token="app",
        source_table_id="projects",
        source_record_id="project-total-hkd",
        project_scope=ProjectScope.OVERSEAS,
        total_amount=Decimal("8000"),
        currency="HKD",
        stat_amount_usd=Decimal("900"),
    )
    Project.all_objects.create(
        source_app_token="app",
        source_table_id="projects",
        source_record_id="project-domestic-cny",
        project_scope=ProjectScope.DOMESTIC,
        estimated_amount=Decimal("500"),
        currency="CNY",
    )

    cards = get_pipeline_projects_data(
        scope="all",
        include_landed=True,
    )["cards"]
    summary = get_pipeline_summary_data()

    by_record = {item["source_record_id"]: item for item in cards}
    assert by_record["project-payment-usd"]["display_amount"] == 1000.0
    assert by_record["project-payment-usd"]["display_currency"] == "USD"
    assert by_record["project-total-hkd"]["display_amount"] == 8000.0
    assert by_record["project-total-hkd"]["display_currency"] == "HKD"
    assert summary["domestic_amount_by_currency"] == [
        {"currency": "CNY", "amount": 500.0},
    ]
    assert summary["oversea_amount_by_currency"] == [
        {"currency": "HKD", "amount": 8000.0},
        {"currency": "USD", "amount": 1000.0},
    ]


@pytest.mark.django_db
def test_pipeline_uses_business_scope_for_counts_and_amounts():
    today = timezone.localdate()
    Project.all_objects.create(
        source_app_token="app",
        source_table_id="projects",
        source_record_id="project-pure-overseas",
        project_scope=ProjectScope.DOMESTIC,
        domestic_type="纯海外项目",
        estimated_amount=Decimal("100"),
        currency="USD",
        license_expiry=today + timedelta(days=10),
    )
    Project.all_objects.create(
        source_app_token="app",
        source_table_id="projects",
        source_record_id="project-pure-domestic",
        project_scope=ProjectScope.DOMESTIC,
        domestic_type="纯国内项目",
        estimated_amount=Decimal("500"),
        currency="CNY",
    )

    summary = get_pipeline_summary_data()

    assert summary["domestic_projects"] == 1
    assert summary["oversea_projects"] == 1
    assert summary["domestic_amount_by_currency"] == [
        {"currency": "CNY", "amount": 500.0},
    ]
    assert summary["oversea_amount_by_currency"] == [
        {"currency": "USD", "amount": 100.0},
    ]
    assert summary["at_risk"] == 1
