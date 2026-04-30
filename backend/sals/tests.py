"""
Tests for SALS app.
"""
from unittest.mock import patch

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model

from .models import Company, Incident
from . import views


class CompanyModelTest(TestCase):
    def test_create_company(self):
        company = Company.objects.create(sys_id="test-001", name="Test Corp")
        self.assertEqual(company.sys_id, "test-001")
        self.assertEqual(str(company), "test-001 Test Corp")

    def test_company_unique_sys_id(self):
        Company.objects.create(sys_id="unique-001", name="First")
        with self.assertRaises(Exception):
            Company.objects.create(sys_id="unique-001", name="Second")


class UserModelTest(TestCase):
    def test_create_user(self):
        from .models import User as SalsUser

        user = SalsUser.objects.create(
            sys_id="user-001",
            name="John Doe",
            email="john@example.com",
            department="Engineering",
        )
        self.assertEqual(user.sys_id, "user-001")
        self.assertEqual(user.name, "John Doe")
        self.assertEqual(str(user), "user-001 John Doe")


class IncidentModelTest(TestCase):
    def test_create_incident(self):
        incident = Incident.objects.create(
            number="INC-001",
            priority="P1",
            state="New",
            company="Test Corp",
            caller="John",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        self.assertEqual(incident.number, "INC-001")
        self.assertEqual(incident.priority, "P1")
        self.assertEqual(str(incident), "INC-001 New")

    def test_derive_fields(self):
        incident = Incident.objects.create(
            number="INC-002",
            priority="P1",
            state="New",
            company="Test Corp",
            caller="John",
            resolve_hours=2.0,
            sla_limit=4.0,
            is_sla_met=True,
            month="2026-01",
            weekday="Thursday",
            hour=9,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        self.assertEqual(incident.resolve_hours, 2.0)
        self.assertTrue(incident.is_sla_met)


class KpiStatViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(
            username="staff", password="pass", is_staff=True
        )
        Incident.objects.create(
            number="INC-001", priority="P1", state="New",
            company="A", caller="C", created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        Incident.objects.create(
            number="INC-002", priority="P2", state="Resolved",
            company="A", caller="C", created_at="2026-01-02T00:00:00Z",
            updated_at="2026-01-03T00:00:00Z",
        )

    def test_kpi_returns_counts(self):
        request = self.factory.get("/api/v1/sals/stats/kpi")
        request.user = self.user
        response = views.KpiStatAPIView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 2)
        self.assertEqual(response.data["p1_total"], 1)
        self.assertEqual(response.data["p2_total"], 1)

    def test_priority_dist(self):
        request = self.factory.get("/api/v1/sals/stats/priority-dist")
        request.user = self.user
        response = views.PriorityDistAPIView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        priorities = {r["priority"]: r["count"] for r in response.data}
        self.assertEqual(priorities.get("P1"), 1)
        self.assertEqual(priorities.get("P2"), 1)

    def test_state_dist(self):
        request = self.factory.get("/api/v1/sals/stats/state-dist")
        request.user = self.user
        response = views.StateDistAPIView.as_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_ping(self):
        request = self.factory.get("/api/v1/sals/ping")
        request.user = self.user
        response = views.PingAPIView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["pong"])


class EtlServiceTest(TestCase):
    @patch("sals.services.etl.login_api")
    def test_sync_companies_empty_response(self, mock_login):
        mock_login.return_value = None
        from .services import etl
        result = etl.sync_companies_from_api()
        self.assertEqual(result["status"], "error")
        self.assertIn("认证失败", result["message"])
