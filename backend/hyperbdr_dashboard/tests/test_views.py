import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_list_data_sources(api_client, data_source):
    response = api_client.get("/api/v1/hyperbdr-dashboard/data-sources/")

    assert response.status_code == 200
    assert response.data["total"] == 1
    assert response.data["items"][0]["name"] == data_source.name
    assert response.data["items"][0]["password"] == ""


@pytest.mark.django_db
def test_dashboard_endpoint_returns_summary(api_client):
    response = api_client.get(
        "/api/v1/hyperbdr-dashboard/analyzer/dashboard/"
    )

    assert response.status_code == 200
    assert set(response.data) == {"tenant", "license", "task"}


@pytest.mark.django_db
def test_dashboard_requires_authentication():
    client = APIClient()

    response = client.get(
        "/api/v1/hyperbdr-dashboard/analyzer/dashboard/"
    )

    assert response.status_code == 401
