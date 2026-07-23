from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import resolve
from rest_framework.response import Response
from rest_framework.test import APIClient

from quotation.audit import record_audit_event
from quotation.middleware import (
    QuotationAuditMiddleware,
    RequestIdMiddleware,
    _audit_changes,
    _classify,
    _is_automatic_activity,
    _is_automatic_generate_followup,
)
from quotation.models import AuditEvent, DocumentAsset, Quotation


class QuotationAuditEventTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="audit-user",
            email="audit@example.com",
            password="password",
        )
        self.viewer = User.objects.create_user(
            username="audit-viewer",
            email="viewer@example.com",
            password="password",
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_catalog_changes_record_clear_item_targets(self):
        payload = {
            "version": "audit-test",
            "products": [
                {
                    "id": "product-a",
                    "name": "HyperBDR Monthly License",
                    "code": "SW-HYPERBDR-MONTHLY",
                }
            ],
            "services": [],
            "discounts": [],
            "product_lines": [],
            "payment_terms": [],
        }
        created = self.api.put(
            "/api/v1/quotation/catalog",
            payload,
            format="json",
        )

        self.assertEqual(created.status_code, 200)
        created_event = AuditEvent.objects.get(
            module="catalog",
            action="create",
        )
        self.assertEqual(created_event.actor, self.user)
        self.assertEqual(
            created_event.target_label,
            "HyperBDR Monthly License",
        )
        self.assertEqual(created_event.target_type, "software_product")

        payload["products"] = []
        deleted = self.api.put(
            "/api/v1/quotation/catalog",
            payload,
            format="json",
        )

        self.assertEqual(deleted.status_code, 200)
        deleted_event = AuditEvent.objects.get(
            module="catalog",
            action="delete",
        )
        self.assertEqual(
            deleted_event.target_label,
            "HyperBDR Monthly License",
        )
        self.assertEqual(AuditEvent.objects.count(), 2)

    def test_automatic_description_catalog_creates_are_not_audited(self):
        payload = {
            "version": "audit-test",
            "products": [
                {
                    "id": "prod-auto-1784626297067-0",
                    "name": "Automatically saved description",
                    "code": "SW-AUTO",
                }
            ],
            "services": [
                {
                    "id": "serv-auto-1784626297067-1",
                    "name": "Automatically saved description",
                    "code": "OT-AUTO",
                }
            ],
            "discounts": [],
            "product_lines": [],
            "payment_terms": [],
        }

        response = self.api.put(
            "/api/v1/quotation/catalog",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(AuditEvent.objects.exists())

    def test_all_authenticated_users_can_view_audit_events(self):
        AuditEvent.objects.create(
            actor=self.user,
            actor_email=self.user.email,
            actor_name=self.user.username,
            module="quotation",
            action="create",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="quotation",
            target_id="quote-id",
            target_label="BDR2600001",
        )
        self.api.force_authenticate(user=self.viewer)

        response = self.api.get(
            "/api/v1/quotation/audit-events",
            {"module": "quotation", "search": "BDR2600001"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(
            response.data["items"][0]["actor_email"],
            self.user.email,
        )

    def test_missing_document_target_resolves_to_quote_number(self):
        quotation = Quotation.objects.create(
            quote_no="Q-AUDIT-TARGET-001",
            project_name="Audit target",
            payment_terms="CIA",
            quote_date="2026-07-21",
            expire_date="2026-08-21",
            issuer_contact_name="Audit User",
            issuer_contact_email=self.user.email,
            client_company="Example",
            contact_person="Customer",
            email="customer@example.com",
            created_by_email=self.user.email,
        )
        asset = DocumentAsset.objects.create(
            quotation=quotation,
            doc_type="pdf",
            file_name="quote.pdf",
            mime_type="application/pdf",
            storage_key="documents/audit/quote.pdf",
            created_by_email=self.user.email,
        )
        AuditEvent.objects.create(
            actor=self.user,
            module="document",
            action="download",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="document",
            target_id=asset.id,
            document_id_snapshot=asset.id,
        )

        response = self.api.get("/api/v1/quotation/audit-events")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(
            response.data["items"][0]["target_label"],
            quotation.quote_no,
        )

    def test_audit_endpoint_is_read_only(self):
        response = self.api.post(
            "/api/v1/quotation/audit-events",
            {"action": "forged"},
            format="json",
        )

        self.assertEqual(response.status_code, 405)
        self.assertFalse(AuditEvent.objects.exists())

    def test_key_user_actions_have_stable_audit_semantics(self):
        cases = [
            (
                "POST",
                "/api/v1/quotation/quotations",
                ("quotation", "create", "quotation"),
            ),
            (
                "PUT",
                "/api/v1/quotation/quotations/quote-id",
                ("quotation", "update", "quotation"),
            ),
            (
                "GET",
                "/api/v1/quotation/documents/document-id/download",
                ("document", "download", "document"),
            ),
            (
                "GET",
                "/api/v1/quotation/quotations/quote-id/documents",
                ("document", "view", "quotation"),
            ),
            (
                "POST",
                "/api/v1/quotation/quotations/quote-id/documents",
                ("document", "upload", "document"),
            ),
            (
                "POST",
                "/api/v1/quotation/feishu/sync-folder",
                ("feishu", "sync", "folder"),
            ),
        ]
        for method, path, expected in cases:
            with self.subTest(method=method, path=path):
                self.assertEqual(_classify(method, path), expected)

        self.assertIsNone(
            _classify(
                "POST",
                "/api/v1/quotation/feishu/files/access/batch",
            )
        )
        self.assertIsNone(
            _classify("POST", "/api/v1/quotation/pdf/from-html")
        )

    def test_quote_updates_defer_field_diffs_to_version_history(self):
        fields = ["project_name", "status", "items"]

        self.assertEqual(
            _audit_changes("quotation", "update", fields),
            {},
        )
        self.assertEqual(
            _audit_changes("catalog", "update", fields),
            {"fields": fields},
        )

    def test_generate_after_quote_update_is_not_a_duplicate_event(self):
        AuditEvent.objects.create(
            actor=self.user,
            actor_email=self.user.email,
            actor_name=self.user.username,
            module="quotation",
            action="update",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="quotation",
            target_id="quote-id",
            target_label="BDR2600001",
        )

        request = type("Request", (), {"user": self.user})()
        self.assertTrue(
            _is_automatic_generate_followup(
                request,
                "quotation",
                "generate",
                "quote-id",
            )
        )
        self.assertFalse(
            _is_automatic_generate_followup(
                request,
                "quotation",
                "generate",
                "another-quote",
            )
        )

    def test_background_refresh_is_not_user_activity(self):
        request = type(
            "Request",
            (),
            {
                "META": {
                    "HTTP_X_QUOTATION_AUDIT_SOURCE": "automatic",
                }
            },
        )()

        self.assertTrue(_is_automatic_activity(request))

    def test_background_refresh_is_not_persisted_as_activity(self):
        path = "/api/v1/quotation/feishu/sync-folder"
        factory = RequestFactory()
        request = factory.post(
            path,
            HTTP_X_QUOTATION_AUDIT_SOURCE="automatic",
        )
        request.user = self.user
        request.resolver_match = resolve(path)
        middleware = RequestIdMiddleware(
            QuotationAuditMiddleware(
                lambda _request: Response({"ok": True}, status=200)
            )
        )

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(AuditEvent.objects.exists())

    def test_activity_log_hides_internal_events_by_default(self):
        AuditEvent.objects.create(
            actor=self.user,
            module="feishu",
            action="sync",
            result=AuditEvent.RESULT_SUCCEEDED,
            metadata={"automatic": True, "status_code": 200},
        )
        AuditEvent.objects.create(
            actor=self.user,
            module="replica",
            action="sync_succeeded",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="document_replica",
            target_id="replica-id",
        )
        AuditEvent.objects.create(
            actor=self.user,
            module="quotation",
            action="post",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="request",
            target_id="",
        )
        AuditEvent.objects.create(
            actor=self.user,
            module="audit",
            action="view",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="audit_log",
        )
        AuditEvent.objects.create(
            actor=self.user,
            module="feishu",
            action="upload",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="document",
            target_id="document-id",
        )

        response = self.api.get("/api/v1/quotation/audit-events")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["items"][0]["action"], "upload")

    def test_request_and_trace_ids_are_generated_and_propagated(self):
        response = self.api.get("/api/v1/quotation/audit-events")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["X-Request-ID"])
        self.assertEqual(response["X-Trace-ID"], response["X-Request-ID"])
        event = AuditEvent.objects.get(event_name="audit.viewed")
        self.assertEqual(event.request_id, response["X-Request-ID"])
        self.assertEqual(event.trace_id, response["X-Trace-ID"])

        response = self.api.get(
            "/api/v1/quotation/audit-events",
            HTTP_X_REQUEST_ID="request-from-client",
            HTTP_X_TRACE_ID="trace-from-client",
        )
        self.assertEqual(response["X-Request-ID"], "request-from-client")
        self.assertEqual(response["X-Trace-ID"], "trace-from-client")

    def test_denied_request_has_reason_risk_and_resource_link(self):
        path = "/api/v1/quotation/documents/private-id/download"
        factory = RequestFactory()
        request = factory.get(path)
        request.user = self.user
        request.resolver_match = resolve(path)
        middleware = RequestIdMiddleware(
            QuotationAuditMiddleware(lambda _request: Response(status=403))
        )

        response = middleware(request)

        event = AuditEvent.objects.get()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(event.result, AuditEvent.RESULT_DENIED)
        self.assertEqual(event.reason_code, "authorization_denied")
        self.assertEqual(event.risk_level, AuditEvent.RISK_HIGH)
        self.assertEqual(event.document_id_snapshot, "private-id")
        self.assertEqual(event.request_id, response["X-Request-ID"])

    def test_request_target_hint_is_used_when_response_has_no_object(self):
        path = "/api/v1/quotation/feishu/upload"
        factory = RequestFactory()
        request = factory.post(path)
        request.user = self.user
        request.resolver_match = resolve(path)
        request.quotation_audit_target_label = "Quote-BDR2600001.pdf"
        middleware = RequestIdMiddleware(
            QuotationAuditMiddleware(
                lambda _request: Response(
                    {"detail": "Feishu resource not found"},
                    status=404,
                )
            )
        )

        response = middleware(request)

        event = AuditEvent.objects.get()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(event.target_type, "document")
        self.assertEqual(event.target_label, "Quote-BDR2600001.pdf")

    def test_sensitive_values_are_removed_from_audit_payload(self):
        request = RequestFactory().post("/", HTTP_AUTHORIZATION="Bearer bad")
        request.user = self.user
        request.audit_request_id = "request-safe"
        request.audit_trace_id = "trace-safe"

        event = record_audit_event(
            request=request,
            module="quotation",
            action="update",
            result=AuditEvent.RESULT_FAILED,
            summary="token=secret-value operation failed",
            changes={"fields": ["project_name"], "token": "secret"},
            before_summary={"password": "secret", "status": "draft"},
            metadata={"body": "secret", "status_code": 400},
        )

        self.assertNotIn("secret-value", event.summary)
        self.assertNotIn("token", event.changes)
        self.assertNotIn("password", event.before_summary)
        self.assertNotIn("body", event.metadata)
        self.assertEqual(event.metadata["status_code"], 400)

    def test_persisted_audit_events_cannot_be_changed_or_deleted(self):
        event = AuditEvent.objects.create(
            module="quotation",
            action="create",
            result=AuditEvent.RESULT_SUCCEEDED,
        )

        event.summary = "changed"
        with self.assertRaises(TypeError):
            event.save()
        with self.assertRaises(TypeError):
            event.delete()

    def test_idempotency_key_prevents_duplicate_terminal_events(self):
        request = RequestFactory().post(
            "/api/v1/quotation/quotations",
            HTTP_IDEMPOTENCY_KEY="quote-create-1",
        )
        request.user = self.user

        first = record_audit_event(
            request=request,
            module="quotation",
            action="create",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="quotation",
            target_id="quote-1",
        )
        second = record_audit_event(
            request=request,
            module="quotation",
            action="create",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="quotation",
            target_id="quote-1",
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_only_administrators_can_export_audit_records(self):
        AuditEvent.objects.create(
            actor=self.user,
            module="quotation",
            action="create",
            result=AuditEvent.RESULT_SUCCEEDED,
            request_id="export-source",
        )

        denied = self.api.get("/api/v1/quotation/audit-events/export")

        self.assertEqual(denied.status_code, 403)
        self.assertTrue(
            AuditEvent.objects.filter(
                event_name="audit.exported",
                result=AuditEvent.RESULT_DENIED,
                reason_code="administrator_required",
            ).exists()
        )

        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        exported = self.api.get(
            "/api/v1/quotation/audit-events/export",
            {"request_id": "export-source"},
        )
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported["Content-Type"], "text/csv")
        self.assertIn("export-source", exported.content.decode())
        self.assertTrue(
            AuditEvent.objects.filter(
                event_name="audit.exported",
                result=AuditEvent.RESULT_SUCCEEDED,
            ).exists()
        )
