from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from data_ops.models import Contract, Observation
from data_ops.services.knowledge.contract_renewal import (
    produce_contract_renewal_observations,
)


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
