from django.contrib.auth.models import User
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework.test import APIClient

from quotation.audit import record_audit_event
from quotation.models import AuditEvent, SecurityAlert


class SecurityAlertTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="security-user",
            email="security@example.com",
            password="password",
        )
        self.viewer = User.objects.create_user(
            username="security-viewer",
            email="viewer@example.com",
            password="password",
        )
        self.admin = User.objects.create_user(
            username="security-admin",
            email="admin@example.com",
            password="password",
            is_staff=True,
        )

    def request(self, user=None, user_agent="Chrome/138.0 Mac OS X"):
        return type(
            "Request",
            (),
            {
                "user": user or self.user,
                "META": {
                    "REMOTE_ADDR": "198.51.100.24",
                    "HTTP_USER_AGENT": user_agent,
                },
            },
        )()

    def record_downloads(self, count=20):
        for number in range(count):
            record_audit_event(
                request=self.request(),
                module="document",
                action="download",
                result=AuditEvent.RESULT_SUCCEEDED,
                target_type="document",
                target_id=str(number),
                target_label=f"Quote-{number}.xlsx",
            )

    def test_bulk_downloads_create_one_alert_with_all_evidence(self):
        self.record_downloads()

        alert = SecurityAlert.objects.get(rule="unusual_bulk_downloads")

        self.assertEqual(alert.severity, SecurityAlert.SEVERITY_HIGH)
        self.assertEqual(alert.status, SecurityAlert.STATUS_OPEN)
        self.assertEqual(alert.trigger_count, 20)
        self.assertEqual(alert.evidence_events.count(), 20)

    def test_repeated_failed_feishu_access_creates_medium_alert(self):
        for number in range(5):
            record_audit_event(
                request=self.request(),
                module="feishu",
                action="open",
                result=AuditEvent.RESULT_FAILED,
                target_type="document",
                target_id=str(number),
                summary="Access denied",
            )

        alert = SecurityAlert.objects.get(
            rule="repeated_feishu_access_failures"
        )

        self.assertEqual(alert.severity, SecurityAlert.SEVERITY_MEDIUM)
        self.assertEqual(alert.evidence_events.count(), 5)

    def test_all_users_can_view_alerts_but_evidence_is_masked(self):
        self.record_downloads()
        api = APIClient()
        api.force_authenticate(user=self.viewer)

        response = api.get("/api/v1/quotation/security-alerts")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["can_manage"])
        self.assertEqual(
            response.data["items"][0]["source_ip"],
            "198.51.100.*",
        )
        self.assertEqual(response.data["items"][0]["device"], "")
        self.assertEqual(response.data["summary"]["open"], 1)

    def test_only_admin_can_acknowledge_or_resolve_an_alert(self):
        self.record_downloads()
        alert = SecurityAlert.objects.get(rule="unusual_bulk_downloads")
        api = APIClient()
        api.force_authenticate(user=self.viewer)

        forbidden = api.patch(
            f"/api/v1/quotation/security-alerts/{alert.id}",
            {"action": "acknowledge"},
            format="json",
        )

        self.assertEqual(forbidden.status_code, 403)

        api.force_authenticate(user=self.admin)
        acknowledged = api.patch(
            f"/api/v1/quotation/security-alerts/{alert.id}",
            {"action": "acknowledge"},
            format="json",
        )
        self.assertEqual(acknowledged.status_code, 200)
        self.assertEqual(
            acknowledged.data["alert"]["status"],
            SecurityAlert.STATUS_ACKNOWLEDGED,
        )

        resolved = api.patch(
            f"/api/v1/quotation/security-alerts/{alert.id}",
            {
                "action": "resolve",
                "resolution": SecurityAlert.RESOLUTION_AUTHORIZED,
                "resolution_note": "Confirmed with the sales manager.",
                "notify_affected_user": False,
            },
            format="json",
        )

        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(
            resolved.data["alert"]["status"],
            SecurityAlert.STATUS_RESOLVED,
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                module="security",
                action="resolve",
                target_id=str(alert.id),
            ).exists()
        )

    def test_admin_sees_complete_source_ip_and_evidence(self):
        self.record_downloads()
        alert = SecurityAlert.objects.get(rule="unusual_bulk_downloads")
        api = APIClient()
        api.force_authenticate(user=self.admin)

        response = api.get(
            f"/api/v1/quotation/security-alerts/{alert.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["can_manage"])
        self.assertEqual(response.data["alert"]["source_ip"], "198.51.100.24")
        self.assertEqual(len(response.data["alert"]["evidence"]), 20)

    @override_settings(
        QUOTATION_SECURITY_ENUMERATION_THRESHOLD=3,
        QUOTATION_SECURITY_ENUMERATION_WINDOW_MINUTES=5,
    )
    def test_distinct_missing_ids_trigger_enumeration_alert(self):
        for number in range(3):
            record_audit_event(
                request=self.request(),
                module="document",
                action="download",
                result=AuditEvent.RESULT_FAILED,
                target_type="document",
                target_id=f"missing-{number}",
                reason_code="resource_not_found",
            )

        alert = SecurityAlert.objects.get(rule="object_id_enumeration")
        self.assertEqual(alert.threshold, 3)
        self.assertEqual(alert.window_minutes, 5)
        self.assertTrue(alert.owner)
        self.assertIn("object_id_enumeration", alert.runbook)

    def test_catalog_change_triggers_configuration_alert(self):
        record_audit_event(
            request=self.request(),
            module="catalog",
            action="delete",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="software_product",
            target_id="product-1",
            target_label="OnePro",
        )

        alert = SecurityAlert.objects.get(rule="configuration_change")
        self.assertEqual(alert.severity, SecurityAlert.SEVERITY_MEDIUM)
        self.assertEqual(alert.evidence_events.count(), 1)

    @override_settings(
        QUOTATION_SECURITY_SYNC_FAILURE_THRESHOLD=3,
        QUOTATION_SECURITY_SYNC_FAILURE_WINDOW_MINUTES=30,
    )
    def test_repeated_sync_failures_trigger_backlog_alert(self):
        for number in range(3):
            record_audit_event(
                request=self.request(),
                module="feishu",
                action="sync",
                result=AuditEvent.RESULT_FAILED,
                target_type="sync_job",
                target_id=str(number),
            )

        alert = SecurityAlert.objects.get(rule="sync_failure_backlog")
        self.assertEqual(alert.trigger_count, 3)
        self.assertEqual(alert.threshold, 3)
        self.assertEqual(alert.window_minutes, 30)
