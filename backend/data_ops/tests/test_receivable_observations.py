from datetime import date, timedelta
from decimal import Decimal

import pytest

from data_ops.models import (
    DomesticLedger,
    Evidence,
    KnowledgeProductionRun,
    Observation,
    ObservationEvidence,
)
from data_ops.services.knowledge.receivable_overdue import (
    produce_receivable_overdue_observations,
)


def _create_ledger(
    *,
    as_of,
    days_overdue=20,
    outstanding=Decimal("1250.5000"),
    currency="USD",
    source_record_id="ledger-1",
):
    return DomesticLedger.all_objects.create(
        source_app_token="app-token",
        source_table_id="domestic-ledger-table",
        source_record_id=source_record_id,
        source_content_hash="ledger-source-hash",
        ledger_type="收入",
        currency=currency,
        customer_name="Example Customer",
        project_name="Example Project",
        sales_person="Example Owner",
        outstanding=outstanding,
        expected_payment_date=as_of - timedelta(days=days_overdue),
    )


@pytest.mark.django_db
def test_receivable_producer_creates_traceable_observation():
    as_of = date(2026, 7, 20)
    ledger = _create_ledger(as_of=as_of)

    run = produce_receivable_overdue_observations(as_of=as_of)

    observation = Observation.objects.get()
    evidence = Evidence.objects.get()
    assert run.status == KnowledgeProductionRun.Status.SUCCEEDED
    assert run.result_counts == {
        "created": 1,
        "resolved": 0,
        "updated": 0,
    }
    assert observation.observation_type == "receivable_overdue_risk"
    assert observation.subject_type == "domestic_ledger"
    assert observation.subject_key == str(ledger.id)
    assert observation.structured_value == {
        "currency": "USD",
        "customer_name": "Example Customer",
        "days_overdue": 20,
        "expected_payment_date": "2026-06-30",
        "outstanding": "1250.5000",
        "project_name": "Example Project",
        "sales_person": "Example Owner",
    }
    assert observation.severity == Observation.Severity.MEDIUM
    assert evidence.source_model == "data_ops.DomesticLedger"
    assert evidence.source_object_id == str(ledger.id)
    assert evidence.snapshot["currency"] == "USD"
    assert evidence.snapshot["outstanding"] == "1250.5000"
    assert ObservationEvidence.objects.filter(
        observation=observation,
        evidence=evidence,
    ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("days_overdue", "severity"),
    [
        (1, Observation.Severity.LOW),
        (15, Observation.Severity.LOW),
        (16, Observation.Severity.MEDIUM),
        (30, Observation.Severity.MEDIUM),
        (31, Observation.Severity.HIGH),
        (60, Observation.Severity.HIGH),
        (61, Observation.Severity.CRITICAL),
    ],
)
def test_receivable_producer_assigns_severity_by_overdue_days(
    days_overdue,
    severity,
):
    as_of = date(2026, 7, 20)
    _create_ledger(as_of=as_of, days_overdue=days_overdue)

    produce_receivable_overdue_observations(as_of=as_of)

    assert Observation.objects.get().severity == severity


@pytest.mark.django_db
def test_receivable_producer_is_idempotent_and_recalculates_dates():
    as_of = date(2026, 7, 20)
    ledger = _create_ledger(as_of=as_of, days_overdue=10)
    first_run = produce_receivable_overdue_observations(as_of=as_of)

    ledger.expected_payment_date = as_of - timedelta(days=40)
    ledger.save(update_fields=["expected_payment_date"])
    second_run = produce_receivable_overdue_observations(as_of=as_of)

    observation = Observation.objects.get()
    assert first_run.result_counts["created"] == 1
    assert second_run.result_counts == {
        "created": 0,
        "resolved": 0,
        "updated": 1,
    }
    assert observation.structured_value["days_overdue"] == 40
    assert observation.severity == Observation.Severity.HIGH
    assert Observation.objects.count() == 1
    assert Evidence.objects.count() == 1
    assert ObservationEvidence.objects.count() == 1


@pytest.mark.django_db
def test_receivable_producer_resolves_observation_after_payment():
    as_of = date(2026, 7, 20)
    ledger = _create_ledger(as_of=as_of)
    produce_receivable_overdue_observations(as_of=as_of)

    ledger.outstanding = Decimal("0")
    ledger.save(update_fields=["outstanding"])
    run = produce_receivable_overdue_observations(as_of=as_of)

    observation = Observation.objects.get()
    assert run.result_counts == {
        "created": 0,
        "resolved": 1,
        "updated": 0,
    }
    assert observation.status == Observation.Status.RESOLVED
    assert observation.resolved_at is not None


@pytest.mark.django_db
def test_receivable_producer_ignores_non_income_and_not_yet_due_rows():
    as_of = date(2026, 7, 20)
    non_income = _create_ledger(as_of=as_of)
    non_income.ledger_type = "支出"
    non_income.save(update_fields=["ledger_type"])
    not_due = _create_ledger(
        as_of=as_of,
        source_record_id="ledger-2",
    )
    not_due.expected_payment_date = as_of
    not_due.save(update_fields=["expected_payment_date"])

    run = produce_receivable_overdue_observations(as_of=as_of)

    assert run.result_counts == {
        "created": 0,
        "resolved": 0,
        "updated": 0,
    }
    assert Observation.objects.count() == 0
