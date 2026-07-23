from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from quotation.models import DocumentAsset, FeishuConnection, Quotation
from quotation.services.quotation_service import (
    build_quotation,
    create_version_snapshot,
)


def quote_payload(quote_no: str = "QA-HARDEN-001") -> dict:
    return {
        "quote_no": quote_no,
        "product_line": "BDR",
        "project_name": "Hardening test",
        "currency": "USD",
        "payment_term_option": "CIA",
        "payment_terms": "CIA",
        "quote_date": "2026-07-15",
        "expire_date": "2026-08-15",
        "vat_rate": "10.00",
        "issuer_contact_name": "QA Admin",
        "issuer_contact_email": "admin@example.com",
        "client_company": "QA Company",
        "contact_person": "QA Contact",
        "email": "qa@example.com",
        "items": [
            {
                "line_no": 1,
                "type": "Software",
                "name": "Cloud subscription",
                "description": "Annual plan",
                "qty": "2.00",
                "list_price": "100.00",
                "discount_percent": "10.00",
                "net_unit_price": "999999.00",
                "extended_price": "999999.00",
            }
        ],
    }


class QuotationBoundaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="qa-hardening",
            email="admin@example.com",
            password="password",
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_server_recomputes_derived_line_amounts_and_totals(self):
        response = self.api.post(
            "/api/v1/quotation/quotations",
            quote_payload(),
            format="json",
        )

        assert response.status_code == 201
        assert Decimal(response.data["items"][0]["net_unit_price"]) == Decimal(
            "90.00"
        )
        assert Decimal(response.data["items"][0]["extended_price"]) == Decimal(
            "180.00"
        )
        assert Decimal(response.data["subtotal_before_vat"]) == Decimal(
            "180.00"
        )
        assert Decimal(response.data["vat_amount"]) == Decimal("18.00")
        assert Decimal(response.data["grand_total"]) == Decimal("198.00")

    def test_rejects_invalid_quantity_discount_price_and_vat_boundaries(self):
        invalid_values = [
            ("qty", "0", "10.00"),
            ("list_price", "-1", "10.00"),
            ("discount_percent", "100.01", "10.00"),
            ("discount_percent", "-0.01", "10.00"),
            ("vat_rate", "101", "101"),
            ("vat_rate", "-0.01", "-0.01"),
        ]
        for index, (field, value, vat_rate) in enumerate(
            invalid_values, start=1
        ):
            payload = quote_payload(f"QA-HARDEN-INVALID-{index}")
            if field == "vat_rate":
                payload["vat_rate"] = vat_rate
            else:
                payload["items"][0][field] = value
            response = self.api.post(
                "/api/v1/quotation/quotations",
                payload,
                format="json",
            )
            assert response.status_code == 400, (field, value, response.data)

    def test_rejects_expiry_date_before_quote_date(self):
        payload = quote_payload("QA-HARDEN-DATE-001")
        payload["expire_date"] = "2026-07-14"

        response = self.api.post(
            "/api/v1/quotation/quotations",
            payload,
            format="json",
        )

        assert response.status_code == 400
        assert "expire_date" in response.data

    def test_rejects_partial_update_that_makes_date_range_invalid(self):
        created = self.api.post(
            "/api/v1/quotation/quotations",
            quote_payload("QA-HARDEN-DATE-UPDATE-001"),
            format="json",
        )

        response = self.api.put(
            f"/api/v1/quotation/quotations/{created.data['id']}",
            {"expire_date": "2026-07-14"},
            format="json",
        )

        assert response.status_code == 400
        assert "expire_date" in response.data

    def test_create_uses_authenticated_user_as_owner(self):
        payload = quote_payload("QA-HARDEN-OWNER-001")
        payload["created_by_email"] = "someone-else@example.com"

        response = self.api.post(
            "/api/v1/quotation/quotations",
            payload,
            format="json",
        )

        assert response.status_code == 201
        assert response.data["created_by_email"] == self.user.email

    def test_invalid_pagination_values_return_validation_error(self):
        for query in ("page=abc", "page_size=all"):
            response = self.api.get(f"/api/v1/quotation/quotations?{query}")

            assert response.status_code == 400
            assert response.data == {"detail": "invalid pagination"}


class QuotationRollbackTests(TestCase):
    def setUp(self):
        self.settings_override = self.settings(
            FEISHU_APP_ID="cli_test",
            FEISHU_APP_SECRET="secret_test",
            QUOTATION_FEISHU_ARCHIVE_FOLDER_TOKEN="folder_token",
        )
        self.settings_override.enable()
        self.user = User.objects.create_user(
            username="qa-rollback",
            email="admin@example.com",
            password="password",
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        self.api.raise_request_exception = False
        created = self.api.post(
            "/api/v1/quotation/quotations",
            quote_payload("QA-ROLLBACK-001"),
            format="json",
        )
        assert created.status_code == 201
        self.quote_id = created.data["id"]

    def tearDown(self):
        self.settings_override.disable()

    def test_update_rolls_back_quote_and_items_when_snapshot_fails(self):
        payload = quote_payload("QA-ROLLBACK-001")
        payload["project_name"] = "Must roll back"
        payload["items"][0]["list_price"] = "500.00"
        payload["status"] = "generated"

        with patch(
            "quotation.views.quotations.create_version_snapshot",
            side_effect=RuntimeError("snapshot unavailable"),
        ):
            response = self.api.put(
                f"/api/v1/quotation/quotations/{self.quote_id}",
                payload,
                format="json",
            )

        assert response.status_code == 500
        quote = Quotation.objects.get(pk=self.quote_id)
        assert quote.project_name == "Hardening test"
        assert quote.status == "draft"
        assert quote.items.get().list_price == Decimal("100.00")
        assert quote.versions.count() == 0

    def test_repeated_generate_is_idempotent(self):
        url = f"/api/v1/quotation/quotations/{self.quote_id}/generate"
        first = self.api.post(url, {}, format="json")
        second = self.api.post(url, {}, format="json")

        assert first.status_code == 200
        assert second.status_code == 200
        quote = Quotation.objects.get(pk=self.quote_id)
        assert quote.status == "generated"
        assert quote.version_current == 1
        assert quote.versions.count() == 1

    def test_feishu_upload_compensates_remote_file_when_database_write_fails(
        self,
    ):
        FeishuConnection.objects.create(
            user=self.user,
            user_email=self.user.email,
            access_token="user-access-token",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        class FakeFeishuClient:
            deleted_tokens = []

            def get_tenant_access_token(self):
                return "tenant-token"

            def get_folder_meta(self, access_token, folder_token):
                return {"token": folder_token, "name": "test"}

            def list_folder_files(self, access_token, folder_token, **kwargs):
                if folder_token == "folder_token":
                    return {
                        "files": [
                            {
                                "token": "fld_test_folder",
                                "name": "Test folder",
                                "type": "folder",
                            }
                        ],
                        "has_more": False,
                    }
                return {"files": [], "has_more": False}

            def upload_file(self, access_token, **kwargs):
                return {
                    "file_token": "qa_remote_orphan",
                    "url": "https://example.feishu.cn/file/qa_remote_orphan",
                }

            def delete_file(self, access_token, file_token):
                self.deleted_tokens.append(file_token)

        fake_client = FakeFeishuClient()
        upload = SimpleUploadedFile(
            "QA-ROLLBACK-001.xlsx",
            b"PK\x03\x04excel bytes",
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        with (
            patch(
                "quotation.views.feishu.common._client",
                return_value=fake_client,
            ),
            patch(
                "quotation.views.feishu.upload.create_version_snapshot",
                side_effect=RuntimeError("snapshot unavailable"),
            ),
        ):
            response = self.api.post(
                "/api/v1/quotation/feishu/upload",
                {
                    "file": upload,
                    "folder": "fld_test_folder",
                    "quotation_id": self.quote_id,
                },
                format="multipart",
            )

        assert response.status_code == 500
        quote = Quotation.objects.get(pk=self.quote_id)
        assert quote.status == "draft"
        assert DocumentAsset.objects.filter(quotation=quote).count() == 0
        assert fake_client.deleted_tokens == ["qa_remote_orphan"]


class QuotationConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_identical_snapshots_create_only_one_version(self):
        payload = quote_payload("QA-CONCURRENT-001")
        items = payload.pop("items")
        quote = build_quotation(data=payload, items_data=items)

        def create_snapshot(_):
            close_old_connections()
            try:
                thread_quote = Quotation.objects.get(pk=quote.pk)
                result = create_version_snapshot(
                    thread_quote,
                    operator_email="admin@example.com",
                    notes="Concurrent generate",
                )
                return result.version_no
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=6) as executor:
            version_numbers = list(executor.map(create_snapshot, range(6)))

        quote.refresh_from_db()
        assert version_numbers == [1] * 6
        assert quote.version_current == 1
        assert quote.versions.count() == 1
