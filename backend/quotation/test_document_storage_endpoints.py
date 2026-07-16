import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote
from uuid import UUID

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from quotation.models import DocumentAsset, FeishuConnection, Quotation


class DocumentStorageEndpointTests(TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.storage = Path(self._temp.name)
        self.settings_override = self.settings(
            QUOTATION_STORAGE=str(self.storage)
        )
        self.settings_override.enable()
        self.user = User.objects.create_user(
            username="storage-user",
            email="storage@example.com",
            password="password",
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def tearDown(self):
        self.settings_override.disable()
        self._temp.cleanup()

    def create_quote(self) -> Quotation:
        return Quotation.objects.create(
            quote_no="Q-STORAGE-001",
            project_name="Storage alignment",
            payment_terms="CIA",
            quote_date="2026-07-15",
            expire_date="2026-08-15",
            issuer_contact_name="Storage User",
            issuer_contact_email=self.user.email,
            client_company="Example",
            contact_person="Customer",
            email="customer@example.com",
            created_by_email=self.user.email,
        )

    def assert_uuid_storage(self, asset: DocumentAsset, expected: bytes):
        parts = Path(asset.storage_key).parts
        self.assertEqual(parts[0], "documents")
        self.assertEqual(str(UUID(parts[1])), parts[1])
        self.assertEqual(str(UUID(parts[2])), parts[2])
        self.assertEqual(parts[2], asset.id)
        self.assertEqual(
            (self.storage / asset.storage_key).read_bytes(), expected
        )
        self.assertNotIn(asset.file_name, asset.storage_key)

    def test_local_upload_download_and_delete_use_uuid_storage(self):
        quote = self.create_quote()
        response = self.api.post(
            f"/api/v1/quotation/quotations/{quote.id}/documents",
            {
                "file": SimpleUploadedFile(
                    "客户 报价.xlsx",
                    b"PK\x03\x04local-file",
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
                "doc_type": "excel",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        asset = DocumentAsset.objects.get(pk=response.data["id"])
        self.assertEqual(Path(asset.storage_key).parts[1], quote.id)
        self.assert_uuid_storage(asset, b"PK\x03\x04local-file")

        download = self.api.get(
            f"/api/v1/quotation/documents/{asset.id}/download"
        )
        self.assertEqual(download.status_code, 200)
        disposition = download["Content-Disposition"]
        self.assertIn("filename*=utf-8''", disposition)
        self.assertEqual(
            unquote(disposition.split("''", 1)[1]), "客户 报价.xlsx"
        )

        delete = self.api.delete(f"/api/v1/quotation/documents/{asset.id}")
        self.assertEqual(delete.status_code, 204)
        self.assertFalse((self.storage / asset.storage_key).exists())
        self.assertFalse(DocumentAsset.objects.filter(pk=asset.id).exists())

    def test_feishu_import_uses_uuid_storage_and_keeps_original_name(self):
        FeishuConnection.objects.create(
            user=self.user,
            user_email=self.user.email,
            access_token="token",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        class FakeClient:
            def download_drive_item(self, access_token, **kwargs):
                return b"feishu-file", "application/pdf", "飞书报价.pdf"

        with patch(
            "quotation.views.feishu.common._client", return_value=FakeClient()
        ):
            response = self.api.post(
                "/api/v1/quotation/feishu/import/file_test?file_type=file"
            )

        self.assertEqual(response.status_code, 200)
        asset = DocumentAsset.objects.get(pk=response.data["document_id"])
        self.assertEqual(asset.file_name, "飞书报价.pdf")
        self.assertEqual(Path(asset.storage_key).parts[1], asset.id)
        self.assert_uuid_storage(asset, b"feishu-file")

    def test_feishu_upload_keeps_uuid_only_local_copy(self):
        quote = self.create_quote()
        FeishuConnection.objects.create(
            user=self.user,
            user_email=self.user.email,
            access_token="token",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        class FakeClient:
            def get_folder_meta(self, access_token, folder_token):
                return {"token": folder_token, "name": "Quotation Uploads"}

            def list_folder_files(self, access_token, folder_token, **kwargs):
                return {"files": [], "has_more": False}

            def upload_file(self, access_token, **kwargs):
                return {
                    "file_token": "file_uploaded",
                    "url": "https://example.feishu.cn/file/file_uploaded",
                }

        with patch(
            "quotation.views.feishu.common._client", return_value=FakeClient()
        ):
            response = self.api.post(
                "/api/v1/quotation/feishu/upload",
                {
                    "file": SimpleUploadedFile(
                        "Uploaded Quote.pdf",
                        b"%PDF-uploaded-file",
                        content_type="application/pdf",
                    ),
                    "folder": "folder_token",
                    "quotation_id": quote.id,
                },
                format="multipart",
            )

        self.assertEqual(response.status_code, 200)
        asset = DocumentAsset.objects.get(
            source="feishu_upload",
            feishu_file_token="file_uploaded",
        )
        self.assertEqual(Path(asset.storage_key).parts[1], quote.id)
        self.assert_uuid_storage(asset, b"%PDF-uploaded-file")
