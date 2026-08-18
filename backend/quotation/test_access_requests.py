from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from quotation.access import can_access_document, can_upload_to_folder
from quotation.models import (
    AuditEvent,
    DocumentAsset,
    DocumentType,
    Quotation,
    QuotationAccessRequest,
    QuotationAccessRequestStatus,
    QuotationAccessRequestType,
    QuotationMembership,
    QuotationMembershipRole,
    QuotationUploadPermission,
    QuotationViewPermission,
)


class QuotationAccessRequestTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("request-admin")
        QuotationMembership.objects.create(
            user=self.admin,
            role=QuotationMembershipRole.ADMIN,
        )
        self.user = User.objects.create_user(
            "request-user",
            email="request-user@example.com",
        )
        QuotationMembership.objects.create(
            user=self.user,
            role=QuotationMembershipRole.USER,
        )
        self.quotation = Quotation.objects.create(
            quote_no="Q-ACCESS-REQUEST",
            project_name="Access request",
            currency="USD",
            payment_terms="CIA",
            quote_date="2026-08-01",
            expire_date="2026-09-01",
            issuer_contact_name="another-salesperson",
            issuer_contact_email="owner@example.com",
            client_company="Client",
            contact_person="Contact",
            email="client@example.com",
            created_by_email="owner@example.com",
        )
        self.asset = DocumentAsset.objects.create(
            quotation=self.quotation,
            doc_type=DocumentType.PDF,
            file_name="Confidential Quote.pdf",
            mime_type="application/pdf",
            storage_key="documents/access-request/quote.pdf",
            source="feishu",
            feishu_file_token="confidential-file-token",
            feishu_folder_token="sales-folder",
            feishu_folder_path=[
                {"token": "archive-root", "name": "Quotation"},
                {"token": "sales-folder", "name": "Sales Folder"},
            ],
        )
        self.admin_api = APIClient()
        self.admin_api.force_authenticate(self.admin)
        self.user_api = APIClient()
        self.user_api.force_authenticate(self.user)

    def submit(self, request_type, target_id):
        return self.user_api.post(
            "/api/v1/quotation/access-requests",
            {
                "request_type": request_type,
                "target_id": target_id,
                "reason": "Needed for customer follow-up.",
            },
            format="json",
        )

    def decide(self, request_id, action, **payload):
        return self.admin_api.post(
            f"/api/v1/quotation/access-requests/{request_id}/decision",
            {"action": action, **payload},
            format="json",
        )

    def test_regular_context_has_safe_folders_without_file_enumeration(self):
        response = self.user_api.get("/api/v1/quotation/access-requests")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_admin"])
        self.assertEqual(response.data["documents"], [])
        self.assertIn(
            {"token": "sales-folder", "name": "Sales Folder"},
            response.data["folders"],
        )
        self.assertNotIn(
            self.asset.file_name,
            str(response.data),
        )

    def test_regular_user_can_submit_view_and_upload_requests(self):
        folder_view = self.submit("folder_view", "sales-folder")
        document_view = self.submit("document_view", self.asset.id)
        folder_upload = self.submit("folder_upload", "sales-folder")

        self.assertEqual(folder_view.status_code, 201)
        self.assertEqual(document_view.status_code, 201)
        self.assertEqual(folder_upload.status_code, 201)
        self.assertEqual(
            document_view.data["target_name"],
            "Specific document",
        )
        self.assertEqual(
            QuotationAccessRequest.objects.filter(
                applicant=self.user,
                status=QuotationAccessRequestStatus.PENDING,
            ).count(),
            3,
        )

    def test_equivalent_pending_request_is_rejected(self):
        first = self.submit("folder_upload", "sales-folder")
        duplicate = self.submit("folder_upload", "sales-folder")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(
            QuotationAccessRequest.objects.filter(
                applicant=self.user,
                request_type=QuotationAccessRequestType.FOLDER_UPLOAD,
                status=QuotationAccessRequestStatus.PENDING,
            ).count(),
            1,
        )

    def test_approvals_create_existing_view_and_upload_permissions(self):
        folder_view = self.submit("folder_view", "sales-folder")
        document_view = self.submit("document_view", self.asset.id)
        folder_upload = self.submit("folder_upload", "sales-folder")
        expires_at = timezone.now() + timedelta(days=14)

        view_approved = self.decide(folder_view.data["id"], "approve")
        document_approved = self.decide(
            document_view.data["id"],
            "approve",
        )
        upload_approved = self.decide(
            folder_upload.data["id"],
            "approve",
            expires_at=expires_at.isoformat(),
        )

        self.assertEqual(view_approved.status_code, 200)
        self.assertEqual(document_approved.status_code, 200)
        self.assertEqual(upload_approved.status_code, 200)
        self.assertEqual(
            QuotationViewPermission.objects.filter(
                user=self.user,
                is_active=True,
            ).count(),
            2,
        )
        self.assertEqual(
            QuotationUploadPermission.objects.filter(
                user=self.user,
                folder_token="sales-folder",
                is_active=True,
            ).count(),
            1,
        )
        self.assertTrue(can_access_document(self.user, self.asset))
        self.assertTrue(can_upload_to_folder(self.user, "sales-folder"))

    def test_reject_revoke_and_expire_are_visible_and_audited(self):
        rejected_request = self.submit("folder_view", "sales-folder")
        rejected = self.decide(
            rejected_request.data["id"],
            "reject",
            review_note="Not required for this account.",
        )
        upload_request = self.submit("folder_upload", "sales-folder")
        self.decide(upload_request.data["id"], "approve")
        revoked = self.decide(upload_request.data["id"], "revoke")

        second_upload = self.submit("folder_upload", "sales-folder")
        self.decide(second_upload.data["id"], "approve")
        expired = self.decide(second_upload.data["id"], "expire")
        own_list = self.user_api.get("/api/v1/quotation/access-requests")

        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(expired.status_code, 200)
        statuses = {
            item["id"]: item["status"] for item in own_list.data["requests"]
        }
        self.assertEqual(
            statuses[rejected_request.data["id"]],
            QuotationAccessRequestStatus.REJECTED,
        )
        self.assertEqual(
            statuses[upload_request.data["id"]],
            QuotationAccessRequestStatus.REVOKED,
        )
        self.assertEqual(
            statuses[second_upload.data["id"]],
            QuotationAccessRequestStatus.EXPIRED,
        )
        rejected_row = next(
            item
            for item in own_list.data["requests"]
            if item["id"] == rejected_request.data["id"]
        )
        self.assertEqual(rejected_row["reviewer"], self.admin.username)
        self.assertEqual(
            rejected_row["review_note"],
            "Not required for this account.",
        )
        self.assertFalse(can_upload_to_folder(self.user, "sales-folder"))
        self.assertGreaterEqual(
            AuditEvent.objects.filter(module="access_requests").count(),
            8,
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                module="access_requests",
                action="reject",
                summary="Access request rejected.",
            ).exists()
        )

    def test_regular_user_cannot_decide_requests(self):
        access_request = self.submit("folder_view", "sales-folder")

        response = self.user_api.post(
            "/api/v1/quotation/access-requests/"
            f"{access_request.data['id']}/decision",
            {"action": "approve"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
