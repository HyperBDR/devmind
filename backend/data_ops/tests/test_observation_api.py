from datetime import date, timedelta
from decimal import Decimal

import pytest
from data_ops.models import Contract, DomesticLedger, Observation
from data_ops.services.knowledge.contract_renewal import (
    produce_contract_renewal_observations,
)
from django.urls import reverse
from django.utils import timezone


def _create_expiring_contract(*, as_of, days_until_expiry=10):
    return Contract.all_objects.create(
        source_app_token="app-token",
        source_table_id="contracts-table",
        source_record_id="contract-api-1",
        source_content_hash="contract-api-hash",
        contract_number="API-C-001",
        customer_name="API Customer",
        service_end=as_of + timedelta(days=days_until_expiry),
        status="active",
    )


@pytest.mark.django_db
def test_observation_list_is_paginated_and_filterable(
    api_client,
    data_ops_user,
    monkeypatch,
):
    as_of = date(2026, 7, 20)
    _create_expiring_contract(as_of=as_of)
    produce_contract_renewal_observations(as_of=as_of)
    monkeypatch.setattr(
        "accounts.permissions.get_effective_feature_keys",
        lambda user: ["data_ops"],
    )
    api_client.force_authenticate(user=data_ops_user)

    response = api_client.get(
        reverse("data-ops-observations"),
        {
            "observation_type": "contract_renewal_risk",
            "status": "active",
            "severity": "medium",
        },
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["subject_type"] == "contract"
    latest_run = response.data["production"]["latest_runs"]
    assert latest_run["contract-renewal-risk"]["status"] == "succeeded"


@pytest.mark.django_db
def test_observation_list_explains_when_production_has_not_run(
    api_client,
    data_ops_user,
    monkeypatch,
):
    monkeypatch.setattr(
        "accounts.permissions.get_effective_feature_keys",
        lambda user: ["data_ops"],
    )
    api_client.force_authenticate(user=data_ops_user)

    response = api_client.get(reverse("data-ops-observations"))

    assert response.status_code == 200
    assert response.data["count"] == 0
    assert response.data["production"] == {
        "latest_runs": {
            "contract-renewal-risk": None,
            "receivable-overdue-risk": None,
        }
    }


@pytest.mark.django_db
def test_observation_detail_includes_source_evidence(
    api_client,
    data_ops_user,
    monkeypatch,
):
    as_of = date(2026, 7, 20)
    contract = _create_expiring_contract(as_of=as_of)
    produce_contract_renewal_observations(as_of=as_of)
    observation = Observation.objects.get()
    monkeypatch.setattr(
        "accounts.permissions.get_effective_feature_keys",
        lambda user: ["data_ops"],
    )
    api_client.force_authenticate(user=data_ops_user)

    response = api_client.get(
        reverse("data-ops-observation-detail", args=[observation.id]),
    )

    assert response.status_code == 200
    assert response.data["id"] == str(observation.id)
    assert response.data["run"]["producer_key"] == "contract-renewal-risk"
    assert len(response.data["evidence"]) == 1
    evidence = response.data["evidence"][0]
    assert evidence["role"] == "supporting"
    assert evidence["source_object_id"] == str(contract.id)
    assert evidence["snapshot"]["contract_number"] == "API-C-001"


@pytest.mark.django_db
def test_admin_can_create_contract_renewal_observation_run(
    api_client,
    data_ops_admin,
):
    as_of = timezone.localdate()
    _create_expiring_contract(as_of=as_of, days_until_expiry=5)
    api_client.force_authenticate(user=data_ops_admin)

    response = api_client.post(
        reverse("data-ops-observation-runs"),
        {"producer_key": "contract-renewal-risk"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["status"] == "succeeded"
    assert response.data["result_counts"]["created"] == 1
    assert Observation.objects.count() == 1


@pytest.mark.django_db
def test_admin_can_create_receivable_overdue_observation_run(
    api_client,
    data_ops_admin,
):
    as_of = timezone.localdate()
    DomesticLedger.all_objects.create(
        source_app_token="app-token",
        source_table_id="domestic-ledger-table",
        source_record_id="ledger-api-1",
        ledger_type="收入",
        currency="CNY",
        customer_name="API Customer",
        outstanding=Decimal("8000"),
        expected_payment_date=as_of - timedelta(days=35),
    )
    api_client.force_authenticate(user=data_ops_admin)

    response = api_client.post(
        reverse("data-ops-observation-runs"),
        {"producer_key": "receivable-overdue-risk"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["producer_key"] == "receivable-overdue-risk"
    assert response.data["status"] == "succeeded"
    assert response.data["result_counts"]["created"] == 1
    observation = Observation.objects.get()
    assert observation.observation_type == "receivable_overdue_risk"


@pytest.mark.django_db
def test_observation_run_rejects_historical_parameters(
    api_client,
    data_ops_admin,
):
    api_client.force_authenticate(user=data_ops_admin)

    response = api_client.post(
        reverse("data-ops-observation-runs"),
        {
            "producer_key": "contract-renewal-risk",
            "as_of": "2025-01-01",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "as_of" in response.data


@pytest.mark.django_db
def test_observation_run_rejects_unknown_producer(
    api_client,
    data_ops_admin,
):
    api_client.force_authenticate(user=data_ops_admin)

    response = api_client.post(
        reverse("data-ops-observation-runs"),
        {"producer_key": "unknown-producer"},
        format="json",
    )

    assert response.status_code == 400
    assert "producer_key" in response.data
