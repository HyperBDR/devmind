"""
Tests for llm_tracker admin API views: token-stats and llm-usage.

Uses project URLconf (admin_api re-exports llm_tracker views at
/api/v1/admin/token-stats/ and /api/v1/admin/llm-usage/).
"""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def admin_user(django_user_model):
    """
    Staff user for admin-only API access.
    """
    return django_user_model.objects.create_user(
        username="adminuser",
        email="admin@example.com",
        password="adminpass123",
        is_staff=True,
    )


@pytest.fixture
def admin_client(api_client, admin_user):
    """
    APIClient authenticated as staff user.
    """
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.mark.unit
@pytest.mark.django_db
class TestAdminTokenStatsView:
    """
    GET token-stats: IsAdminUser, 200 with data, 400 on bad params.
    """

    def test_unauthorized_returns_401(self, api_client):
        response = api_client.get("/api/v1/admin/token-stats/")
        assert response.status_code == 401

    def test_non_staff_returns_403(self, authenticated_client):
        response = authenticated_client.get("/api/v1/admin/token-stats/")
        assert response.status_code == 403

    def test_staff_returns_200_with_summary_and_by_model(self, admin_client):
        response = admin_client.get("/api/v1/admin/token-stats/")
        assert response.status_code == 200
        body = response.json()
        data = body.get("data", body)
        assert "summary" in data
        assert "by_model" in data
        assert data["summary"]["total_calls"] >= 0
        assert "total_tokens" in data["summary"]

    def test_staff_bad_granularity_returns_400(self, admin_client):
        response = admin_client.get(
            "/api/v1/admin/token-stats/",
            {"granularity": "invalid"},
        )
        assert response.status_code == 400
        body = response.json()
        data = body.get("data", body)
        assert "detail" in data
        detail = data["detail"].lower()
        assert "granularity" in detail or "unsupported" in detail


@pytest.mark.unit
@pytest.mark.django_db
class TestAdminLLMUsageListView:
    """
    GET /api/v1/admin/llm-usage/: IsAdminUser, 200 with results/total/page.
    """

    def test_unauthorized_returns_401(self, api_client):
        response = api_client.get("/api/v1/admin/llm-usage/")
        assert response.status_code == 401

    def test_non_staff_returns_403(self, authenticated_client):
        response = authenticated_client.get("/api/v1/admin/llm-usage/")
        assert response.status_code == 403

    def test_staff_returns_200_with_results_and_pagination(self, admin_client):
        response = admin_client.get("/api/v1/admin/llm-usage/")
        assert response.status_code == 200
        body = response.json()
        data = body.get("data", body)
        assert "results" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert isinstance(data["results"], list)
