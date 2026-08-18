from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import resolve
from quotation.audit import record_audit_event
from quotation.middleware import (
    QuotationAuditMiddleware,
    RequestIdMiddleware,
    _audit_changes,
    _classify,
    _is_automatic_generate_followup,
    _should_record_audit,
)
from quotation.models import (
    AuditEvent,
    DocumentAsset,
    Quotation,
    QuotationItem,
    SyncJob,
    SyncJobStatus,
    SyncJobType,
)
from quotation.tasks import _record_feishu_sync_observability
from quotation.views.quotations import (
    _quotation_change_details,
    _quotation_changed_fields,
)
from rest_framework.response import Response
from rest_framework.test import APIClient


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

    def test_document_download_history_is_user_facing(self):
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
            (
                "POST",
                "/api/v1/quotation/quotations/quote-id/exports",
                ("quotation", "generate", "quotation"),
            ),
        ]
        for method, path, expected in cases:
            with self.subTest(method=method, path=path):
                self.assertEqual(_classify(method, path), expected)

        self.assertEqual(
            _classify(
                "POST",
                "/api/v1/quotation/feishu/files/access/batch",
            ),
            ("feishu", "open", "document"),
        )
        self.assertIsNone(
            _classify("GET", "/api/v1/quotation/exports/export-id")
        )
        self.assertEqual(
            _classify("POST", "/api/v1/quotation/unregistered-action"),
            ("quotation", "post", "request"),
        )

    def test_business_actions_and_authorization_denials_are_recorded(self):
        business_cases = [
            ("quotation", "create"),
            ("quotation", "update"),
            ("quotation", "delete"),
            ("quotation", "generate"),
            ("document", "upload"),
            ("document", "download"),
            ("document", "delete"),
            ("document", "archive"),
            ("document", "restore"),
            ("feishu", "upload"),
            ("feishu", "import"),
            ("catalog", "create"),
            ("catalog", "update"),
            ("catalog", "delete"),
        ]
        for module, action in business_cases:
            with self.subTest(module=module, action=action):
                self.assertTrue(_should_record_audit(module, action, 200))

        quiet_cases = [
            ("quotation", "view"),
            ("document", "view"),
            ("feishu", "open"),
            ("feishu", "sync"),
            ("storage", "health_checked"),
        ]
        for module, action in quiet_cases:
            with self.subTest(module=module, action=action):
                self.assertFalse(_should_record_audit(module, action, 200))
                self.assertTrue(_should_record_audit(module, action, 403))

    def test_quote_updates_record_the_affected_business_fields(self):
        fields = ["project_name", "status", "items"]

        self.assertEqual(
            _audit_changes(
                "quotation",
                "update",
                fields,
                {"project_name": {"old": "Before", "new": "After"}},
            ),
            {
                "fields": fields,
                "project_name": {"old": "Before", "new": "After"},
            },
        )
        self.assertEqual(
            _audit_changes("catalog", "update", fields),
            {"fields": fields},
        )

    def test_full_quote_payload_records_only_real_changes(self):
        quotation = Quotation.objects.create(
            quote_no="Q-AUDIT-DIFF-001",
            project_name="Before",
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
        item = QuotationItem.objects.create(
            quotation=quotation,
            line_no=1,
            type="software",
            item_id="product-1",
            name="Product",
            description="Description",
            qty=Decimal("1.00"),
            list_price=Decimal("100.00"),
            discount_percent=Decimal("0.00"),
            net_unit_price=Decimal("100.00"),
            extended_price=Decimal("100.00"),
        )
        quotation = Quotation.objects.prefetch_related("items").get(
            pk=quotation.pk
        )
        item_payload = {
            field: getattr(item, field)
            for field in (
                "line_no",
                "type",
                "item_id",
                "name",
                "description",
                "qty",
                "list_price",
                "discount_percent",
                "net_unit_price",
                "extended_price",
            )
        }

        fields = _quotation_changed_fields(
            quotation,
            {
                "quote_no": quotation.quote_no,
                "project_name": "After",
                "client_company": quotation.client_company,
                "items": [item_payload],
            },
        )

        self.assertEqual(fields, ["project_name"])

        details = _quotation_change_details(
            quotation,
            {
                "quote_no": quotation.quote_no,
                "project_name": "After",
                "client_company": quotation.client_company,
                "items": [item_payload],
            },
        )

        self.assertEqual(
            details,
            {"project_name": {"old": "Before", "new": "After"}},
        )

    def test_quote_update_audit_event_stores_json_change_details(self):
        quotation = Quotation.objects.create(
            quote_no="Q-AUDIT-JSON-001",
            project_name="Before",
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

        response = self.api.put(
            f"/api/v1/quotation/quotations/{quotation.id}",
            {"project_name": "After"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        event = AuditEvent.objects.get(
            module="quotation",
            action="update",
        )
        self.assertEqual(event.changes["fields"], ["project_name"])
        self.assertEqual(
            event.changes["project_name"],
            {"old": "Before", "new": "After"},
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

    def test_manual_feishu_sync_request_is_not_business_history(self):
        path = "/api/v1/quotation/feishu/sync-folder"
        factory = RequestFactory()
        request = factory.post(
            path,
            HTTP_X_QUOTATION_AUDIT_SOURCE="user",
        )
        request.user = self.user
        request.resolver_match = resolve(path)
        middleware = RequestIdMiddleware(
            QuotationAuditMiddleware(
                lambda _request: Response(
                    {
                        "sync_job_id": "sync-job-id",
                        "storage_connection_id": "storage-id",
                    },
                    status=202,
                )
            )
        )

        response = middleware(request)

        self.assertEqual(response.status_code, 202)
        self.assertFalse(AuditEvent.objects.exists())

    def test_successful_views_do_not_create_business_history(self):
        cases = [
            "/api/v1/quotation/quotations/quote-id",
            "/api/v1/quotation/quotations/quote-id/documents",
            "/api/v1/quotation/feishu/documents/file-id/access",
        ]
        for path in cases:
            with self.subTest(path=path):
                request = RequestFactory().get(path)
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

    def test_unregistered_mutation_only_records_authorization_denial(self):
        path = "/api/v1/quotation/unregistered-action"
        factory = RequestFactory()
        middleware = RequestIdMiddleware(
            QuotationAuditMiddleware(
                lambda _request: Response({"ok": True}, status=200)
            )
        )
        successful_request = factory.post(path)
        successful_request.user = self.user

        successful_response = middleware(successful_request)

        self.assertEqual(successful_response.status_code, 200)
        self.assertFalse(AuditEvent.objects.exists())

        denied_middleware = RequestIdMiddleware(
            QuotationAuditMiddleware(
                lambda _request: Response(status=403)
            )
        )
        denied_request = factory.post(path)
        denied_request.user = self.user

        denied_response = denied_middleware(denied_request)

        self.assertEqual(denied_response.status_code, 403)
        event = AuditEvent.objects.get()
        self.assertEqual(event.event_name, "quotation.post")
        self.assertEqual(event.result, AuditEvent.RESULT_DENIED)
        self.assertEqual(event.target_type, "request")

    def test_feishu_sync_uses_operational_telemetry_not_audit(self):
        job = SyncJob.objects.create(
            job_type=SyncJobType.PULL,
            status=SyncJobStatus.SUCCESS,
            actor=self.user,
            request_id="request-id",
            trace_id="trace-id",
            payload_json={"audit_source": "user"},
            result_json={
                "created_count": 2,
                "skipped_count": 3,
                "queued_parse_count": 2,
                "parsed_count": 1,
                "folders": [
                    {"name": "Tower"},
                    {"name": "Customer A"},
                ],
                "errors": [],
            },
            duration_ms=125,
        )

        with patch(
            "quotation.tasks.record_storage_operation"
        ) as record_metric, self.assertLogs(
            "quotation.tasks",
            level="INFO",
        ) as logs:
            _record_feishu_sync_observability(
                job,
                result="success",
            )

        record_metric.assert_called_once_with(
            provider="feishu",
            operation="archive_sync",
            result="success",
            duration_seconds=0.125,
        )
        self.assertIn("quotation_feishu_sync_completed", logs.output[0])
        self.assertFalse(AuditEvent.objects.exists())

    def test_feishu_sync_failures_use_error_logs_and_metrics(self):
        job = SyncJob.objects.create(
            job_type=SyncJobType.PULL,
            status=SyncJobStatus.FAILED,
            actor=self.user,
            error_code="folder_sync_failed",
            duration_ms=250,
        )

        with patch(
            "quotation.tasks.record_storage_operation"
        ) as record_metric, self.assertLogs(
            "quotation.tasks",
            level="ERROR",
        ) as logs:
            _record_feishu_sync_observability(
                job,
                result="failure",
                error_code=job.error_code,
            )

        record_metric.assert_called_once_with(
            provider="feishu",
            operation="archive_sync",
            result="failure",
            duration_seconds=0.25,
        )
        self.assertIn("quotation_feishu_sync_completed", logs.output[0])
        self.assertFalse(AuditEvent.objects.exists())

    def test_archive_sync_history_is_not_user_facing(self):
        AuditEvent.objects.create(
            actor=self.user,
            actor_email=self.user.email,
            module="feishu",
            action="sync",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="folder",
            target_id="sync-job-id",
            sync_job_id="sync-job-id",
            event_name="storage.archive_sync_requested",
            metadata={"status_code": 202},
        )
        AuditEvent.objects.create(
            actor=self.user,
            module="feishu",
            action="upload",
            event_name="document.uploaded",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="document",
            target_id="document-id",
        )
        AuditEvent.objects.create(
            actor=self.user,
            module="quotation",
            action="update",
            event_name="quotation.updated",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="quotation",
            target_id="quote-id",
        )

        response = self.api.get("/api/v1/quotation/audit-events")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 2)
        self.assertEqual(
            {
                item["event_name"]
                for item in response.data["items"]
            },
            {"document.uploaded", "quotation.updated"},
        )

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
        AuditEvent.objects.create(
            actor=self.user,
            module="quotation",
            action="update",
            event_name="quotation.updated",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="quotation",
            target_id="quote-id",
        )
        AuditEvent.objects.create(
            actor=self.user,
            module="document",
            action="download",
            event_name="document.downloaded",
            result=AuditEvent.RESULT_DENIED,
            target_type="document",
            target_id="private-document-id",
        )

        response = self.api.get("/api/v1/quotation/audit-events")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 2)
        self.assertEqual(
            {item["action"] for item in response.data["items"]},
            {"upload", "update"},
        )

    def test_internal_audit_history_requires_an_administrator(self):
        AuditEvent.objects.create(
            actor=self.user,
            module="document",
            action="download",
            event_name="document.downloaded",
            result=AuditEvent.RESULT_DENIED,
            target_type="document",
            target_id="private-document-id",
        )

        denied = self.api.get(
            "/api/v1/quotation/audit-events",
            {"include_internal": "true"},
        )

        self.assertEqual(denied.status_code, 403)
        self.assertTrue(
            AuditEvent.objects.filter(
                event_name="audit.viewed",
                result=AuditEvent.RESULT_DENIED,
                reason_code="administrator_required",
            ).exists()
        )

        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        allowed = self.api.get(
            "/api/v1/quotation/audit-events",
            {"include_internal": "true"},
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.data["total"], 2)
        self.assertEqual(
            {
                item["event_name"]
                for item in allowed.data["items"]
            },
            {"document.downloaded", "audit.viewed"},
        )

    def test_request_and_trace_ids_are_generated_and_propagated(self):
        response = self.api.get("/api/v1/quotation/audit-events")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["X-Request-ID"])
        self.assertEqual(response["X-Trace-ID"], response["X-Request-ID"])
        self.assertFalse(AuditEvent.objects.exists())

        response = self.api.get(
            "/api/v1/quotation/audit-events",
            HTTP_X_REQUEST_ID="request-from-client",
            HTTP_X_TRACE_ID="trace-from-client",
        )
        self.assertEqual(response["X-Request-ID"], "request-from-client")
        self.assertEqual(response["X-Trace-ID"], "trace-from-client")

    def test_denied_request_has_reason_risk_and_resource_link(self):
        path = "/api/v1/quotation/quotations/private-id"
        factory = RequestFactory()
        request = factory.delete(path)
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
        self.assertEqual(event.quotation_id_snapshot, "private-id")
        self.assertEqual(event.request_id, response["X-Request-ID"])

    def test_request_target_hint_is_used_when_response_has_no_object(self):
        path = "/api/v1/quotation/quotations/quote-id/exports"
        factory = RequestFactory()
        request = factory.post(path)
        request.user = self.user
        request.resolver_match = resolve(path)
        request.quotation_audit_target_label = "BDR2600001"
        middleware = RequestIdMiddleware(
            QuotationAuditMiddleware(
                lambda _request: Response(
                    {"detail": "quotation not found"},
                    status=404,
                )
            )
        )

        response = middleware(request)

        event = AuditEvent.objects.get()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(event.target_type, "quotation")
        self.assertEqual(event.target_label, "BDR2600001")

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
            target_id="business-quote-id",
            request_id="export-source",
        )
        AuditEvent.objects.create(
            actor=self.user,
            module="feishu",
            action="sync",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_id="internal-sync-id",
            request_id="export-source",
        )
        AuditEvent.objects.create(
            actor=self.user,
            module="document",
            action="download",
            event_name="document.downloaded",
            result=AuditEvent.RESULT_DENIED,
            target_id="private-document-id",
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
        content = exported.content.decode()
        self.assertIn("business-quote-id", content)
        self.assertNotIn("internal-sync-id", content)
        self.assertNotIn("private-document-id", content)
        self.assertNotIn("risk_level", content.splitlines()[0])
        self.assertTrue(
            AuditEvent.objects.filter(
                event_name="audit.exported",
                result=AuditEvent.RESULT_SUCCEEDED,
            ).exists()
        )
