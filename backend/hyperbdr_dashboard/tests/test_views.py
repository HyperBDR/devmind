"""
Tests for hyperbdr_dashboard API views.
"""

import pytest
from django.utils import timezone
from rest_framework import status


@pytest.mark.django_db
class TestOverviewAPIView:
    def test_overview_returns_expected_sections(
        self, api_client, poc_tenant, official_tenant, poc_license, official_license
    ):
        """
        The overview endpoint should return all required dashboard sections.
        """
        response = api_client.get("/api/v1/hyperbdr-dashboard/overview/")

        assert response.status_code == status.HTTP_200_OK
        assert set(response.data.keys()) == {
            "kpis",
            "focus_cards",
            "distribution",
            "funnel",
            "tenant_table",
        }

    def test_overview_kpis_include_counts(
        self, api_client, poc_tenant, official_tenant, poc_license, official_license
    ):
        """KPI section should contain total tenants, PoC, official, and conversion rate."""
        response = api_client.get("/api/v1/hyperbdr-dashboard/overview/")

        kpis = {item["key"]: item for item in response.data["kpis"]}
        assert kpis["totalTenants"]["value"] == 2
        assert kpis["pocTenants"]["value"] == 1
        assert kpis["officialTenants"]["value"] == 1

    def test_overview_focus_cards_structure(
        self, api_client, poc_tenant, official_tenant, poc_license, official_license
    ):
        """Focus cards should include the four required card types."""
        response = api_client.get("/api/v1/hyperbdr-dashboard/overview/")

        card_keys = {card["key"] for card in response.data["focus_cards"]}
        assert card_keys == {
            "expiring_soon",
            "high_potential",
            "poc_expiring",
            "low_activity",
        }
        # Each card should have descriptionKey for i18n
        for card in response.data["focus_cards"]:
            assert "descriptionKey" in card
            assert "labelKey" in card

    def test_overview_poc_expiring_count(
        self, api_client, poc_tenant, poc_license
    ):
        """PoC tenant expiring within 7 days should appear in poc_expiring."""
        response = api_client.get("/api/v1/hyperbdr-dashboard/overview/")
        cards = {c["key"]: c for c in response.data["focus_cards"]}
        assert cards["poc_expiring"]["count"] == 1

    def test_overview_empty_when_no_data(self, api_client):
        """Without any tenants, the dashboard should return empty but valid sections."""
        response = api_client.get("/api/v1/hyperbdr-dashboard/overview/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["kpis"][0]["value"] == 0

    def test_overview_denies_without_feature(self, unauthenticated_client, user):
        """A user without the hyperbdr_dashboard feature should be denied."""
        from rest_framework.test import APIClient
        from accounts.models import Role

        role = Role.objects.create(
            name="No Dashboard Role",
            is_active=True,
            visible_features=["workspace"],
        )
        user.platform_roles.add(role)

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/api/v1/hyperbdr-dashboard/overview/")

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestTrendsAPIView:
    def test_trends_returns_snapshot(self, api_client, poc_tenant, official_tenant):
        """Trends endpoint should return current distribution snapshot."""
        response = api_client.get("/api/v1/hyperbdr-dashboard/trends/")

        assert response.status_code == status.HTTP_200_OK
        assert "current" in response.data
        assert "poc_count" in response.data["current"]
        assert "official_count" in response.data["current"]

    def test_trends_respects_days_param(self, api_client, poc_tenant):
        """The days param should be accepted and reflected in the response."""
        response = api_client.get("/api/v1/hyperbdr-dashboard/trends/?days=7")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["period_days"] == 7


@pytest.mark.django_db
class TestMonthlyTrendsAPIView:
    def test_monthly_trends_include_churned_tenants_field(
        self, api_client, official_tenant, official_license
    ):
        """Monthly trends should expose churned tenant counts from backend."""
        response = api_client.get("/api/v1/hyperbdr-dashboard/trends/monthly/")

        assert response.status_code == status.HTTP_200_OK
        assert "months" in response.data
        assert len(response.data["months"]) > 0
        assert "churned_tenants" in response.data["months"][0]


@pytest.mark.django_db
class TestTenantsAPIView:
    def test_tenants_returns_rows(
        self, api_client, poc_tenant, official_tenant, poc_license, official_license
    ):
        """Tenants endpoint should return a paginated list of tenant rows."""
        response = api_client.get("/api/v1/hyperbdr-dashboard/tenants/")

        assert response.status_code == status.HTTP_200_OK
        assert "items" in response.data
        assert "total" in response.data
        assert response.data["total"] == 2

    def test_tenants_pagination(self, api_client, poc_tenant, official_tenant):
        """Skip/limit pagination should work correctly."""
        response = api_client.get("/api/v1/hyperbdr-dashboard/tenants/?skip=0&limit=1")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["items"]) == 1
        assert response.data["total"] == 2

    def test_tenant_row_includes_required_fields(
        self, api_client, poc_tenant, poc_license
    ):
        """Each tenant row should include all required dashboard columns."""
        response = api_client.get("/api/v1/hyperbdr-dashboard/tenants/")

        assert response.status_code == status.HTTP_200_OK
        row = response.data["items"][0]
        required_fields = [
            "id", "name", "scenario", "tenant_type", "total_authorization",
            "used_authorization", "utilization", "remaining_days",
        ]
        for field in required_fields:
            assert field in row, f"Missing field: {field}"

    def test_tenant_row_conversion_cycle_days_is_computed(
        self, api_client, data_source
    ):
        """Conversion cycle should be days between PoC expire and official start."""
        from datetime import timedelta
        from hyperbdr_monitor.models import License, Tenant

        tenant = Tenant.objects.create(
            data_source=data_source,
            source_tenant_id="conv-001",
            name="Conversion Tenant",
            status="active",
            trialed=False,
        )
        poc_expire = timezone.now() - timedelta(days=18)
        official_start = timezone.now()
        License.objects.create(
            data_source=data_source,
            tenant=tenant,
            scene="dr",
            total_amount=10,
            total_used=5,
            total_unused=5,
            expire_at=poc_expire,
        )
        License.objects.create(
            data_source=data_source,
            tenant=tenant,
            scene="production",
            total_amount=10,
            total_used=5,
            total_unused=5,
            start_at=official_start,
            expire_at=official_start + timedelta(days=365),
        )

        response = api_client.get("/api/v1/hyperbdr-dashboard/tenants/")
        assert response.status_code == status.HTTP_200_OK

        rows = response.data["items"]
        row = next(r for r in rows if r["id"] == "conv-001")
        assert row["conversion_cycle_days"] == 18
