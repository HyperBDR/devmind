from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from quotation.models import (
    DocumentAsset,
    DocumentType,
    FeishuConnection,
    Quotation,
    QuoteStatus,
)
from quotation.serializers import QuotationSerializer
from quotation.services.feishu_client import FeishuAPIError
from quotation.services.quotation_service import (
    build_quotation,
    create_version_snapshot,
)


class QuotationVersionHistoryTests(TestCase):
    def _base_quote_data(self, quote_no: str = "Q-VER-001") -> dict:
        return {
            "quote_no": quote_no,
            "product_line": "BDR",
            "project_name": "Version History Project",
            "currency": "USD",
            "payment_term_option": "CIA",
            "payment_terms": "CIA",
            "quote_date": "2026-07-09",
            "expire_date": "2026-08-08",
            "tax_label": "VAT",
            "vat_rate": Decimal("0"),
            "issuer_company_name": "OnePro Cloud Limited",
            "issuer_contact_name": "Alice Chen",
            "issuer_contact_email": "alice.chen@oneprocloud.com",
            "issuer_contact_title": "",
            "issuer_signature": "",
            "client_company": "Demo Client",
            "contact_person": "Mary Tan",
            "email": "mary@example.com",
            "billing_company": "Demo Client",
            "billing_contact": "Mary Tan",
            "billing_email": "mary@example.com",
            "created_by_email": "alice.chen@oneprocloud.com",
        }

    def test_create_quotation_does_not_write_initial_version(self):
        quotation = build_quotation(
            data=self._base_quote_data(),
            items_data=[
                {
                    "line_no": 1,
                    "type": "Software",
                    "item_id": "SKU-1",
                    "name": "HyperBDR",
                    "description": "License",
                    "qty": Decimal("1"),
                    "list_price": Decimal("1000"),
                    "discount_percent": Decimal("0"),
                    "net_unit_price": Decimal("1000"),
                    "extended_price": Decimal("1000"),
                }
            ],
        )
        assert quotation.versions.count() == 0
        assert quotation.version_current == 0

    def test_status_update_appends_version_and_exposes_via_api(self):
        user = User.objects.create_user(
            username="alice-version",
            email="alice.chen@oneprocloud.com",
            password="password",
        )
        quotation = build_quotation(
            data=self._base_quote_data("Q-VER-002"),
            items_data=[],
        )
        api = APIClient()
        api.force_authenticate(user=user)
        response = api.put(
            f"/api/v1/quotation/quotations/{quotation.id}",
            {
                "status": "sent",
                "notes": "Marked as sent",
                "project_name": quotation.project_name,
                "payment_terms": quotation.payment_terms,
                "quote_date": str(quotation.quote_date),
                "expire_date": str(quotation.expire_date),
                "issuer_contact_name": quotation.issuer_contact_name,
                "issuer_contact_email": quotation.issuer_contact_email,
                "client_company": quotation.client_company,
                "contact_person": quotation.contact_person,
                "email": quotation.email,
                "items": [],
            },
            format="json",
        )
        assert response.status_code == 200
        versions = response.data["versions"]
        assert len(versions) == 1
        assert versions[0]["version_no"] == 1
        assert versions[0]["notes"] == "Marked as sent"
        assert versions[0]["status"] == "sent"
        assert "snapshot" in versions[0]
        assert versions[0]["snapshot"]["status"] == "sent"

    def test_update_skip_version_does_not_append_snapshot(self):
        user = User.objects.create_user(
            username="alice-skip-version",
            email="alice.chen@oneprocloud.com",
            password="password",
        )
        quotation = build_quotation(
            data=self._base_quote_data("Q-VER-004"),
            items_data=[],
        )
        api = APIClient()
        api.force_authenticate(user=user)
        response = api.put(
            f"/api/v1/quotation/quotations/{quotation.id}",
            {
                "status": "generated",
                "notes": "Quote edited",
                "skip_version": True,
                "project_name": quotation.project_name,
                "payment_terms": quotation.payment_terms,
                "quote_date": str(quotation.quote_date),
                "expire_date": str(quotation.expire_date),
                "issuer_contact_name": quotation.issuer_contact_name,
                "issuer_contact_email": quotation.issuer_contact_email,
                "client_company": quotation.client_company,
                "contact_person": quotation.contact_person,
                "email": quotation.email,
                "items": [],
            },
            format="json",
        )
        assert response.status_code == 200
        assert response.data["versions"] == []
        assert response.data["status"] == "generated"

    def test_generate_after_edit_does_not_duplicate_same_snapshot(self):
        user = User.objects.create_user(
            username="alice-generate-dedupe",
            email="alice.chen@oneprocloud.com",
            password="password",
        )
        quotation = build_quotation(
            data=self._base_quote_data("Q-VER-005"),
            items_data=[],
        )
        quotation.status = QuoteStatus.GENERATED
        quotation.save(update_fields=["status", "updated_at"])
        first = create_version_snapshot(
            quotation,
            operator_email=user.email,
            notes="Generated quotation",
        )

        api = APIClient()
        api.force_authenticate(user=user)
        response = api.put(
            f"/api/v1/quotation/quotations/{quotation.id}",
            {
                "status": "generated",
                "notes": "Quote edited",
                "skip_version": True,
                "project_name": quotation.project_name,
                "payment_terms": quotation.payment_terms,
                "quote_date": str(quotation.quote_date),
                "expire_date": str(quotation.expire_date),
                "issuer_contact_name": quotation.issuer_contact_name,
                "issuer_contact_email": quotation.issuer_contact_email,
                "client_company": quotation.client_company,
                "contact_person": quotation.contact_person,
                "email": quotation.email,
                "items": [],
            },
            format="json",
        )
        assert response.status_code == 200

        quotation.refresh_from_db()
        second = create_version_snapshot(
            quotation,
            operator_email=user.email,
            notes="Generated quotation",
        )

        assert second.id == first.id
        assert quotation.versions.count() == 1
        quotation.refresh_from_db()
        assert quotation.version_current == first.version_no

    def test_create_version_snapshot_increments_version_no(self):
        quotation = build_quotation(
            data=self._base_quote_data("Q-VER-003"),
            items_data=[],
        )
        create_version_snapshot(
            quotation,
            operator_email="alice.chen@oneprocloud.com",
            notes="Manual snapshot",
        )
        assert quotation.versions.count() == 1
        latest = quotation.versions.order_by("-version_no").first()
        assert latest.version_no == 1
        assert latest.notes == "Manual snapshot"
        quotation.refresh_from_db()
        assert quotation.version_current == 1

    def test_delete_quotation_removes_row(self):
        user = User.objects.create_user(
            username="alice-delete",
            email="alice.chen@oneprocloud.com",
            password="password",
        )
        quotation = build_quotation(
            data=self._base_quote_data("Q-DEL-001"),
            items_data=[],
        )
        quote_id = quotation.id
        api = APIClient()
        api.force_authenticate(user=user)
        response = api.delete(f"/api/v1/quotation/quotations/{quote_id}")
        assert response.status_code == 204
        assert not Quotation.objects.filter(pk=quote_id).exists()


class QuotationFeishuMetadataTests(TestCase):
    def test_serializer_exposes_latest_feishu_upload_open_url(self):
        quotation = Quotation.objects.create(
            quote_no="Q-FEISHU-001",
            status=QuoteStatus.GENERATED,
            project_name="Feishu Upload Project",
            payment_terms="CIA",
            quote_date="2026-07-09",
            expire_date="2026-08-08",
            issuer_contact_name="Alice Chen",
            issuer_contact_email="alice.chen@oneprocloud.com",
            client_company="Demo Client",
            contact_person="Mary Tan",
            email="mary@example.com",
            created_by_email="alice.chen@oneprocloud.com",
        )
        DocumentAsset.objects.create(
            quotation=quotation,
            doc_type=DocumentType.PDF,
            file_name="Quote-Q-FEISHU-001.pdf",
            mime_type="application/pdf",
            storage_key="feishu_uploads/file_v3_pdf/Quote-Q-FEISHU-001.pdf",
            size_bytes=128,
            source="feishu_upload",
            feishu_file_token="file_v3_pdf",
            feishu_url="https://oneprocloud.feishu.cn/file/file_v3_pdf",
            created_by_email="alice.chen@oneprocloud.com",
        )

        data = QuotationSerializer(quotation).data

        assert data["feishu_file_token"] == "file_v3_pdf"
        assert (
            data["feishu_url"]
            == "https://oneprocloud.feishu.cn/file/file_v3_pdf"
        )
        assert data["feishu_path"] == "Quote-Q-FEISHU-001.pdf"

    def test_serializer_exposes_excel_and_pdf_feishu_links_separately(self):
        quotation = Quotation.objects.create(
            quote_no="Q-FEISHU-004",
            status=QuoteStatus.UPLOADED,
            project_name="Separate Excel PDF",
            payment_terms="CIA",
            quote_date="2026-07-09",
            expire_date="2026-08-08",
            issuer_contact_name="Alice Chen",
            issuer_contact_email="alice.chen@oneprocloud.com",
            client_company="Demo Client",
            contact_person="Mary Tan",
            email="mary@example.com",
            created_by_email="alice.chen@oneprocloud.com",
        )
        DocumentAsset.objects.create(
            quotation=quotation,
            doc_type=DocumentType.EXCEL,
            file_name="Quote-Q-FEISHU-004.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            storage_key="feishu_uploads/file_v3_excel/Quote-Q-FEISHU-004.xlsx",
            size_bytes=256,
            source="feishu_upload",
            feishu_file_token="file_v3_excel",
            feishu_url="https://oneprocloud.feishu.cn/file/file_v3_excel",
            created_by_email="alice.chen@oneprocloud.com",
        )
        DocumentAsset.objects.create(
            quotation=quotation,
            doc_type=DocumentType.PDF,
            file_name="Quote-Q-FEISHU-004.pdf",
            mime_type="application/pdf",
            storage_key="feishu_uploads/file_v3_pdf/Quote-Q-FEISHU-004.pdf",
            size_bytes=128,
            source="feishu_upload",
            feishu_file_token="file_v3_pdf",
            feishu_url="https://oneprocloud.feishu.cn/file/file_v3_pdf",
            created_by_email="alice.chen@oneprocloud.com",
        )

        data = QuotationSerializer(quotation).data

        assert data["feishu_excel_file_token"] == "file_v3_excel"
        assert (
            data["feishu_excel_url"]
            == "https://oneprocloud.feishu.cn/file/file_v3_excel"
        )
        assert data["feishu_excel_path"] == "Quote-Q-FEISHU-004.xlsx"
        assert data["feishu_pdf_file_token"] == "file_v3_pdf"
        assert (
            data["feishu_pdf_url"]
            == "https://oneprocloud.feishu.cn/file/file_v3_pdf"
        )
        assert data["feishu_pdf_path"] == "Quote-Q-FEISHU-004.pdf"


class FeishuImportMetadataTests(TestCase):
    def test_import_preserves_original_feishu_file_url(self):
        user = User.objects.create_user(
            username="alice-import",
            email="alice.import@oneprocloud.com",
            password="password",
        )
        FeishuConnection.objects.create(
            user=user,
            user_email=user.email,
            access_token="user_access_token",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        class FakeFeishuClient:
            def list_folder_files(
                self,
                access_token,
                folder_token,
                *,
                page_size=50,
                page_token=None,
            ):
                return {
                    "files": [
                        {
                            "token": "file_v3_imported",
                            "name": "Quote-Imported.pdf",
                            "type": "file",
                            "url": (
                                "https://oneprocloud.feishu.cn/file/"
                                "file_v3_imported"
                            ),
                        }
                    ],
                    "has_more": False,
                }

            def download_drive_item(
                self,
                access_token,
                *,
                file_token,
                file_type=None,
                file_name=None,
            ):
                return (
                    b"%PDF-1.4 imported",
                    "application/pdf",
                    file_name or "Quote-Imported.pdf",
                )

        api = APIClient()
        api.force_authenticate(user=user)
        feishu_url = "https://oneprocloud.feishu.cn/file/file_v3_imported"

        with patch(
            "quotation.views.feishu.common._client", return_value=FakeFeishuClient()
        ):
            response = api.post(
                "/api/v1/quotation/feishu/import/file_v3_imported?"
                + urlencode(
                    {
                        "file_name": "Quote-Imported.pdf",
                        "file_type": "file",
                        "file_url": feishu_url,
                    }
                ),
            )

        assert response.status_code == 200
        assert response.data["url"] == feishu_url
        assert DocumentAsset.objects.filter(
            source="feishu",
            file_name="Quote-Imported.pdf",
            feishu_file_token="file_v3_imported",
            feishu_url=feishu_url,
        ).exists()


class FeishuUploadReuseTests(TestCase):
    def test_upload_reuses_same_named_file_in_target_folder(self):
        user = User.objects.create_user(
            username="alice",
            email="alice.chen@oneprocloud.com",
            password="password",
        )
        FeishuConnection.objects.create(
            user=user,
            user_email=user.email,
            access_token="user_access_token",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        quotation = Quotation.objects.create(
            quote_no="Q-FEISHU-002",
            status=QuoteStatus.GENERATED,
            project_name="Reuse Existing File",
            payment_terms="CIA",
            quote_date="2026-07-09",
            expire_date="2026-08-08",
            issuer_contact_name="Alice Chen",
            issuer_contact_email="alice.chen@oneprocloud.com",
            client_company="Demo Client",
            contact_person="Mary Tan",
            email="mary@example.com",
            created_by_email="alice.chen@oneprocloud.com",
        )
        DocumentAsset.objects.create(
            quotation=quotation,
            doc_type=DocumentType.PDF,
            file_name="Quote-Q-FEISHU-002.pdf",
            mime_type="application/pdf",
            storage_key="feishu_uploads/file_v3_existing_pdf_Quote-Q-FEISHU-002.pdf",
            size_bytes=11,
            source="feishu_upload",
            feishu_file_token="file_v3_existing_pdf",
            feishu_url="https://oneprocloud.feishu.cn/file/file_v3_existing_pdf",
            created_by_email=user.email,
        )
        DocumentAsset.objects.create(
            quotation=quotation,
            doc_type=DocumentType.PDF,
            file_name="Quote-Q-FEISHU-002.pdf",
            mime_type="application/pdf",
            storage_key="feishu_uploads/file_v3_existing_pdf_duplicate.pdf",
            size_bytes=11,
            source="feishu_upload",
            feishu_file_token="file_v3_existing_pdf",
            feishu_url="https://oneprocloud.feishu.cn/file/file_v3_existing_pdf",
            created_by_email=user.email,
        )

        class FakeFeishuClient:
            upload_calls = []

            def get_folder_meta(self, access_token, folder_token):
                return {"token": folder_token, "name": "Target Folder"}

            def list_folder_files(
                self,
                access_token,
                folder_token,
                *,
                page_size=50,
                page_token=None,
            ):
                return {
                    "files": [
                        {
                            "token": "file_v3_existing_pdf",
                            "name": "Quote-Q-FEISHU-002.pdf",
                            "type": "file",
                            "url": "https://oneprocloud.feishu.cn/file/file_v3_existing_pdf",
                            "size": 11,
                        }
                    ],
                    "has_more": False,
                }

            def upload_file(
                self, access_token, *, folder_token, file_name, content
            ):
                self.upload_calls.append(file_name)
                return {"file_token": "file_v3_new_upload"}

        fake_client = FakeFeishuClient()
        api = APIClient()
        api.force_authenticate(user=user)
        upload = SimpleUploadedFile(
            "Quote-Q-FEISHU-002.pdf",
            b"%PDF-hello world",
            content_type="application/pdf",
        )

        with patch("quotation.views.feishu.common._client", return_value=fake_client):
            conflict_response = api.post(
                "/api/v1/quotation/feishu/upload",
                {
                    "file": upload,
                    "quotation_id": quotation.id,
                },
                format="multipart",
            )

        assert conflict_response.status_code == 409
        assert conflict_response.data["code"] == "feishu_name_conflict"
        assert (
            conflict_response.data["existing"]["file_token"]
            == "file_v3_existing_pdf"
        )
        assert (
            conflict_response.data["suggested_file_name"]
            == "Quote-Q-FEISHU-002 (1).pdf"
        )
        assert fake_client.upload_calls == []

        reuse_upload = SimpleUploadedFile(
            "Quote-Q-FEISHU-002.pdf",
            b"%PDF-hello world",
            content_type="application/pdf",
        )
        with patch("quotation.views.feishu.common._client", return_value=fake_client):
            response = api.post(
                "/api/v1/quotation/feishu/upload",
                {
                    "file": reuse_upload,
                    "quotation_id": quotation.id,
                    "conflict_action": "reuse",
                },
                format="multipart",
            )

        assert response.status_code == 200
        assert response.data["file_token"] == "file_v3_existing_pdf"
        assert (
            response.data["url"]
            == "https://oneprocloud.feishu.cn/file/file_v3_existing_pdf"
        )
        assert response.data["reused_existing"] is True
        assert fake_client.upload_calls == []
        assert DocumentAsset.objects.filter(
            quotation=quotation,
            file_name="Quote-Q-FEISHU-002.pdf",
            source="feishu_upload",
            feishu_file_token="file_v3_existing_pdf",
            feishu_url="https://oneprocloud.feishu.cn/file/file_v3_existing_pdf",
        ).exists()
        assert (
            DocumentAsset.objects.filter(
                quotation=quotation,
                doc_type=DocumentType.PDF,
                source="feishu_upload",
                feishu_file_token="file_v3_existing_pdf",
            ).count()
            == 1
        )
        quotation.refresh_from_db()
        assert quotation.status == QuoteStatus.UPLOADED

    def test_upload_renames_when_same_name_exists(self):
        user = User.objects.create_user(
            username="dave",
            email="dave.li@oneprocloud.com",
            password="password",
        )
        FeishuConnection.objects.create(
            user=user,
            user_email=user.email,
            access_token="user_access_token",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        quotation = Quotation.objects.create(
            quote_no="Q-FEISHU-005",
            status=QuoteStatus.GENERATED,
            project_name="Rename Existing File",
            payment_terms="CIA",
            quote_date="2026-07-09",
            expire_date="2026-08-08",
            issuer_contact_name="Dave Li",
            issuer_contact_email="dave.li@oneprocloud.com",
            client_company="Demo Client",
            contact_person="Mary Tan",
            email="mary@example.com",
            created_by_email="dave.li@oneprocloud.com",
        )

        class FakeFeishuClient:
            upload_calls = []

            def get_folder_meta(self, access_token, folder_token):
                return {"token": folder_token, "name": "Target Folder"}

            def list_folder_files(
                self,
                access_token,
                folder_token,
                *,
                page_size=50,
                page_token=None,
            ):
                return {
                    "files": [
                        {
                            "token": "file_v3_existing_xlsx",
                            "name": "Quote-Q-FEISHU-005.xlsx",
                            "type": "file",
                            "url": "https://oneprocloud.feishu.cn/file/file_v3_existing_xlsx",
                            "size": 12,
                        }
                    ],
                    "has_more": False,
                }

            def upload_file(
                self, access_token, *, folder_token, file_name, content
            ):
                self.upload_calls.append(file_name)
                return {
                    "file_token": "file_v3_renamed_xlsx",
                    "url": "https://oneprocloud.feishu.cn/file/file_v3_renamed_xlsx",
                }

        fake_client = FakeFeishuClient()
        api = APIClient()
        api.force_authenticate(user=user)
        upload = SimpleUploadedFile(
            "Quote-Q-FEISHU-005.xlsx",
            b"PK\x03\x04hello rename",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        with patch("quotation.views.feishu.common._client", return_value=fake_client):
            response = api.post(
                "/api/v1/quotation/feishu/upload",
                {
                    "file": upload,
                    "quotation_id": quotation.id,
                    "conflict_action": "rename",
                },
                format="multipart",
            )

        assert response.status_code == 200
        assert response.data["file_name"] == "Quote-Q-FEISHU-005 (1).xlsx"
        assert response.data["renamed_from"] == "Quote-Q-FEISHU-005.xlsx"
        assert response.data["reused_existing"] is False
        assert fake_client.upload_calls == ["Quote-Q-FEISHU-005 (1).xlsx"]
        assert DocumentAsset.objects.filter(
            quotation=quotation,
            file_name="Quote-Q-FEISHU-005 (1).xlsx",
            source="feishu_upload",
            feishu_file_token="file_v3_renamed_xlsx",
        ).exists()

    def test_upload_resolves_real_file_url_after_new_upload(self):
        user = User.objects.create_user(
            username="carol",
            email="carol.zhang@oneprocloud.com",
            password="password",
        )
        FeishuConnection.objects.create(
            user=user,
            user_email=user.email,
            access_token="user_access_token",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        quotation = Quotation.objects.create(
            quote_no="Q-FEISHU-003",
            status=QuoteStatus.GENERATED,
            project_name="Resolve Uploaded URL",
            payment_terms="CIA",
            quote_date="2026-07-09",
            expire_date="2026-08-08",
            issuer_contact_name="Carol Zhang",
            issuer_contact_email="carol.zhang@oneprocloud.com",
            client_company="Demo Client",
            contact_person="Mary Tan",
            email="mary@example.com",
            created_by_email="carol.zhang@oneprocloud.com",
        )

        class FakeFeishuClient:
            def __init__(self):
                self.uploaded = False

            def get_folder_meta(self, access_token, folder_token):
                return {"token": folder_token, "name": "Target Folder"}

            def list_folder_files(
                self,
                access_token,
                folder_token,
                *,
                page_size=50,
                page_token=None,
            ):
                if not self.uploaded:
                    return {"files": [], "has_more": False}
                return {
                    "files": [
                        {
                            "token": "file_v3_new_pdf",
                            "name": "Quote-Q-FEISHU-003.pdf",
                            "type": "file",
                            "url": "https://oneprocloud.feishu.cn/file/file_v3_new_pdf",
                            "size": 7,
                        }
                    ],
                    "has_more": False,
                }

            def upload_file(
                self, access_token, *, folder_token, file_name, content
            ):
                self.uploaded = True
                return {"file_token": "file_v3_new_pdf"}

        fake_client = FakeFeishuClient()
        api = APIClient()
        api.force_authenticate(user=user)
        upload = SimpleUploadedFile(
            "Quote-Q-FEISHU-003.pdf",
            b"%PDF-content",
            content_type="application/pdf",
        )

        with patch("quotation.views.feishu.common._client", return_value=fake_client):
            response = api.post(
                "/api/v1/quotation/feishu/upload",
                {
                    "file": upload,
                    "quotation_id": quotation.id,
                },
                format="multipart",
            )

        assert response.status_code == 200
        assert response.data["file_token"] == "file_v3_new_pdf"
        assert (
            response.data["url"]
            == "https://oneprocloud.feishu.cn/file/file_v3_new_pdf"
        )
        assert response.data["reused_existing"] is False
        assert DocumentAsset.objects.filter(
            quotation=quotation,
            source="feishu_upload",
            feishu_file_token="file_v3_new_pdf",
            feishu_url="https://oneprocloud.feishu.cn/file/file_v3_new_pdf",
        ).exists()


class FeishuDriveTreeTests(TestCase):
    def test_drive_tree_keeps_accessible_shared_nested_folders(self):
        user = User.objects.create_user(
            username="shared-tree",
            email="shared.tree@oneprocloud.com",
            password="password",
        )
        FeishuConnection.objects.create(
            user=user,
            user_email=user.email,
            access_token="user_access_token",
            expires_at=timezone.now() + timedelta(hours=1),
            scope="drive:file search:docs:read",
        )

        class FakeFeishuClient:
            def get_root_folder_meta(self, access_token):
                return {"token": "root_token"}

            def list_folder_files(
                self,
                access_token,
                folder_token,
                *,
                page_size=50,
                page_token=None,
            ):
                if folder_token == "root_token":
                    return {
                        "files": [
                            {
                                "token": "my_folder",
                                "name": "test",
                                "type": "folder",
                            }
                        ],
                        "has_more": False,
                    }
                return {"files": [], "has_more": False}

            def search_folders(self, access_token, *, query, page_size=20):
                if query == "a":
                    return [
                        {
                            "token": "shared_nested",
                            "name": "**From Evelyn",
                            "type": "folder",
                        }
                    ]
                return []

            def get_folder_meta(self, access_token, folder_token):
                if folder_token == "shared_nested":
                    return {
                        "token": "shared_nested",
                        "name": "**From Evelyn",
                        "parentId": "not_root",
                    }
                return {
                    "token": folder_token,
                    "name": folder_token,
                    "parentId": "0",
                }

        api = APIClient()
        api.force_authenticate(user=user)
        with patch(
            "quotation.views.feishu.common._client", return_value=FakeFeishuClient()
        ):
            response = api.get("/api/v1/quotation/feishu/drive-tree")

        assert response.status_code == 200
        assert response.data["my_folders"] == []
        assert response.data["shared_folders"] == []
        assert response.data["can_discover_shared"] is False

    def test_drive_tree_collapses_discovered_shared_children_under_parent(
        self,
    ):
        user = User.objects.create_user(
            username="shared-parent",
            email="shared.parent@oneprocloud.com",
            password="password",
        )
        FeishuConnection.objects.create(
            user=user,
            user_email=user.email,
            access_token="user_access_token",
            expires_at=timezone.now() + timedelta(hours=1),
            scope="drive:file search:docs:read",
        )

        class FakeFeishuClient:
            def get_root_folder_meta(self, access_token):
                return {"token": "my_root"}

            def list_folder_files(
                self,
                access_token,
                folder_token,
                *,
                page_size=50,
                page_token=None,
            ):
                return {"files": [], "has_more": False}

            def search_folders(self, access_token, *, query, page_size=20):
                if query == "t":
                    return [
                        {"token": "tower", "name": "Tower", "type": "folder"},
                        {
                            "token": "shared_child",
                            "name": "**From Evelyn",
                            "type": "folder",
                        },
                    ]
                if query == "a":
                    return [
                        {
                            "token": "shared_grandchild",
                            "name": "Alibaba Malaysia_Philip Capital",
                            "type": "folder",
                        }
                    ]
                return []

            def get_folder_meta(self, access_token, folder_token):
                meta = {
                    "tower": {
                        "token": "tower",
                        "id": "tower_id",
                        "name": "Tower",
                        "parentId": "0",
                    },
                    "shared_child": {
                        "token": "shared_child",
                        "id": "child_id",
                        "name": "**From Evelyn",
                        "parentId": "tower_id",
                    },
                    "shared_grandchild": {
                        "token": "shared_grandchild",
                        "id": "grandchild_id",
                        "name": "Alibaba Malaysia_Philip Capital",
                        "parentId": "child_id",
                    },
                }
                return meta[folder_token]

        api = APIClient()
        api.force_authenticate(user=user)
        with patch(
            "quotation.views.feishu.common._client", return_value=FakeFeishuClient()
        ):
            response = api.get("/api/v1/quotation/feishu/drive-tree")

        assert response.status_code == 200
        assert response.data["shared_folders"] == []
        assert response.data["can_discover_shared"] is False

    def test_drive_tree_does_not_prune_accessible_bookmarked_shared_folder(
        self,
    ):
        user = User.objects.create_user(
            username="shared-bookmark",
            email="shared.bookmark@oneprocloud.com",
            password="password",
        )
        connection = FeishuConnection.objects.create(
            user=user,
            user_email=user.email,
            access_token="user_access_token",
            expires_at=timezone.now() + timedelta(hours=1),
            scope="drive:file search:docs:read",
            shared_folder_bookmarks=[
                {
                    "token": "bookmarked_nested",
                    "name": "Pinned Shared Folder",
                    "type": "folder",
                }
            ],
        )

        class FakeFeishuClient:
            def get_root_folder_meta(self, access_token):
                return {"token": "root_token"}

            def list_folder_files(
                self,
                access_token,
                folder_token,
                *,
                page_size=50,
                page_token=None,
            ):
                return {"files": [], "has_more": False}

            def search_folders(self, access_token, *, query, page_size=20):
                return []

            def get_folder_meta(self, access_token, folder_token):
                return {
                    "token": folder_token,
                    "name": "Pinned Shared Folder",
                    "parentId": "not_root",
                }

        api = APIClient()
        api.force_authenticate(user=user)
        with patch(
            "quotation.views.feishu.common._client", return_value=FakeFeishuClient()
        ):
            response = api.get("/api/v1/quotation/feishu/drive-tree")

        assert response.status_code == 200
        assert response.data["shared_folders"] == []
        connection.refresh_from_db()
        assert (
            connection.shared_folder_bookmarks
            == [
                {
                    "token": "bookmarked_nested",
                    "name": "Pinned Shared Folder",
                    "type": "folder",
                }
            ]
        )

    def test_drive_tree_does_not_auto_append_discovered_roots_when_bookmarks_exist(
        self,
    ):
        user = User.objects.create_user(
            username="shared-bookmark-existing",
            email="shared.bookmark.existing@oneprocloud.com",
            password="password",
        )
        connection = FeishuConnection.objects.create(
            user=user,
            user_email=user.email,
            access_token="user_access_token",
            expires_at=timezone.now() + timedelta(hours=1),
            scope="drive:file search:docs:read",
            shared_folder_bookmarks=[
                {
                    "token": "tower",
                    "name": "Tower",
                    "type": "folder",
                }
            ],
        )

        class FakeFeishuClient:
            def get_root_folder_meta(self, access_token):
                return {"token": "root_token"}

            def list_folder_files(
                self,
                access_token,
                folder_token,
                *,
                page_size=50,
                page_token=None,
            ):
                return {"files": [], "has_more": False}

            def search_folders(self, access_token, *, query, page_size=20):
                return [
                    {
                        "token": "extra_shared_root",
                        "name": "Unexpected Shared Root",
                        "type": "folder",
                    }
                ]

            def get_folder_meta(self, access_token, folder_token):
                return {
                    "token": folder_token,
                    "id": f"{folder_token}_id",
                    "name": (
                        "Tower"
                        if folder_token == "tower"
                        else "Unexpected Shared Root"
                    ),
                    "parentId": "0",
                }

        api = APIClient()
        api.force_authenticate(user=user)
        with patch(
            "quotation.views.feishu.common._client", return_value=FakeFeishuClient()
        ):
            response = api.get("/api/v1/quotation/feishu/drive-tree")

        assert response.status_code == 200
        assert response.data["shared_folders"] == []
        connection.refresh_from_db()
        assert connection.shared_folder_bookmarks == [
            {"token": "tower", "name": "Tower", "type": "folder"}
        ]


class FeishuFileAccessTests(TestCase):
    def test_access_clears_missing_file_links(self):
        user = User.objects.create_user(
            username="bob",
            email="bob@oneprocloud.com",
            password="password",
        )
        FeishuConnection.objects.create(
            user=user,
            user_email=user.email,
            access_token="user_access_token",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        quotation = Quotation.objects.create(
            quote_no="Q-FEISHU-MISSING",
            status=QuoteStatus.UPLOADED,
            project_name="Missing Feishu File",
            payment_terms="CIA",
            quote_date="2026-07-09",
            expire_date="2026-08-08",
            issuer_contact_name="Bob",
            issuer_contact_email="bob@oneprocloud.com",
            client_company="Demo Client",
            contact_person="Mary Tan",
            email="mary@example.com",
            created_by_email="bob@oneprocloud.com",
        )
        asset = DocumentAsset.objects.create(
            quotation=quotation,
            doc_type=DocumentType.EXCEL,
            file_name="Quote-Q-FEISHU-MISSING.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            storage_key="feishu_uploads/file_v3_missing/Quote.xlsx",
            size_bytes=12,
            source="feishu_upload",
            feishu_file_token="file_v3_missing",
            feishu_url="https://oneprocloud.feishu.cn/file/file_v3_missing",
            created_by_email="bob@oneprocloud.com",
        )

        class FakeFeishuClient:
            def batch_query_file_meta(
                self,
                access_token,
                file_token,
                *,
                doc_type="file",
                with_url=True,
            ):
                raise FeishuAPIError(
                    "meta query failed code=970005",
                    code=970005,
                )

        api = APIClient()
        api.force_authenticate(user=user)
        with patch(
            "quotation.views.feishu.common._client", return_value=FakeFeishuClient()
        ):
            response = api.get(
                f"/api/v1/quotation/feishu/documents/{asset.id}/access",
            )

        assert response.status_code == 200
        assert response.data["exists"] is False
        assert response.data["cleared"] is True
        asset.refresh_from_db()
        quotation.refresh_from_db()
        assert asset.feishu_file_token is None
        assert asset.feishu_url is None
        assert quotation.status == QuoteStatus.GENERATED

    def test_access_clears_missing_file_without_quotation_filter(self):
        user = User.objects.create_user(
            username="dave",
            email="dave@oneprocloud.com",
            password="password",
        )
        FeishuConnection.objects.create(
            user=user,
            user_email=user.email,
            access_token="user_access_token",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        asset = DocumentAsset.objects.create(
            doc_type=DocumentType.PDF,
            file_name="orphan.pdf",
            mime_type="application/pdf",
            storage_key="imports/orphan.pdf",
            size_bytes=12,
            source="feishu",
            feishu_file_token="file_v3_orphan",
            feishu_url="https://oneprocloud.feishu.cn/file/file_v3_orphan",
            created_by_email="dave@oneprocloud.com",
        )

        class FakeFeishuClient:
            def batch_query_file_meta(
                self,
                access_token,
                file_token,
                *,
                doc_type="file",
                with_url=True,
            ):
                raise FeishuAPIError(
                    "meta query failed code=970005",
                    code=970005,
                )

        api = APIClient()
        api.force_authenticate(user=user)
        with patch(
            "quotation.views.feishu.common._client", return_value=FakeFeishuClient()
        ):
            response = api.get(
                f"/api/v1/quotation/feishu/documents/{asset.id}/access"
            )

        assert response.status_code == 200
        assert response.data["exists"] is True
        assert response.data["direct_access_allowed"] is True
        asset.refresh_from_db()
        assert asset.feishu_file_token == "file_v3_orphan"

    def test_access_returns_url_when_file_exists(self):
        user = User.objects.create_user(
            username="carol",
            email="carol@oneprocloud.com",
            password="password",
        )
        FeishuConnection.objects.create(
            user=user,
            user_email=user.email,
            access_token="user_access_token",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        asset = DocumentAsset.objects.create(
            doc_type=DocumentType.PDF,
            file_name="alive.pdf",
            mime_type="application/pdf",
            storage_key="imports/alive.pdf",
            size_bytes=12,
            source="feishu",
            feishu_file_token="file_v3_alive",
            feishu_url=(
                "https://oneprocloud.feishu.cn/file/file_v3_alive"
            ),
            created_by_email="carol@oneprocloud.com",
        )

        class FakeFeishuClient:
            def batch_query_file_meta(
                self,
                access_token,
                file_token,
                *,
                doc_type="file",
                with_url=True,
            ):
                return {
                    "doc_token": file_token,
                    "doc_type": "file",
                    "title": "Quote.xlsx",
                    "url": f"https://oneprocloud.feishu.cn/file/{file_token}",
                }

            def download_file(self, access_token, file_token):
                return b"file-content", "application/pdf"

        api = APIClient()
        api.force_authenticate(user=user)
        with patch(
            "quotation.views.feishu.common._client", return_value=FakeFeishuClient()
        ):
            response = api.get(
                f"/api/v1/quotation/feishu/documents/{asset.id}/access"
            )

        assert response.status_code == 200
        assert response.data["exists"] is True
        assert "file_v3_alive" in response.data["url"]

    def test_access_clears_link_when_meta_exists_but_download_is_gone(self):
        user = User.objects.create_user(
            username="gina",
            email="gina@oneprocloud.com",
            password="password",
        )
        FeishuConnection.objects.create(
            user=user,
            user_email=user.email,
            access_token="user_access_token",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        quotation = Quotation.objects.create(
            quote_no="Q-FEISHU-DOWNLOAD-GONE",
            status=QuoteStatus.UPLOADED,
            project_name="Deleted Uploaded PDF",
            payment_terms="CIA",
            quote_date="2026-07-09",
            expire_date="2026-08-08",
            issuer_contact_name="Gina",
            issuer_contact_email="gina@oneprocloud.com",
            client_company="Demo Client",
            contact_person="Mary Tan",
            email="mary@example.com",
            created_by_email="gina@oneprocloud.com",
        )
        asset = DocumentAsset.objects.create(
            quotation=quotation,
            doc_type=DocumentType.PDF,
            file_name="Quote-Q-FEISHU-DOWNLOAD-GONE.pdf",
            mime_type="application/pdf",
            storage_key="feishu_uploads/file_v3_download_gone/Quote.pdf",
            size_bytes=128,
            source="feishu_upload",
            feishu_file_token="file_v3_download_gone",
            feishu_url="https://oneprocloud.feishu.cn/file/file_v3_download_gone",
            created_by_email="gina@oneprocloud.com",
        )

        class FakeFeishuClient:
            def batch_query_file_meta(
                self,
                access_token,
                file_token,
                *,
                doc_type="file",
                with_url=True,
            ):
                return {
                    "doc_token": file_token,
                    "doc_type": "file",
                    "title": "Quote.pdf",
                    "url": f"https://oneprocloud.feishu.cn/file/{file_token}",
                }

            def download_file(self, access_token, file_token):
                raise FeishuAPIError("download failed HTTP 404: {'msg': ''}")

        api = APIClient()
        api.force_authenticate(user=user)
        with patch(
            "quotation.views.feishu.common._client", return_value=FakeFeishuClient()
        ):
            response = api.get(
                f"/api/v1/quotation/feishu/documents/{asset.id}/access",
            )

        assert response.status_code == 200
        assert response.data["exists"] is False
        assert response.data["cleared"] is True
        asset.refresh_from_db()
        assert asset.feishu_file_token is None
        assert asset.feishu_url is None

    def test_batch_access_clears_missing_pdf_link(self):
        user = User.objects.create_user(
            username="erin",
            email="erin@oneprocloud.com",
            password="password",
        )
        FeishuConnection.objects.create(
            user=user,
            user_email=user.email,
            access_token="user_access_token",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        quotation = Quotation.objects.create(
            quote_no="Q-FEISHU-BATCH",
            status=QuoteStatus.UPLOADED,
            project_name="Batch Missing PDF",
            payment_terms="CIA",
            quote_date="2026-07-09",
            expire_date="2026-08-08",
            issuer_contact_name="Erin",
            issuer_contact_email="erin@oneprocloud.com",
            client_company="Demo Client",
            contact_person="Mary Tan",
            email="mary@example.com",
            created_by_email="erin@oneprocloud.com",
        )
        pdf_asset = DocumentAsset.objects.create(
            quotation=quotation,
            doc_type=DocumentType.PDF,
            file_name="Quote-Q-FEISHU-BATCH.pdf",
            mime_type="application/pdf",
            storage_key="feishu_uploads/file_v3_batch_pdf/Quote.pdf",
            size_bytes=128,
            source="feishu_upload",
            feishu_file_token="file_v3_batch_pdf",
            feishu_url="https://oneprocloud.feishu.cn/file/file_v3_batch_pdf",
            created_by_email="erin@oneprocloud.com",
        )
        excel_asset = DocumentAsset.objects.create(
            quotation=quotation,
            doc_type=DocumentType.EXCEL,
            file_name="Quote-Q-FEISHU-BATCH.xlsx",
            mime_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            storage_key="feishu_uploads/file_v3_batch_excel/Quote.xlsx",
            size_bytes=256,
            source="feishu_upload",
            feishu_file_token="file_v3_batch_excel",
            feishu_url="https://oneprocloud.feishu.cn/file/file_v3_batch_excel",
            created_by_email="erin@oneprocloud.com",
        )

        class FakeFeishuClient:
            def batch_query_files_meta(
                self,
                access_token,
                file_tokens,
                *,
                doc_type="file",
                with_url=False,
            ):
                metas = []
                failed = []
                for token in file_tokens:
                    if token == "file_v3_batch_pdf":
                        failed.append({"token": token, "code": 970005})
                    else:
                        metas.append({"doc_token": token, "doc_type": "file"})
                return metas, failed

            def download_file(self, access_token, file_token):
                return b"file-content", "application/octet-stream"

        api = APIClient()
        api.force_authenticate(user=user)
        with patch(
            "quotation.views.feishu.common._client", return_value=FakeFeishuClient()
        ):
            response = api.post(
                "/api/v1/quotation/feishu/files/access/batch",
                {
                    "items": [
                        {
                            "document_id": pdf_asset.id,
                        },
                        {
                            "document_id": excel_asset.id,
                        },
                    ]
                },
                format="json",
            )

        assert response.status_code == 200
        results = {
            item["document_id"]: item for item in response.data["results"]
        }
        assert results[pdf_asset.id]["exists"] is False
        assert results[excel_asset.id]["exists"] is True
        pdf_asset.refresh_from_db()
        excel_asset.refresh_from_db()
        assert pdf_asset.feishu_file_token is None
        assert excel_asset.feishu_file_token == "file_v3_batch_excel"
        serializer_data = QuotationSerializer(quotation).data
        assert serializer_data["feishu_pdf_file_token"] is None
        assert (
            serializer_data["feishu_excel_file_token"] == "file_v3_batch_excel"
        )

    def test_batch_access_clears_link_when_meta_exists_but_download_is_gone(
        self,
    ):
        user = User.objects.create_user(
            username="henry",
            email="henry@oneprocloud.com",
            password="password",
        )
        FeishuConnection.objects.create(
            user=user,
            user_email=user.email,
            access_token="user_access_token",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        quotation = Quotation.objects.create(
            quote_no="Q-FEISHU-BATCH-DOWNLOAD-GONE",
            status=QuoteStatus.UPLOADED,
            project_name="Batch Download Gone",
            payment_terms="CIA",
            quote_date="2026-07-09",
            expire_date="2026-08-08",
            issuer_contact_name="Henry",
            issuer_contact_email="henry@oneprocloud.com",
            client_company="Demo Client",
            contact_person="Mary Tan",
            email="mary@example.com",
            created_by_email="henry@oneprocloud.com",
        )
        asset = DocumentAsset.objects.create(
            quotation=quotation,
            doc_type=DocumentType.EXCEL,
            file_name="Quote-Q-FEISHU-BATCH-DOWNLOAD-GONE.xlsx",
            mime_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            storage_key="feishu_uploads/file_v3_batch_download_gone/Quote.xlsx",
            size_bytes=256,
            source="feishu_upload",
            feishu_file_token="file_v3_batch_download_gone",
            feishu_url="https://oneprocloud.feishu.cn/file/file_v3_batch_download_gone",
            created_by_email="henry@oneprocloud.com",
        )

        class FakeFeishuClient:
            def batch_query_files_meta(
                self,
                access_token,
                file_tokens,
                *,
                doc_type="file",
                with_url=False,
            ):
                return [
                    {"doc_token": token, "doc_type": "file"}
                    for token in file_tokens
                ], []

            def download_file(self, access_token, file_token):
                raise FeishuAPIError("download failed HTTP 404: {'msg': ''}")

        api = APIClient()
        api.force_authenticate(user=user)
        with patch(
            "quotation.views.feishu.common._client", return_value=FakeFeishuClient()
        ):
            response = api.post(
                "/api/v1/quotation/feishu/files/access/batch",
                {
                    "items": [
                        {
                            "document_id": asset.id,
                        }
                    ]
                },
                format="json",
            )

        assert response.status_code == 200
        assert response.data["results"][0]["exists"] is False
        assert response.data["cleared_count"] == 1
        asset.refresh_from_db()
        quotation.refresh_from_db()
        assert asset.feishu_file_token is None
        assert asset.feishu_url is None
        assert quotation.status == QuoteStatus.GENERATED

    def test_batch_access_marks_unreturned_tokens_as_missing(self):
        user = User.objects.create_user(
            username="fay",
            email="fay@oneprocloud.com",
            password="password",
        )
        FeishuConnection.objects.create(
            user=user,
            user_email=user.email,
            access_token="user_access_token",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        asset = DocumentAsset.objects.create(
            doc_type=DocumentType.PDF,
            file_name="ghost.pdf",
            mime_type="application/pdf",
            storage_key="imports/ghost.pdf",
            size_bytes=12,
            source="feishu",
            feishu_file_token="file_v3_ghost",
            feishu_url="https://oneprocloud.feishu.cn/file/file_v3_ghost",
            created_by_email="fay@oneprocloud.com",
        )

        class FakeFeishuClient:
            def batch_query_files_meta(
                self,
                access_token,
                file_tokens,
                *,
                doc_type="file",
                with_url=False,
            ):
                return [], []

        api = APIClient()
        api.force_authenticate(user=user)
        with patch(
            "quotation.views.feishu.common._client", return_value=FakeFeishuClient()
        ):
            response = api.post(
                "/api/v1/quotation/feishu/files/access/batch",
                {
                    "items": [
                        {
                            "document_id": asset.id,
                        }
                    ]
                },
                format="json",
            )

        assert response.status_code == 200
        assert response.data["results"][0]["exists"] is False
        asset.refresh_from_db()
        assert asset.feishu_file_token is None
