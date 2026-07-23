import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote
from uuid import UUID

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role
from quotation.models import (
    DocumentAsset,
    DocumentReplica,
    DocumentType,
    FeishuConnection,
    ReplicaSyncStatus,
    StorageConnection,
    StorageMount,
    StorageMountPurpose,
    Quotation,
    QuoteStatus,
)


class DocumentStorageEndpointTests(TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.storage = Path(self._temp.name)
        self.settings_override = self.settings(
            QUOTATION_STORAGE=str(self.storage),
            FEISHU_APP_ID="cli_test",
            FEISHU_APP_SECRET="secret_test",
            FEISHU_WEB_BASE_URL="https://tenant.feishu.cn",
            QUOTATION_FEISHU_ARCHIVE_FOLDER_TOKEN="folder_token",
        )
        self.settings_override.enable()
        self.user = User.objects.create_user(
            username="storage-user",
            email="storage@example.com",
            password="password",
        )
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        cache.delete("quotation:feishu:archive-folder-sync")

    def tearDown(self):
        cache.delete("quotation:feishu:archive-folder-sync")
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
                    content_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
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
        self.assertEqual(delete.status_code, 404)
        self.assertTrue((self.storage / asset.storage_key).exists())
        self.assertTrue(DocumentAsset.objects.filter(pk=asset.id).exists())

    def test_feishu_import_uses_uuid_storage_and_keeps_original_name(self):
        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def list_folder_files(self, access_token, folder_token, **kwargs):
                if folder_token != "folder_token":
                    return {"files": [], "has_more": False}
                return {
                    "files": [
                        {
                            "token": "file_test",
                            "name": "飞书报价.pdf",
                            "type": "file",
                            "url": "https://example.feishu.cn/file/file_test",
                        }
                    ],
                    "has_more": False,
                }

            def download_drive_item(self, access_token, **kwargs):
                return b"feishu-file", "application/pdf", "飞书报价.pdf"

        with patch(
            "quotation.views.feishu.common._client", return_value=FakeClient()
        ):
            response = self.api.post(
                "/api/v1/quotation/feishu/import/file_test"
                "?file_type=file&file_url=https://attacker.example/file"
            )

        self.assertEqual(response.status_code, 200)
        asset = DocumentAsset.objects.get(pk=response.data["document_id"])
        self.assertEqual(asset.file_name, "飞书报价.pdf")
        self.assertEqual(
            asset.feishu_url,
            "https://example.feishu.cn/file/file_test",
        )
        self.assertNotIn("file_token", response.data)
        self.assertEqual(
            response.data["url"],
            "https://example.feishu.cn/file/file_test",
        )
        self.assertTrue(response.data["direct_access_allowed"])
        self.assertEqual(Path(asset.storage_key).parts[1], asset.id)
        self.assert_uuid_storage(asset, b"feishu-file")

    def test_feishu_folder_sync_imports_new_files_to_configured_storage(self):
        downloaded_tokens = []

        DocumentAsset.objects.create(
            doc_type=DocumentType.EXCEL,
            file_name="Existing.xlsx",
            mime_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            storage_key="documents/existing/asset",
            size_bytes=12,
            source="feishu",
            feishu_file_token="existing_token",
            feishu_url="https://example.feishu.cn/file/existing_token",
            created_by_email=self.user.email,
        )

        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def list_folder_files(self, access_token, folder_token, **kwargs):
                if folder_token != "folder_token":
                    return {"files": [], "has_more": False}
                return {
                    "files": [
                        {
                            "token": "folder_child",
                            "name": "Nested folder",
                            "type": "folder",
                        },
                        {
                            "token": "existing_token",
                            "name": "Existing.xlsx",
                            "type": "file",
                        },
                        {
                            "token": "new_pdf",
                            "name": "New Quote.pdf",
                            "type": "file",
                            "url": "https://example.feishu.cn/file/new_pdf",
                        },
                        {
                            "token": "note_txt",
                            "name": "Notes.txt",
                            "type": "file",
                        },
                    ],
                    "has_more": False,
                }

            def download_drive_item(self, access_token, **kwargs):
                downloaded_tokens.append(kwargs["file_token"])
                return b"%PDF-synced", "application/pdf", "New Quote.pdf"

        with patch(
            "quotation.views.feishu.common._client", return_value=FakeClient()
        ):
            response = self.api.post("/api/v1/quotation/feishu/sync-folder")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(downloaded_tokens, ["new_pdf"])
        self.assertEqual(response.data["created_count"], 1)
        self.assertEqual(response.data["skipped_count"], 3)
        asset = DocumentAsset.objects.get(feishu_file_token="new_pdf")
        self.assertEqual(asset.created_by_email, self.user.email)
        self.assertEqual(Path(asset.storage_key).parts[1], asset.id)
        self.assert_uuid_storage(asset, b"%PDF-synced")

    def test_feishu_folder_sync_reuses_asset_created_by_other_user(self):
        other_user = User.objects.create_user(
            username="other-storage-user",
            email="other-storage@example.com",
            password="password",
        )
        existing = DocumentAsset.objects.create(
            doc_type=DocumentType.SIGNATURE,
            file_name="Shared Quote.pdf",
            mime_type="application/pdf",
            storage_key="documents/shared/asset",
            size_bytes=12,
            source="feishu",
            feishu_file_token="shared_token",
            feishu_url="https://example.feishu.cn/file/shared_token",
            created_by_email=other_user.email,
        )

        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def list_folder_files(self, access_token, folder_token, **kwargs):
                return {
                    "files": [
                        {
                            "token": "shared_token",
                            "name": "Shared Quote.pdf",
                            "type": "file",
                        }
                    ],
                    "has_more": False,
                }

            def download_drive_item(self, access_token, **kwargs):
                raise AssertionError("existing file was downloaded again")

        with patch(
            "quotation.views.feishu.common._client",
            return_value=FakeClient(),
        ):
            response = self.api.post(
                "/api/v1/quotation/feishu/sync-folder"
            )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["created_count"], 0)
        self.assertEqual(DocumentAsset.objects.count(), 1)
        self.assertEqual(
            response.data["file_locations"][0]["document_id"],
            existing.id,
        )

    def test_feishu_folder_sync_imports_files_from_child_folders(self):
        downloaded_tokens = []

        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def get_folder_meta(self, access_token, folder_token):
                return {"token": folder_token, "name": "Tower"}

            def list_folder_files(self, access_token, folder_token, **kwargs):
                if folder_token == "folder_token":
                    return {
                        "files": [
                            {
                                "token": "child_folder",
                                "name": "Child folder",
                                "type": "folder",
                            }
                        ],
                        "has_more": False,
                    }
                if folder_token == "child_folder":
                    return {
                        "files": [
                            {
                                "token": "nested_excel",
                                "name": "Nested Quote.xlsx",
                                "type": "file",
                                "url": (
                                    "https://example.feishu.cn/file/"
                                    "nested_excel"
                                ),
                            }
                        ],
                        "has_more": False,
                    }
                return {"files": [], "has_more": False}

            def download_drive_item(self, access_token, **kwargs):
                downloaded_tokens.append(kwargs["file_token"])
                return (
                    b"PK\x03\x04nested",
                    (
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    "Nested Quote.xlsx",
                )

        with patch(
            "quotation.views.feishu.common._client", return_value=FakeClient()
        ):
            response = self.api.post("/api/v1/quotation/feishu/sync-folder")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(downloaded_tokens, ["nested_excel"])
        self.assertEqual(response.data["created_count"], 1)
        self.assertEqual(response.data["skipped_count"], 1)
        self.assertEqual(
            response.data["folders"],
            [
                {
                    "token": "folder_token",
                    "name": "Tower",
                    "parent_token": None,
                },
                {
                    "token": "child_folder",
                    "name": "Child folder",
                    "parent_token": "folder_token",
                },
            ],
        )
        asset = DocumentAsset.objects.get(feishu_file_token="nested_excel")
        self.assertEqual(asset.feishu_folder_token, "child_folder")
        self.assertEqual(
            asset.feishu_folder_path,
            [
                {"token": "folder_token", "name": "Tower"},
                {"token": "child_folder", "name": "Child folder"},
            ],
        )
        self.assertEqual(
            response.data["file_locations"],
            [
                {
                    "document_id": asset.id,
                    "folder_token": "child_folder",
                }
            ],
        )
        self.assertEqual(asset.created_by_email, self.user.email)
        self.assertEqual(Path(asset.storage_key).parts[1], asset.id)
        self.assert_uuid_storage(asset, b"PK\x03\x04nested")

    def test_feishu_document_list_keeps_unique_token_path(self):
        path = [
            {"token": "folder_token", "name": "Tower"},
            {"token": "child_folder", "name": "Child folder"},
        ]
        DocumentAsset.objects.create(
            doc_type=DocumentType.PDF,
            file_name="Unique remote file.pdf",
            mime_type="application/pdf",
            storage_key="documents/unique/file",
            size_bytes=10,
            source="feishu",
            feishu_file_token="unique_remote_token",
            feishu_folder_token="child_folder",
            feishu_folder_path=path,
            created_by_email=self.user.email,
        )
        DocumentAsset.objects.create(
            doc_type=DocumentType.EXCEL,
            file_name="~$Temporary.xlsx",
            mime_type="application/octet-stream",
            storage_key="documents/temporary/file",
            size_bytes=165,
            source="feishu",
            feishu_file_token="temporary_remote_token",
            feishu_folder_token="child_folder",
            feishu_folder_path=path,
            created_by_email="another-user@example.com",
        )

        response = self.api.get(
            "/api/v1/quotation/documents?source=feishu"
        )

        self.assertEqual(response.status_code, 200)
        matches = [
            item
            for item in response.data
            if item["file_name"] == "Unique remote file.pdf"
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["feishu_folder_path"], path)
        self.assertEqual(
            matches[0]["feishu_url"],
            "https://tenant.feishu.cn/file/unique_remote_token",
        )
        self.assertTrue(matches[0]["remote_access_available"])
        self.assertIsNone(matches[0]["feishu_file_token"])
        temporary = [
            item
            for item in response.data
            if item["file_name"] == "~$Temporary.xlsx"
        ]
        self.assertEqual(len(temporary), 1)
        self.assertEqual(temporary[0]["feishu_folder_path"], path)

    def test_feishu_folder_sync_ignores_client_folder_and_uses_configured_root(
        self,
    ):
        requested_folders = []

        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def list_folder_files(self, access_token, folder_token, **kwargs):
                requested_folders.append(folder_token)
                if folder_token == "folder_token":
                    return {
                        "files": [
                            {
                                "token": "selected_pdf",
                                "name": "Selected Quote.pdf",
                                "type": "file",
                            }
                        ],
                        "has_more": False,
                    }
                return {"files": [], "has_more": False}

            def download_drive_item(self, access_token, **kwargs):
                return (
                    b"%PDF-selected",
                    "application/pdf",
                    "Selected Quote.pdf",
                )

        with patch(
            "quotation.views.feishu.common._client", return_value=FakeClient()
        ):
            response = self.api.post(
                "/api/v1/quotation/feishu/sync-folder",
                {"folder_token": "selected_folder"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(requested_folders, ["folder_token"])
        self.assertEqual(response.data["created_count"], 1)
        asset = DocumentAsset.objects.get(feishu_file_token="selected_pdf")
        self.assert_uuid_storage(asset, b"%PDF-selected")

    def test_feishu_folder_sync_visits_more_than_one_hundred_folders(self):
        requested_folders = []
        child_tokens = [f"child_{index}" for index in range(101)]

        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def list_folder_files(self, access_token, folder_token, **kwargs):
                requested_folders.append(folder_token)
                if folder_token == "folder_token":
                    return {
                        "files": [
                            {
                                "token": token,
                                "name": f"Folder {index}",
                                "type": "folder",
                            }
                            for index, token in enumerate(child_tokens)
                        ],
                        "has_more": False,
                    }
                return {"files": [], "has_more": False}

        with patch(
            "quotation.views.feishu.common._client", return_value=FakeClient()
        ):
            response = self.api.post("/api/v1/quotation/feishu/sync-folder")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(requested_folders, ["folder_token", *child_tokens])
        self.assertEqual(len(response.data["folders"]), 102)

    def test_feishu_upload_keeps_uuid_only_local_copy(self):
        quote = self.create_quote()
        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def get_folder_meta(self, access_token, folder_token):
                return {"token": folder_token, "name": "Quotation Uploads"}

            def list_folder_files(self, access_token, folder_token, **kwargs):
                if folder_token == "folder_token":
                    return {
                        "files": [
                            {
                                "token": "selected_folder",
                                "name": "Selected folder",
                                "type": "folder",
                            }
                        ],
                        "has_more": False,
                    }
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

    def test_feishu_upload_uses_selected_folder_token(self):
        quote = self.create_quote()
        upload_folders = []

        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def list_folder_files(self, access_token, folder_token, **kwargs):
                if folder_token == "folder_token":
                    return {
                        "files": [
                            {
                                "token": "selected_folder",
                                "name": "Selected folder",
                                "type": "folder",
                            }
                        ],
                        "has_more": False,
                    }
                return {"files": [], "has_more": False}

            def upload_file(self, access_token, **kwargs):
                upload_folders.append(kwargs["folder_token"])
                return {
                    "file_token": "file_selected_folder",
                    "url": (
                        "https://example.feishu.cn/file/"
                        "file_selected_folder"
                    ),
                }

        with patch(
            "quotation.views.feishu.common._client", return_value=FakeClient()
        ):
            response = self.api.post(
                "/api/v1/quotation/feishu/upload",
                {
                    "file": SimpleUploadedFile(
                        "Selected Folder Quote.pdf",
                        b"%PDF-selected-upload",
                        content_type="application/pdf",
                    ),
                    "folder_token": "selected_folder",
                    "quotation_id": quote.id,
                },
                format="multipart",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["folder_token"], "selected_folder")
        self.assertEqual(upload_folders, ["selected_folder"])

    def test_other_user_cannot_access_quote_documents_by_id(self):
        quote = self.create_quote()
        upload = self.api.post(
            f"/api/v1/quotation/quotations/{quote.id}/documents",
            {
                "file": SimpleUploadedFile(
                    "owner.xlsx",
                    b"PK\x03\x04owner-file",
                    content_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                ),
                "doc_type": "excel",
            },
            format="multipart",
        )
        self.assertEqual(upload.status_code, 201)
        asset = DocumentAsset.objects.get(pk=upload.data["id"])

        other = User.objects.create_user(
            username="other-storage-user",
            email="other-storage@example.com",
            password="password",
        )
        other_api = APIClient()
        other_api.force_authenticate(user=other)

        list_response = other_api.get(
            f"/api/v1/quotation/quotations/{quote.id}/documents"
        )
        self.assertEqual(list_response.status_code, 403)

        post_response = other_api.post(
            f"/api/v1/quotation/quotations/{quote.id}/documents",
            {
                "file": SimpleUploadedFile(
                    "other.xlsx",
                    b"PK\x03\x04other-file",
                    content_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                ),
                "doc_type": "excel",
            },
            format="multipart",
        )
        self.assertEqual(post_response.status_code, 403)

        download = other_api.get(
            f"/api/v1/quotation/documents/{asset.id}/download"
        )
        self.assertEqual(download.status_code, 403)

        delete = other_api.delete(f"/api/v1/quotation/documents/{asset.id}")
        self.assertEqual(delete.status_code, 404)
        self.assertTrue(DocumentAsset.objects.filter(pk=asset.id).exists())

    def test_feishu_upload_rejects_inaccessible_quotation_before_remote_call(
        self,
    ):
        quote = self.create_quote()
        other = User.objects.create_user(
            username="other-feishu-upload",
            email="other-feishu-upload@example.com",
            password="password",
        )
        FeishuConnection.objects.create(
            user=other,
            user_email=other.email,
            access_token="token",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        other_api = APIClient()
        other_api.force_authenticate(user=other)

        class FakeClient:
            called = False

            def get_folder_meta(self, *args, **kwargs):
                self.called = True
                raise AssertionError("remote Feishu API should not be called")

        fake_client = FakeClient()
        with patch(
            "quotation.views.feishu.common._client", return_value=fake_client
        ):
            response = other_api.post(
                "/api/v1/quotation/feishu/upload",
                {
                    "file": SimpleUploadedFile(
                        "blocked.pdf",
                        b"%PDF-blocked",
                        content_type="application/pdf",
                    ),
                    "folder": "folder_token",
                    "quotation_id": quote.id,
                },
                format="multipart",
            )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(fake_client.called)
        self.assertFalse(
            DocumentAsset.objects.filter(quotation=quote).exists()
        )

    def test_feishu_import_rejects_inaccessible_quotation_before_download(
        self,
    ):
        quote = self.create_quote()
        other = User.objects.create_user(
            username="other-feishu-import",
            email="other-feishu-import@example.com",
            password="password",
        )
        FeishuConnection.objects.create(
            user=other,
            user_email=other.email,
            access_token="token",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        other_api = APIClient()
        other_api.force_authenticate(user=other)

        class FakeClient:
            called = False

            def download_drive_item(self, *args, **kwargs):
                self.called = True
                raise AssertionError("remote Feishu API should not be called")

        fake_client = FakeClient()
        with patch(
            "quotation.views.feishu.common._client", return_value=fake_client
        ):
            response = other_api.post(
                "/api/v1/quotation/feishu/import/file_test"
                f"?quotation_id={quote.id}"
            )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(fake_client.called)
        self.assertFalse(
            DocumentAsset.objects.filter(quotation=quote).exists()
        )

    def test_feishu_missing_file_check_cannot_clear_other_users_link(self):
        quote = self.create_quote()
        quote.status = QuoteStatus.UPLOADED
        quote.save(update_fields=["status"])
        asset = DocumentAsset.objects.create(
            quotation=quote,
            doc_type=DocumentType.EXCEL,
            file_name="owner.xlsx",
            mime_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            storage_key="documents/owner/asset",
            size_bytes=12,
            source="feishu_upload",
            feishu_file_token="owner_token",
            feishu_url="https://example.feishu.cn/file/owner_token",
            created_by_email=self.user.email,
        )
        other = User.objects.create_user(
            username="other-feishu-access",
            email="other-feishu-access@example.com",
            password="password",
        )
        FeishuConnection.objects.create(
            user=other,
            user_email=other.email,
            access_token="token",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        other_api = APIClient()
        other_api.force_authenticate(user=other)

        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def batch_query_file_meta(self, *args, **kwargs):
                from quotation.services.feishu_client import FeishuAPIError

                raise FeishuAPIError("not found", code=970005)

        with patch(
            "quotation.views.feishu.common._client", return_value=FakeClient()
        ):
            response = other_api.get(
                f"/api/v1/quotation/feishu/documents/{asset.id}/access"
            )

        self.assertEqual(response.status_code, 403)
        asset.refresh_from_db()
        quote.refresh_from_db()
        self.assertEqual(asset.feishu_file_token, "owner_token")
        self.assertEqual(quote.status, QuoteStatus.UPLOADED)

    def test_regular_user_can_sync_archive_as_before(self):
        regular = User.objects.create_user(
            username="regular-sync-user",
            email="regular-sync@example.com",
            password="password",
        )
        api = APIClient()
        api.force_authenticate(user=regular)

        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def list_folder_files(self, access_token, folder_token, **kwargs):
                return {"files": [], "has_more": False}

        with patch(
            "quotation.views.feishu.common._client",
            return_value=FakeClient(),
        ):
            response = api.post("/api/v1/quotation/feishu/sync-folder")

        self.assertEqual(response.status_code, 200)

    def test_presales_keeps_original_cross_quote_upload_access(self):
        quote = self.create_quote()
        presales = User.objects.create_user(
            username="presales-user",
            email="presales@example.com",
            password="password",
        )
        role = Role.objects.create(name="presales")
        role.users.add(presales)
        api = APIClient()
        api.force_authenticate(user=presales)

        listed = api.get(
            f"/api/v1/quotation/quotations/{quote.id}/documents"
        )
        uploaded = api.post(
            f"/api/v1/quotation/quotations/{quote.id}/documents",
            {
                "file": SimpleUploadedFile(
                    "blocked.pdf",
                    b"%PDF-blocked",
                    content_type="application/pdf",
                ),
                "doc_type": "pdf",
            },
            format="multipart",
        )

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(uploaded.status_code, 201)

    def test_upload_rejects_folder_outside_configured_archive(self):
        quote = self.create_quote()

        class FakeClient:
            uploaded = False

            def get_tenant_access_token(self):
                return "tenant-token"

            def list_folder_files(self, access_token, folder_token, **kwargs):
                return {"files": [], "has_more": False}

            def upload_file(self, *args, **kwargs):
                self.uploaded = True
                raise AssertionError("upload must not be attempted")

        fake_client = FakeClient()
        with patch(
            "quotation.views.feishu.common._client",
            return_value=fake_client,
        ):
            response = self.api.post(
                "/api/v1/quotation/feishu/upload",
                {
                    "file": SimpleUploadedFile(
                        "outside.pdf",
                        b"%PDF-outside",
                        content_type="application/pdf",
                    ),
                    "folder_token": "outside_folder",
                    "quotation_id": quote.id,
                },
                format="multipart",
            )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(fake_client.uploaded)

    def test_remote_content_download_requires_authorized_document(self):
        quote = self.create_quote()
        asset = DocumentAsset.objects.create(
            quotation=quote,
            doc_type=DocumentType.PDF,
            file_name="remote.pdf",
            mime_type="application/pdf",
            storage_key="documents/remote/asset",
            size_bytes=10,
            source="feishu_upload",
            feishu_file_token="remote_token",
            feishu_url="https://example.feishu.cn/file/remote_token",
            created_by_email=self.user.email,
        )

        class FakeClient:
            calls = 0

            def get_tenant_access_token(self):
                return "tenant-token"

            def download_drive_item(self, access_token, **kwargs):
                self.calls += 1
                return b"remote-data", "application/pdf", "remote.pdf"

        fake_client = FakeClient()
        other = User.objects.create_user(
            username="remote-other",
            email="remote-other@example.com",
            password="password",
        )
        other_api = APIClient()
        other_api.force_authenticate(user=other)
        url = f"/api/v1/quotation/feishu/documents/{asset.id}/content"
        with patch(
            "quotation.views.feishu.common._client",
            return_value=fake_client,
        ):
            denied = other_api.get(url)
            allowed = self.api.get(url)

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.content, b"remote-data")
        self.assertEqual(fake_client.calls, 1)

    def test_remote_access_uses_document_id_and_hides_direct_link(self):
        quote = self.create_quote()
        asset = DocumentAsset.objects.create(
            quotation=quote,
            doc_type=DocumentType.EXCEL,
            file_name="remote.xlsx",
            mime_type="application/octet-stream",
            storage_key="documents/remote/excel",
            size_bytes=10,
            source="feishu_upload",
            feishu_file_token="remote_excel_token",
            feishu_url="https://example.feishu.cn/file/remote_excel_token",
            created_by_email=self.user.email,
        )

        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def batch_query_file_meta(self, *args, **kwargs):
                return {
                    "doc_token": "remote_excel_token",
                    "doc_type": "file",
                }

            def download_file(self, *args, **kwargs):
                return b"data", "application/octet-stream"

        with patch(
            "quotation.views.feishu.common._client",
            return_value=FakeClient(),
        ):
            response = self.api.get(
                f"/api/v1/quotation/feishu/documents/{asset.id}/access"
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["exists"])
        self.assertFalse(response.data["direct_access_allowed"])
        self.assertNotIn("file_token", response.data)
        self.assertNotIn("url", response.data)

        invalid_batch = self.api.post(
            "/api/v1/quotation/feishu/files/access/batch",
            {"items": [{"file_token": "remote_excel_token"}]},
            format="json",
        )
        self.assertEqual(invalid_batch.status_code, 400)

    def test_remote_access_uses_active_replica_without_legacy_file_token(self):
        quote = self.create_quote()
        asset = DocumentAsset.objects.create(
            quotation=quote,
            doc_type=DocumentType.EXCEL,
            file_name="replica.xlsx",
            mime_type="application/octet-stream",
            storage_key="documents/replica/excel",
            size_bytes=10,
            source="feishu_upload",
            feishu_file_token=None,
            feishu_url=None,
            created_by_email=self.user.email,
        )
        connection = StorageConnection.objects.create(
            display_name="Replica Feishu",
            external_tenant_id="replica-tenant",
            app_id="replica-app",
            app_secret="replica-secret",
        )
        mount = StorageMount.objects.create(
            connection=connection,
            purpose=StorageMountPurpose.QUOTATION_ARCHIVE,
            root_folder_token="folder_token",
        )
        DocumentReplica.objects.create(
            asset=asset,
            connection=connection,
            mount=mount,
            remote_file_token="replica_remote_token",
            remote_url="https://tenant.feishu.cn/file/replica_remote_token",
            folder_token="folder_token",
            sync_status=ReplicaSyncStatus.SYNCED,
        )

        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def batch_query_file_meta(
                self, access_token, file_token, **kwargs
            ):
                self.checked_token = file_token
                return {
                    "doc_token": file_token,
                    "doc_type": "file",
                }

            def download_file(self, access_token, file_token):
                return b"data", "application/octet-stream"

            def download_drive_item(self, access_token, **kwargs):
                self.downloaded_token = kwargs["file_token"]
                return (
                    b"replica-content",
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet",
                    "replica.xlsx",
                )

        fake = FakeClient()

        class FakeProvider:
            def __init__(self, connection):
                self.connection = connection
                self.client = fake

            def access_token(self):
                return "tenant-token"

        with patch(
            "quotation.views.feishu.files.FeishuStorageProvider",
            FakeProvider,
        ):
            access = self.api.get(
                f"/api/v1/quotation/feishu/documents/{asset.id}/access"
            )
            content = self.api.get(
                f"/api/v1/quotation/feishu/documents/{asset.id}/content"
            )

        self.assertEqual(access.status_code, 200)
        self.assertTrue(access.data["exists"])
        self.assertEqual(fake.checked_token, "replica_remote_token")
        self.assertEqual(content.status_code, 200)
        self.assertEqual(content.content, b"replica-content")
        self.assertEqual(fake.downloaded_token, "replica_remote_token")

    def test_remote_access_revokes_missing_active_replica(self):
        quote = self.create_quote()
        quote.status = QuoteStatus.UPLOADED
        quote.save(update_fields=["status"])
        asset = DocumentAsset.objects.create(
            quotation=quote,
            doc_type=DocumentType.PDF,
            file_name="missing.pdf",
            mime_type="application/pdf",
            storage_key="documents/missing/pdf",
            size_bytes=10,
            source="feishu_upload",
            feishu_file_token=None,
            feishu_url=None,
            created_by_email=self.user.email,
        )
        connection = StorageConnection.objects.create(
            display_name="Replica Feishu",
            external_tenant_id="replica-missing",
            app_id="replica-app",
            app_secret="replica-secret",
        )
        mount = StorageMount.objects.create(
            connection=connection,
            purpose=StorageMountPurpose.QUOTATION_ARCHIVE,
            root_folder_token="folder_token",
        )
        replica = DocumentReplica.objects.create(
            asset=asset,
            connection=connection,
            mount=mount,
            remote_file_token="missing_remote_token",
            remote_url="https://tenant.feishu.cn/file/missing_remote_token",
            folder_token="folder_token",
            sync_status=ReplicaSyncStatus.SYNCED,
        )

        class FakeClient:
            def batch_query_file_meta(
                self, access_token, file_token, **kwargs
            ):
                from quotation.services.feishu_client import FeishuAPIError

                raise FeishuAPIError(
                    "meta query failed code=970005",
                    code=970005,
                )

        fake = FakeClient()

        class FakeProvider:
            def __init__(self, connection):
                self.connection = connection
                self.client = fake

            def access_token(self):
                return "tenant-token"

        with patch(
            "quotation.views.feishu.files.FeishuStorageProvider",
            FakeProvider,
        ):
            response = self.api.get(
                f"/api/v1/quotation/feishu/documents/{asset.id}/access"
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["exists"])
        self.assertTrue(response.data["cleared"])
        replica.refresh_from_db()
        quote.refresh_from_db()
        self.assertEqual(replica.sync_status, ReplicaSyncStatus.REVOKED)
        self.assertIsNotNone(replica.revoked_at)
        self.assertEqual(quote.status, QuoteStatus.GENERATED)

    def test_imported_file_access_returns_trusted_feishu_web_url(self):
        asset = DocumentAsset.objects.create(
            doc_type=DocumentType.PDF,
            file_name="imported.pdf",
            mime_type="application/pdf",
            storage_key="documents/imported/file",
            size_bytes=10,
            source="feishu",
            feishu_file_token="imported_token",
            feishu_url="https://attacker.example/file/imported_token",
            created_by_email=self.user.email,
        )

        response = self.api.get(
            f"/api/v1/quotation/feishu/documents/{asset.id}/access"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["exists"])
        self.assertTrue(response.data["direct_access_allowed"])
        self.assertEqual(
            response.data["url"],
            "https://tenant.feishu.cn/file/imported_token",
        )
        self.assertNotIn("file_token", response.data)
