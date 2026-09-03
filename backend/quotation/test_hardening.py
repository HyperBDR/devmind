from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from quotation.models import (
    DocumentAsset,
    FeishuConnection,
    Quotation,
    QuotationUploadPermission,
)
from quotation.services.quotation_service import (
    build_quotation,
    create_version_snapshot,
    formalize_quotation,
    update_quotation,
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

    def test_preserves_four_decimal_discount_percentage(self):
        payload = quote_payload("QA-HARDEN-PRECISE-DISCOUNT")
        payload["items"][0].update(
            {
                "qty": "14",
                "list_price": "1574.07",
                "discount_percent": "71.7647",
            }
        )

        response = self.api.post(
            "/api/v1/quotation/quotations",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        item = response.data["items"][0]
        self.assertEqual(
            Decimal(item["discount_percent"]),
            Decimal("71.7647"),
        )
        self.assertEqual(Decimal(item["net_unit_price"]), Decimal("444.44"))
        self.assertEqual(
            Decimal(item["extended_price"]),
            Decimal("6222.16"),
        )
        stored = Quotation.objects.get(pk=response.data["id"]).items.get()
        self.assertEqual(stored.discount_percent, Decimal("71.7647"))

    def test_auto_numbering_is_deferred_until_formal_generation(self):
        first_payload = quote_payload("ignored-by-auto-numbering")
        first_payload["numbering_mode"] = "auto"
        first = self.api.post(
            "/api/v1/quotation/quotations",
            first_payload,
            format="json",
        )
        self.assertEqual(first.status_code, 201, first.data)
        self.assertIsNone(first.data["quote_no"])
        self.assertEqual(first.data["display_quote_no"], "BDR150726")

        other = User.objects.create_user(
            username="qa-hardening-other",
            email="other@example.com",
            password="password",
        )
        other_api = APIClient()
        other_api.force_authenticate(user=other)
        second_payload = quote_payload("also-ignored-by-auto-numbering")
        second_payload["numbering_mode"] = "auto"
        second = other_api.post(
            "/api/v1/quotation/quotations",
            second_payload,
            format="json",
        )
        self.assertEqual(second.status_code, 201, second.data)
        self.assertIsNone(second.data["quote_no"])
        self.assertEqual(second.data["display_quote_no"], "BDR150726")

        generate = self.api.post(
            f"/api/v1/quotation/quotations/{first.data['id']}/generate",
            {"numbering_mode": "auto"},
            format="json",
        )
        self.assertEqual(generate.status_code, 200, generate.data)
        self.assertEqual(generate.data["quote_no"], "BDR150726")

        generate_other = other_api.post(
            f"/api/v1/quotation/quotations/{second.data['id']}/generate",
            {"numbering_mode": "auto"},
            format="json",
        )
        self.assertEqual(generate_other.status_code, 200, generate_other.data)
        self.assertEqual(generate_other.data["quote_no"], "BDR150726.1")

    def test_auto_numbering_reserves_roots_from_formal_revision_history(self):
        payload = quote_payload("ignored-by-auto-numbering")
        payload["numbering_mode"] = "auto"
        created = self.api.post(
            "/api/v1/quotation/quotations",
            payload,
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)

        generated = self.api.post(
            f"/api/v1/quotation/quotations/{created.data['id']}/generate",
            {"numbering_mode": "auto"},
            format="json",
        )
        self.assertEqual(generated.status_code, 200, generated.data)
        self.assertEqual(generated.data["quote_no"], "BDR150726")

        revised = self.api.put(
            f"/api/v1/quotation/quotations/{created.data['id']}",
            {"project_name": "Formal revision"},
            format="json",
        )
        self.assertEqual(revised.status_code, 200, revised.data)
        self.assertEqual(revised.data["quote_no"], "BDR150726_R1")

        next_draft = self.api.post(
            "/api/v1/quotation/quotations",
            payload,
            format="json",
        )
        self.assertEqual(next_draft.status_code, 201, next_draft.data)
        next_generated = self.api.post(
            f"/api/v1/quotation/quotations/{next_draft.data['id']}/generate",
            {"numbering_mode": "auto"},
            format="json",
        )
        self.assertEqual(next_generated.status_code, 200, next_generated.data)
        self.assertEqual(next_generated.data["quote_no"], "BDR150726.1")

    def test_draft_does_not_require_a_custom_number(self):
        payload = quote_payload()
        payload.pop("quote_no")
        payload["numbering_mode"] = "custom"

        response = self.api.post(
            "/api/v1/quotation/quotations",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data["quote_no"])
        self.assertEqual(response.data["display_quote_no"], "")
        quotation = Quotation.objects.get(pk=response.data["id"])
        self.assertEqual(quotation.version_current, 0)
        self.assertEqual(quotation.versions.count(), 0)

        generate = self.api.post(
            f"/api/v1/quotation/quotations/{quotation.pk}/generate",
            {},
            format="json",
        )

        self.assertEqual(generate.status_code, 400)
        self.assertIn("quote_no", generate.data["detail"])

    def test_status_transition_formalizes_a_draft_before_marking_it_sent(self):
        payload = quote_payload("CUSTOM-SENT-DRAFT")
        payload["numbering_mode"] = "custom"
        created = self.api.post(
            "/api/v1/quotation/quotations",
            payload,
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)

        updated = self.api.put(
            f"/api/v1/quotation/quotations/{created.data['id']}",
            {
                "status": "sent",
                "quote_no": "CUSTOM-SENT-DRAFT",
            },
            format="json",
        )

        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data["status"], "sent")
        self.assertEqual(updated.data["quote_no"], "CUSTOM-SENT-DRAFT")
        self.assertEqual(updated.data["version_current"], 1)
        self.assertEqual(len(updated.data["versions"]), 1)
        self.assertEqual(updated.data["versions"][0]["status"], "sent")

    def test_first_formal_generation_uses_final_draft_values(self):
        payload = quote_payload("ignored-preview")
        payload["numbering_mode"] = "auto"
        created = self.api.post(
            "/api/v1/quotation/quotations",
            payload,
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        created_at = created.data["created_at"]

        updated = self.api.put(
            f"/api/v1/quotation/quotations/{created.data['id']}",
            {
                "product_line": "CloudX",
                "quote_date": "2026-07-16",
                "expire_date": "2026-08-16",
            },
            format="json",
        )
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertIsNone(updated.data["quote_no"])
        self.assertEqual(updated.data["display_quote_no"], "CloudX160726")

        generated = self.api.post(
            f"/api/v1/quotation/quotations/{created.data['id']}/generate",
            {},
            format="json",
        )
        self.assertEqual(generated.status_code, 200, generated.data)
        self.assertEqual(generated.data["quote_no"], "CloudX160726")
        self.assertEqual(generated.data["version_current"], 1)
        self.assertEqual(len(generated.data["versions"]), 1)
        self.assertEqual(generated.data["created_at"], created_at)

    def test_custom_number_is_validated_only_when_formally_generated(self):
        payload = quote_payload("CUSTOM-DRAFT-001")
        payload["numbering_mode"] = "custom"
        created = self.api.post(
            "/api/v1/quotation/quotations",
            payload,
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        self.assertIsNone(created.data["quote_no"])
        self.assertEqual(created.data["display_quote_no"], "CUSTOM-DRAFT-001")

        generated = self.api.post(
            f"/api/v1/quotation/quotations/{created.data['id']}/generate",
            {},
            format="json",
        )
        self.assertEqual(generated.status_code, 200, generated.data)
        self.assertEqual(generated.data["quote_no"], "CUSTOM-DRAFT-001")

    def test_formalize_quotation_clears_draft_candidate(self):
        payload = quote_payload("SERVICE-PREVIEW")
        payload["numbering_mode"] = "custom"
        items = payload.pop("items")
        quotation = build_quotation(
            data={
                **payload,
                "quote_no": None,
                "draft_quote_no": "SERVICE-PREVIEW",
            },
            items_data=items,
        )

        formalize_quotation(
            quotation,
            operator_email=self.user.email,
            notes="Generated quotation",
        )

        quotation.refresh_from_db()
        self.assertEqual(quotation.quote_no, "SERVICE-PREVIEW")
        self.assertEqual(quotation.draft_quote_no, "")
        self.assertEqual(quotation.version_current, 1)

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

    def test_rejects_invalid_currency_and_email_fields(self):
        invalid_fields = (
            ("currency", "NOT-A-CURRENCY"),
            ("email", "not-an-email"),
            ("billing_email", "not-an-email"),
            ("issuer_contact_email", "not-an-email"),
        )
        for index, (field, value) in enumerate(invalid_fields, start=1):
            with self.subTest(field=field):
                payload = quote_payload(f"QA-HARDEN-FIELD-{index}")
                payload[field] = value

                response = self.api.post(
                    "/api/v1/quotation/quotations",
                    payload,
                    format="json",
                )

                assert response.status_code == 400
                assert field in response.data

    def test_rejects_model_field_lengths_and_invalid_item_type(self):
        invalid_fields = (
            ("quote_no", "Q" * 121),
            ("product_line", "L" * 41),
            ("product_line_name", "L" * 121),
            ("project_name", "P" * 256),
            ("payment_terms", "T" * 256),
            ("tax_label", "T" * 41),
            ("issuer_company_name", "I" * 256),
            ("issuer_contact_name", "I" * 121),
            ("issuer_contact_title", "I" * 121),
            ("client_company", "C" * 256),
            ("contact_person", "C" * 121),
            ("billing_company", "B" * 256),
            ("billing_contact", "B" * 121),
        )
        for index, (field, value) in enumerate(invalid_fields, start=1):
            with self.subTest(field=field):
                payload = quote_payload(f"QA-HARDEN-LENGTH-{index}")
                payload[field] = value

                response = self.api.post(
                    "/api/v1/quotation/quotations",
                    payload,
                    format="json",
                )

                assert response.status_code == 400
                assert field in response.data

        item_payload = quote_payload("QA-HARDEN-ITEM-TYPE")
        item_payload["items"][0]["type"] = "Unsupported"

        response = self.api.post(
            "/api/v1/quotation/quotations",
            item_payload,
            format="json",
        )

        assert response.status_code == 400
        assert "type" in response.data["items"][0]

        for field, value in (("item_id", "I" * 121), ("name", "N" * 256)):
            with self.subTest(item_field=field):
                payload = quote_payload(f"QA-HARDEN-ITEM-{field.upper()}")
                payload["items"][0][field] = value

                response = self.api.post(
                    "/api/v1/quotation/quotations",
                    payload,
                    format="json",
                )

                assert response.status_code == 400
                assert field in response.data["items"][0]

    def test_rejects_bounded_text_and_payment_term_combinations(self):
        invalid_values = (
            ("remarks_disclaimer", "R" * 10001),
            ("issuer_signature", "S" * (3 * 1024 * 1024 + 1)),
        )
        for index, (field, value) in enumerate(invalid_values, start=1):
            with self.subTest(field=field):
                payload = quote_payload(f"QA-HARDEN-TEXT-{index}")
                payload[field] = value

                response = self.api.post(
                    "/api/v1/quotation/quotations",
                    payload,
                    format="json",
                )

                assert response.status_code == 400
                assert field in response.data

        description = quote_payload("QA-HARDEN-DESCRIPTION")
        description["items"][0]["description"] = "D" * 4001
        response = self.api.post(
            "/api/v1/quotation/quotations",
            description,
            format="json",
        )
        assert response.status_code == 400
        assert "description" in response.data["items"][0]

        terms = quote_payload("QA-HARDEN-PAYMENT-OPTION")
        terms["payment_term_option"] = "Unsupported"
        response = self.api.post(
            "/api/v1/quotation/quotations",
            terms,
            format="json",
        )
        assert response.status_code == 400
        assert "payment_term_option" in response.data

    @override_settings(QUOTATION_MAX_ITEMS=1)
    def test_rejects_too_many_items_and_duplicate_line_numbers(self):
        too_many = quote_payload("QA-HARDEN-ITEM-LIMIT")
        too_many["items"].append(
            {
                **too_many["items"][0],
                "line_no": 2,
            }
        )

        response = self.api.post(
            "/api/v1/quotation/quotations",
            too_many,
            format="json",
        )

        assert response.status_code == 400
        assert "items" in response.data

        duplicate = quote_payload("QA-HARDEN-DUPLICATE-LINE")
        duplicate["items"].append(dict(duplicate["items"][0]))

        response = self.api.post(
            "/api/v1/quotation/quotations",
            duplicate,
            format="json",
        )

        assert response.status_code == 400
        assert "items" in response.data

    def test_rejects_derived_amount_that_exceeds_database_precision(self):
        payload = quote_payload("QA-HARDEN-AMOUNT-OVERFLOW")
        payload["items"][0]["qty"] = "9999999999999999.99"
        payload["items"][0]["list_price"] = "9999999999999999.99"

        response = self.api.post(
            "/api/v1/quotation/quotations",
            payload,
            format="json",
        )

        assert response.status_code == 400
        assert "items" in response.data

    def test_rejects_line_number_and_aggregate_amount_overflow(self):
        line_number = quote_payload("QA-HARDEN-LINE-NUMBER")
        line_number["items"][0]["line_no"] = 2147483648

        response = self.api.post(
            "/api/v1/quotation/quotations",
            line_number,
            format="json",
        )

        assert response.status_code == 400
        assert "line_no" in response.data["items"][0]

        total = quote_payload("QA-HARDEN-TOTAL-OVERFLOW")
        total["vat_rate"] = "0"
        total["items"] = [
            {
                **total["items"][0],
                "line_no": line_no,
                "qty": "1",
                "list_price": "6000000000000000.00",
                "discount_percent": "0",
            }
            for line_no in (1, 2)
        ]

        response = self.api.post(
            "/api/v1/quotation/quotations",
            total,
            format="json",
        )

        assert response.status_code == 400
        assert "items" in response.data

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

    def test_update_reuses_field_and_item_collection_validation(self):
        created = self.api.post(
            "/api/v1/quotation/quotations",
            quote_payload("QA-HARDEN-UPDATE-BOUNDARY"),
            format="json",
        )
        invalid_updates = (
            {"currency": "INVALID"},
            {"email": "not-an-email"},
            {"project_name": "P" * 256},
            {
                "items": [
                    quote_payload()["items"][0],
                    dict(quote_payload()["items"][0]),
                ]
            },
        )

        for payload in invalid_updates:
            with self.subTest(payload=payload):
                response = self.api.put(
                    f"/api/v1/quotation/quotations/{created.data['id']}",
                    payload,
                    format="json",
                )

                assert response.status_code == 400

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
            "quotation.services.quotation_service.create_version_snapshot",
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
        QuotationUploadPermission.objects.create(
            user=self.user,
            folder_token="fld_test_folder",
            folder_name="Test folder",
            granted_by=self.user,
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
            "QA-ROLLBACK-001.pdf",
            b"%PDF-excel bytes",
            content_type="application/pdf",
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

    @skipUnless(
        connection.vendor == "postgresql",
        "quotation locking requires PostgreSQL",
    )
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

    @skipUnless(
        connection.vendor == "postgresql",
        "formal revision locking requires PostgreSQL",
    )
    def test_concurrent_formal_revisions_receive_distinct_numbers(self):
        payload = quote_payload("BDR-CONCURRENT-REVISION")
        items = payload.pop("items")
        quote = build_quotation(data=payload, items_data=items)
        quote.status = "generated"
        quote.save(update_fields=["status", "updated_at"])
        create_version_snapshot(
            quote,
            operator_email="admin@example.com",
            notes="Initial formal version",
        )

        def update_project(project_name):
            close_old_connections()
            try:
                updated, version, _ = update_quotation(
                    quote.id,
                    {"project_name": project_name},
                    operator_email="admin@example.com",
                    notes="Concurrent formal revision",
                )
                return updated.quote_no, version.version_no
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    update_project,
                    ("Concurrent project A", "Concurrent project B"),
                )
            )

        assert sorted(results) == [
            ("BDR-CONCURRENT-REVISION_R1", 2),
            ("BDR-CONCURRENT-REVISION_R2", 3),
        ]
        quote.refresh_from_db()
        assert quote.version_current == 3
        assert quote.versions.count() == 3
