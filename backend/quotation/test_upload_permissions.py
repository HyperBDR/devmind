from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from quotation.access import can_upload_to_folder
from quotation.models import (
    AuditEvent,
    DocumentAsset,
    DocumentType,
    Quotation,
    QuotationMembership,
    QuotationMembershipRole,
    QuotationUploadPermission,
    QuotationViewPermission,
    QuotationViewPermissionTarget,
)


class QuotationUploadPermissionTests(TestCase):
    def setUp(self):
        self.storage = TemporaryDirectory()
        self.settings_override = self.settings(
            QUOTATION_DOCUMENT_REPLICA_ENABLED=False,
            QUOTATION_STORAGE=self.storage.name,
        )
        self.settings_override.enable()
        self.admin = User.objects.create_user("upload-admin")
        QuotationMembership.objects.create(
            user=self.admin,
            role=QuotationMembershipRole.ADMIN,
        )
        self.user = User.objects.create_user(
            "upload-user",
            email="upload-user@example.com",
        )
        QuotationMembership.objects.create(
            user=self.user,
            role=QuotationMembershipRole.USER,
        )
        self.quotation = Quotation.objects.create(
            quote_no="Q-UPLOAD-PERMISSION",
            project_name="Upload permission",
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
            file_name="Quote.pdf",
            mime_type="application/pdf",
            storage_key="documents/upload-permission/quote.pdf",
            source="feishu",
            feishu_file_token="file-upload-permission",
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

    def tearDown(self):
        self.settings_override.disable()
        self.storage.cleanup()

    def test_view_permission_does_not_grant_upload_permission(self):
        QuotationViewPermission.objects.create(
            user=self.user,
            target_type=QuotationViewPermissionTarget.FOLDER,
            folder_token="sales-folder",
            folder_name="Sales Folder",
            granted_by=self.admin,
        )

        self.assertFalse(can_upload_to_folder(self.user, "sales-folder"))

    def test_upload_permission_is_limited_to_exact_active_folder(self):
        permission = QuotationUploadPermission.objects.create(
            user=self.user,
            folder_token="sales-folder",
            folder_name="Sales Folder",
            granted_by=self.admin,
        )

        self.assertTrue(can_upload_to_folder(self.user, "sales-folder"))
        self.assertFalse(can_upload_to_folder(self.user, "archive-root"))
        self.assertFalse(can_upload_to_folder(self.user, "other-folder"))

        permission.expires_at = timezone.now() - timedelta(seconds=1)
        permission.save(update_fields=["expires_at", "updated_at"])

        self.assertFalse(can_upload_to_folder(self.user, "sales-folder"))

    def test_admin_can_grant_edit_and_revoke_upload_permission(self):
        expires_at = timezone.now() + timedelta(days=7)

        granted = self.admin_api.post(
            "/api/v1/quotation/upload-permissions",
            {
                "user_id": self.user.id,
                "folder_token": "sales-folder",
                "expires_at": expires_at.isoformat(),
            },
            format="json",
        )

        self.assertEqual(granted.status_code, 201)
        permission = QuotationUploadPermission.objects.get(
            pk=granted.data["id"]
        )
        self.assertEqual(permission.folder_token, "sales-folder")
        self.assertTrue(can_upload_to_folder(self.user, "sales-folder"))

        extended_at = timezone.now() + timedelta(days=30)
        edited = self.admin_api.patch(
            f"/api/v1/quotation/upload-permissions/{permission.id}",
            {"expires_at": extended_at.isoformat()},
            format="json",
        )

        self.assertEqual(edited.status_code, 200)
        permission.refresh_from_db()
        self.assertAlmostEqual(
            permission.expires_at.timestamp(),
            extended_at.timestamp(),
            delta=1,
        )

        revoked = self.admin_api.delete(
            f"/api/v1/quotation/upload-permissions/{permission.id}"
        )

        self.assertEqual(revoked.status_code, 204)
        permission.refresh_from_db()
        self.assertFalse(permission.is_active)
        self.assertIsNotNone(permission.revoked_at)
        self.assertFalse(can_upload_to_folder(self.user, "sales-folder"))
        self.assertEqual(
            AuditEvent.objects.filter(
                module="permissions",
                action__in={
                    "grant_upload",
                    "update_upload",
                    "revoke_upload",
                },
            ).count(),
            3,
        )

    def test_regular_user_cannot_manage_upload_permissions(self):
        response = self.user_api.get("/api/v1/quotation/upload-permissions")

        self.assertEqual(response.status_code, 403)

    def test_direct_upload_requires_exact_directory_permission(self):
        own_quote = Quotation.objects.create(
            quote_no="Q-OWN-UPLOAD",
            project_name="Own upload",
            currency="USD",
            payment_terms="CIA",
            quote_date="2026-08-01",
            expire_date="2026-09-01",
            issuer_contact_name=self.user.username,
            issuer_contact_email=self.user.email,
            client_company="Client",
            contact_person="Contact",
            email="client@example.com",
            created_by_email=self.user.email,
        )

        class FakeClient:
            upload_calls = 0

            def list_folder_files(self, *args, **kwargs):
                return {"files": [], "has_more": False}

            def upload_file(self, *args, **kwargs):
                self.upload_calls += 1
                return {
                    "file_token": "uploaded-file",
                    "url": "https://example.feishu.cn/file/uploaded-file",
                }

        client = FakeClient()
        context = (client, "access-token", "archive-root", None, None)

        with (
            patch(
                "quotation.views.feishu.upload."
                "common._system_drive_context_details",
                return_value=context,
            ),
            patch(
                "quotation.views.feishu.upload.common._managed_folder_token",
                side_effect=lambda **kwargs: kwargs["requested_token"],
            ),
            patch(
                "quotation.views.feishu.upload.preserve_remote_file_reference"
            ),
        ):
            denied = self.user_api.post(
                "/api/v1/quotation/feishu/upload",
                {
                    "file": SimpleUploadedFile(
                        "Denied.pdf",
                        b"%PDF-denied",
                        content_type="application/pdf",
                    ),
                    "folder_token": "sales-folder",
                    "quotation_id": own_quote.id,
                },
                format="multipart",
            )

            QuotationUploadPermission.objects.create(
                user=self.user,
                folder_token="sales-folder",
                folder_name="Sales Folder",
                granted_by=self.admin,
            )
            allowed = self.user_api.post(
                "/api/v1/quotation/feishu/upload",
                {
                    "file": SimpleUploadedFile(
                        "Allowed.pdf",
                        b"%PDF-allowed",
                        content_type="application/pdf",
                    ),
                    "folder_token": "sales-folder",
                    "quotation_id": own_quote.id,
                },
                format="multipart",
            )
            changed_token = self.user_api.post(
                "/api/v1/quotation/feishu/upload",
                {
                    "file": SimpleUploadedFile(
                        "Changed.pdf",
                        b"%PDF-changed",
                        content_type="application/pdf",
                    ),
                    "folder_token": "other-folder",
                    "quotation_id": own_quote.id,
                },
                format="multipart",
            )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(
            denied.data["detail"],
            "Upload access to this directory is required.",
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.data["folder_token"], "sales-folder")
        self.assertEqual(changed_token.status_code, 403)
        self.assertEqual(client.upload_calls, 1)

    def test_upload_folder_picker_lists_only_granted_directories(self):
        empty = self.user_api.get(
            "/api/v1/quotation/feishu/folder?intent=upload"
        )
        QuotationUploadPermission.objects.create(
            user=self.user,
            folder_token="sales-folder",
            folder_name="Sales Folder",
            granted_by=self.admin,
        )
        listing = self.user_api.get(
            "/api/v1/quotation/feishu/folder?intent=upload"
        )
        selected = self.user_api.get(
            "/api/v1/quotation/feishu/folder"
            "?intent=upload&folder_token=sales-folder"
        )
        changed_token = self.user_api.get(
            "/api/v1/quotation/feishu/folder"
            "?intent=upload&folder_token=other-folder"
        )

        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.data["files"], [])
        self.assertEqual(
            listing.data["files"],
            [
                {
                    "token": "sales-folder",
                    "open_token": "sales-folder",
                    "name": "Sales Folder",
                    "type": "folder",
                }
            ],
        )
        self.assertNotIn("path", listing.data["files"][0])
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(selected.data["folder_token"], "sales-folder")
        self.assertEqual(selected.data["files"], [])
        self.assertEqual(changed_token.status_code, 403)
