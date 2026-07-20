from datetime import date, timedelta

import pytest

from data_ops.models import (
    Contract,
    Evidence,
    KnowledgeProductionRun,
    Observation,
    ObservationEvidence,
)
from data_ops.services.knowledge.contract_renewal import (
    produce_contract_renewal_observations,
)


def _create_contract(*, service_end, source_record_id="contract-1"):
    return Contract.all_objects.create(
        source_app_token="app-token",
        source_table_id="contracts-table",
        source_record_id=source_record_id,
        source_content_hash="source-hash",
        contract_number="C-001",
        customer_name="Example Customer",
        service_end=service_end,
        status="active",
    )


@pytest.mark.django_db
def test_contract_renewal_producer_creates_traceable_observation():
    as_of = date(2026, 7, 20)
    contract = _create_contract(service_end=as_of + timedelta(days=10))

    run = produce_contract_renewal_observations(as_of=as_of)

    observation = Observation.objects.get()
    evidence = Evidence.objects.get()
    assert run.status == KnowledgeProductionRun.Status.SUCCEEDED
    assert run.result_counts == {
        "created": 1,
        "resolved": 0,
        "updated": 0,
    }
    assert observation.observation_type == "contract_renewal_risk"
    assert observation.subject_type == "contract"
    assert observation.subject_key == str(contract.id)
    assert observation.structured_value["days_until_expiry"] == 10
    assert observation.structured_value["service_end"] == "2026-07-30"
    assert observation.severity == Observation.Severity.MEDIUM
    assert evidence.source_model == "data_ops.Contract"
    assert evidence.source_object_id == str(contract.id)
    assert evidence.source_record_id == "contract-1"
    assert evidence.snapshot["contract_number"] == "C-001"
    assert ObservationEvidence.objects.filter(
        observation=observation,
        evidence=evidence,
    ).exists()


@pytest.mark.django_db
def test_contract_renewal_producer_is_idempotent():
    as_of = date(2026, 7, 20)
    _create_contract(service_end=as_of + timedelta(days=5))

    first_run = produce_contract_renewal_observations(as_of=as_of)
    second_run = produce_contract_renewal_observations(as_of=as_of)

    assert first_run.result_counts["created"] == 1
    assert second_run.result_counts == {
        "created": 0,
        "resolved": 0,
        "updated": 1,
    }
    assert Observation.objects.count() == 1
    assert Evidence.objects.count() == 1
    assert ObservationEvidence.objects.count() == 1


@pytest.mark.django_db
def test_contract_renewal_producer_resolves_observation_after_risk_clears():
    as_of = date(2026, 7, 20)
    contract = _create_contract(service_end=as_of + timedelta(days=5))
    produce_contract_renewal_observations(as_of=as_of)

    contract.service_end = as_of + timedelta(days=90)
    contract.save(update_fields=["service_end"])
    run = produce_contract_renewal_observations(as_of=as_of)

    observation = Observation.objects.get()
    assert run.result_counts == {
        "created": 0,
        "resolved": 1,
        "updated": 0,
    }
    assert observation.status == Observation.Status.RESOLVED
    assert observation.resolved_at is not None


@pytest.mark.django_db
def test_contract_renewal_producer_ignores_contract_outside_window():
    as_of = date(2026, 7, 20)
    _create_contract(service_end=as_of + timedelta(days=31))

    run = produce_contract_renewal_observations(as_of=as_of)

    assert run.result_counts == {
        "created": 0,
        "resolved": 0,
        "updated": 0,
    }
    assert Observation.objects.count() == 0


@pytest.mark.django_db
def test_contract_renewal_producer_versions_evidence_without_source_hash():
    as_of = date(2026, 7, 20)
    contract = _create_contract(service_end=as_of + timedelta(days=10))
    contract.source_content_hash = ""
    contract.save(update_fields=["source_content_hash"])
    produce_contract_renewal_observations(as_of=as_of)

    contract.contract_number = "C-002"
    contract.save(update_fields=["contract_number"])
    produce_contract_renewal_observations(as_of=as_of)

    observation = Observation.objects.get()
    current_evidence = observation.evidence.get()
    assert Evidence.objects.count() == 2
    assert current_evidence.snapshot["contract_number"] == "C-002"
