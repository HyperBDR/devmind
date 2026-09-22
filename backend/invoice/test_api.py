from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from pypdf import PdfReader
from rest_framework.test import APIClient

from accounts.models import Role
from invoice.models import (
    Invoice,
    InvoiceAccessGrant,
    InvoiceAccessRole,
    InvoiceDocument,
    InvoiceDocumentPurpose,
    InvoiceItem,
    InvoiceRevision,
    InvoiceSourceType,
    InvoiceStatus,
)
from quotation.models import (
    AuditEvent,
    QuotationMembership,
    QuotationMembershipRole,
)


class InvoiceApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="invoice-user",
            email="invoice@example.com",
            password="password123",
        )
        self.grantor = User.objects.create_user(
            username="invoice-admin",
            is_staff=True,
        )
        InvoiceAccessGrant.objects.create(
            user=self.user,
            granted_by=self.grantor,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_invoice_api_requires_invoice_access_grant(self):
        outsider = User.objects.create_user(
            username="invoice-outsider",
            password="password123",
        )
        client = APIClient()
        client.force_authenticate(outsider)
        requests = [
            ("get", "/api/v1/invoice/invoices"),
            ("post", "/api/v1/invoice/invoices"),
            ("get", "/api/v1/invoice/invoices/missing"),
            ("patch", "/api/v1/invoice/invoices/missing"),
            ("get", "/api/v1/invoice/invoices/missing/pdf"),
            ("post", "/api/v1/invoice/feishu/sync"),
            ("get", "/api/v1/invoice/dashboard/analytics"),
        ]

        for method, path in requests:
            with self.subTest(method=method, path=path):
                response = getattr(client, method)(path, format="json")
                self.assertEqual(response.status_code, 403)

    def test_invoice_list_filters_sales_dimensions_and_dates(self):
        matching = Invoice.objects.create(
            invoice_no="INV-FILTER-1",
            invoice_date=date(2026, 9, 4),
            customer_name="Acme Ltd",
            contact_person="Alex Buyer",
            contact_email="alex@example.com",
            region="Malaysia",
            sales_owner="Taylor Sales",
            status=InvoiceStatus.ISSUED,
            source_type=InvoiceSourceType.FEISHU,
        )
        InvoiceItem.objects.create(
            invoice=matching,
            line_no=1,
            product_name="Cloud migration",
        )
        Invoice.objects.create(
            invoice_no="INV-FILTER-2",
            invoice_date=date(2026, 8, 1),
            customer_name="Beta Ltd",
            region="Singapore",
            sales_owner="Morgan Sales",
            contact_person="Alex Buyer",
            contact_email="other@example.com",
        )

        response = self.client.get(
            "/api/v1/invoice/invoices",
            {
                "search": "migration",
                "customer": "Acme Ltd",
                "region": "Malaysia",
                "sales_owner": "Taylor Sales",
                "status": InvoiceStatus.ISSUED,
                "source_type": InvoiceSourceType.FEISHU,
                "invoice_contact": "Alex Buyer",
                "invoice_contact_email": "alex@example.com",
                "invoice_from": "2026-09-04",
                "invoice_to": "2026-09-04",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["id"] for row in response.data["items"]],
            [matching.id],
        )
        self.assertEqual(
            response.data["facets"]["sales_owners"],
            ["Morgan Sales", "Taylor Sales"],
        )
        self.assertEqual(
            response.data["facets"]["invoice_contacts"],
            [
                {"name": "Alex Buyer", "email": ""},
            ],
        )

    def test_invoice_update_records_changed_fields(self):
        created = self.client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_date": date(2026, 9, 4).isoformat(),
                "numbering_mode": "auto",
                "product_line": "BDR",
                "customer_name": "Before",
                "currency": "USD",
            },
            format="json",
        )

        response = self.client.patch(
            f"/api/v1/invoice/invoices/{created.data['id']}",
            {"customer_name": "After"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        event = AuditEvent.objects.get(event_name="invoice.updated")
        self.assertEqual(event.target_id, created.data["id"])
        self.assertEqual(event.changes["fields"], ["customer_name"])

    def test_invoice_copy_records_source_and_each_successful_save(self):
        source = self.client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_date": date(2026, 9, 4).isoformat(),
                "numbering_mode": "auto",
                "product_line": "BDR",
                "customer_name": "Copy Source",
                "currency": "USD",
            },
            format="json",
        )
        payload = {
            "invoice_date": date(2026, 9, 5).isoformat(),
            "numbering_mode": "auto",
            "product_line": "BDR",
            "customer_name": "Copied Invoice",
            "currency": "USD",
            "copy_from_id": source.data["id"],
        }

        first = self.client.post(
            "/api/v1/invoice/invoices",
            payload,
            format="json",
        )
        second = self.client.post(
            "/api/v1/invoice/invoices",
            payload,
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        events = AuditEvent.objects.filter(event_name="invoice.copied")
        self.assertEqual(events.count(), 2)
        self.assertEqual(
            set(events.values_list("target_id", flat=True)),
            {first.data["id"], second.data["id"]},
        )
        self.assertEqual(
            events.values_list("request_id", flat=True).distinct().count(),
            2,
        )
        self.assertTrue(
            all(
                event.metadata["copy_from_id"] == source.data["id"]
                for event in events
            )
        )

    def test_invoice_list_paginates_and_exposes_feishu_source_url(self):
        invoices = [
            Invoice.objects.create(
                invoice_no=f"INV-PAGE-{index:02d}",
                invoice_date=date(2026, 9, index + 1),
                customer_name=f"Customer {index}",
                source_type=InvoiceSourceType.FEISHU,
            )
            for index in range(11)
        ]
        InvoiceDocument.objects.create(
            invoice=invoices[-1],
            file_name="invoice.pdf",
            storage_key="documents/invoice-page.pdf",
            feishu_file_token="invoice-page-token",
            feishu_url="https://example.feishu.cn/file/invoice-page-token",
        )

        first = self.client.get(
            "/api/v1/invoice/invoices",
            {"page": 1, "page_size": 10},
        )
        second = self.client.get(
            "/api/v1/invoice/invoices",
            {"page": 2, "page_size": 10},
        )
        invalid = self.client.get(
            "/api/v1/invoice/invoices",
            {"page_size": 25},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data["total"], 11)
        self.assertEqual(first.data["page"], 1)
        self.assertEqual(first.data["page_size"], 10)
        self.assertEqual(first.data["total_pages"], 2)
        self.assertEqual(len(first.data["items"]), 10)
        self.assertEqual(
            first.data["items"][0]["feishu_url"],
            "https://example.feishu.cn/file/invoice-page-token",
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(second.data["items"]), 1)
        self.assertEqual(invalid.status_code, 400)

    def test_invoice_list_contact_filter_matches_name_and_email_pair(self):
        matching = Invoice.objects.create(
            invoice_no="INV-CONTACT-1",
            invoice_date=date(2026, 9, 4),
            customer_name="Acme Ltd",
            contact_person="Alex Morgan",
            contact_email="alex@example.com",
        )
        Invoice.objects.create(
            invoice_no="INV-CONTACT-2",
            invoice_date=date(2026, 9, 3),
            customer_name="Acme Ltd",
            contact_person="Alex Morgan",
            contact_email="other@example.com",
        )

        response = self.client.get(
            "/api/v1/invoice/invoices",
            {
                "invoice_contact": "Alex Morgan",
                "invoice_contact_email": "alex@example.com",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["id"] for row in response.data["items"]],
            [matching.id],
        )

    def test_form_context_only_returns_parsed_invoice_history(self):
        imported = Invoice.objects.create(
            invoice_no="INV-HISTORY-1",
            invoice_date=date(2026, 9, 1),
            source_type=InvoiceSourceType.FEISHU,
            customer_name="History Customer",
            customer_tax_id="VAT-100",
            customer_address="Customer address",
            customer_contact_person="Customer Buyer",
            customer_contact_email="buyer@example.com",
            contact_person="Invoice Owner",
            contact_email="owner@example.com",
            currency="MYR",
            payment_terms="NET45",
        )
        InvoiceItem.objects.create(
            invoice=imported,
            line_no=1,
            product_name="HyperBDR",
            description="Annual recovery subscription",
            quantity=1,
            unit_price=Decimal("1200.00"),
        )
        Invoice.objects.create(
            invoice_no="INV-MANUAL-1",
            invoice_date=date(2026, 9, 2),
            source_type=InvoiceSourceType.MANUAL,
            customer_name="Manual Customer",
        )

        response = self.client.get(
            "/api/v1/invoice/invoices/form-context",
            {"page": 1, "page_size": 50},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(len(response.data["items"]), 1)
        item = response.data["items"][0]
        self.assertEqual(item["id"], imported.id)
        self.assertEqual(
            item["customer_contact_person"],
            "Customer Buyer",
        )
        self.assertEqual(item["contact_person"], "Invoice Owner")
        self.assertEqual(
            item["items"][0]["description"],
            "Annual recovery subscription",
        )

    def test_sales_management_role_does_not_bypass_invoice_grant(self):
        role_user = User.objects.create_user(username="legacy-sales-user")
        role = Role.objects.create(
            name="Legacy Sales Management",
            visible_features=["sales_management"],
        )
        role_user.platform_roles.add(role)
        client = APIClient()
        client.force_authenticate(role_user)

        response = client.get("/api/v1/invoice/invoices")

        self.assertEqual(response.status_code, 403)

    def test_quote_desk_admin_requires_an_invoice_grant(self):
        admin = User.objects.create_user(username="quote-admin")
        QuotationMembership.objects.create(
            user=admin,
            role=QuotationMembershipRole.ADMIN,
            assigned_by=self.grantor,
        )
        client = APIClient()
        client.force_authenticate(admin)

        response = client.get("/api/v1/invoice/invoices")

        self.assertEqual(response.status_code, 403)

    def test_expired_invoice_grant_is_rejected(self):
        InvoiceAccessGrant.objects.filter(user=self.user).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        response = self.client.get("/api/v1/invoice/invoices")

        self.assertEqual(response.status_code, 403)

    def test_invoice_user_can_edit_parse_and_issue(self):
        InvoiceAccessGrant.objects.filter(user=self.user).update(
            role=InvoiceAccessRole.USER,
        )
        listed = self.client.get("/api/v1/invoice/invoices")
        dashboard = self.client.get("/api/v1/invoice/dashboard/analytics")
        draft = self.client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_no": "INV-USER",
                "invoice_date": date(2026, 9, 4).isoformat(),
                "customer_name": "Invoice User",
            },
            format="json",
        )
        issued = self.client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_no": "INV-USER-ISSUED",
                "invoice_date": date(2026, 9, 4).isoformat(),
                "status": InvoiceStatus.ISSUED,
                "customer_name": "Invoice User",
                "items": [
                    {
                        "line_no": 1,
                        "product_name": "Service",
                        "quantity": "1",
                        "unit_price": "10.00",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(draft.status_code, 201)
        self.assertEqual(issued.status_code, 201)

    def test_quote_desk_admin_needs_invoice_grant_for_issue(self):
        admin = User.objects.create_user(username="invoice-role-admin")
        QuotationMembership.objects.create(
            user=admin,
            role=QuotationMembershipRole.ADMIN,
            assigned_by=self.grantor,
        )
        client = APIClient()
        client.force_authenticate(admin)

        response = client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_no": "INV-ADMIN-ISSUED",
                "invoice_date": date(2026, 9, 4).isoformat(),
                "status": InvoiceStatus.ISSUED,
                "customer_name": "Admin Customer",
                "items": [
                    {
                        "line_no": 1,
                        "product_name": "Service",
                        "quantity": "1",
                        "unit_price": "10.00",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_create_and_list_invoice_with_items(self):
        response = self.client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_no": "INV-100",
                "invoice_date": date(2026, 9, 4).isoformat(),
                "customer_name": "Acme Ltd",
                "region": "APAC",
                "currency": "USD",
                "total_amount": "120.00",
                "items": [
                    {
                        "line_no": 1,
                        "product_name": "Cloud migration",
                        "quantity": "2",
                        "unit_price": "60.00",
                        "net_amount": "120.00",
                        "total_amount": "120.00",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["created_by_email"],
            "invoice@example.com",
        )
        self.assertEqual(
            response.data["items"][0]["product_name"],
            "Cloud migration",
        )

        listed = self.client.get("/api/v1/invoice/invoices")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.data["items"]), 1)
        self.assertEqual(
            Invoice.objects.get(invoice_no="INV-100").total_amount,
            Decimal("120.00"),
        )

    def test_auto_invoice_numbers_follow_product_line_and_date(self):
        first = self.client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_date": date(2026, 9, 4).isoformat(),
                "numbering_mode": "auto",
                "product_line": "BDR",
                "customer_name": "Acme Ltd",
                "currency": "USD",
            },
            format="json",
        )
        second = self.client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_date": date(2026, 9, 5).isoformat(),
                "numbering_mode": "auto",
                "product_line": "BDR",
                "customer_name": "Beta Ltd",
                "currency": "USD",
            },
            format="json",
        )
        same_day_other_product = self.client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_date": date(2026, 9, 4).isoformat(),
                "numbering_mode": "auto",
                "product_line": "Motion",
                "customer_name": "Gamma Ltd",
                "currency": "USD",
            },
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data["invoice_no"], "BDR040926")
        self.assertEqual(first.data["numbering_mode"], "auto")
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.data["invoice_no"], "BDR050926")
        self.assertEqual(same_day_other_product.status_code, 201)
        self.assertEqual(
            same_day_other_product.data["invoice_no"],
            "Motion040926",
        )

        same_day_same_product = self.client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_date": date(2026, 9, 4).isoformat(),
                "numbering_mode": "auto",
                "product_line": "BDR",
                "customer_name": "Delta Ltd",
                "currency": "USD",
            },
            format="json",
        )
        self.assertEqual(same_day_same_product.status_code, 201)
        self.assertEqual(
            same_day_same_product.data["invoice_no"],
            "BDR040926.1",
        )

    def test_auto_draft_number_changes_with_date_and_product_line(self):
        created = self.client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_date": date(2026, 9, 4).isoformat(),
                "numbering_mode": "auto",
                "product_line": "BDR",
                "customer_name": "Acme Ltd",
                "currency": "USD",
            },
            format="json",
        )

        changed_date = self.client.patch(
            f"/api/v1/invoice/invoices/{created.data['id']}",
            {
                "invoice_date": date(2026, 9, 5).isoformat(),
                "invoice_no": created.data["invoice_no"],
            },
            format="json",
        )
        changed_product = self.client.patch(
            f"/api/v1/invoice/invoices/{created.data['id']}",
            {
                "product_line": "Motion",
                "invoice_no": changed_date.data["invoice_no"],
            },
            format="json",
        )

        self.assertEqual(changed_date.status_code, 200)
        self.assertEqual(changed_date.data["invoice_no"], "BDR050926")
        self.assertEqual(changed_product.status_code, 200)
        self.assertEqual(changed_product.data["invoice_no"], "Motion050926")

    def test_auto_draft_edit_accepts_blank_number_and_recalculates(self):
        created = self.client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_date": date(2026, 9, 4).isoformat(),
                "numbering_mode": "auto",
                "product_line": "BDR",
                "customer_name": "Acme Ltd",
                "currency": "USD",
            },
            format="json",
        )

        changed = self.client.patch(
            f"/api/v1/invoice/invoices/{created.data['id']}",
            {
                "invoice_no": "",
                "invoice_date": date(2026, 9, 5).isoformat(),
                "product_line": "Motion",
            },
            format="json",
        )

        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.data["invoice_no"], "Motion050926")

    def test_custom_draft_number_does_not_change_with_date(self):
        created = self.client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_no": "CUSTOM-2026-001",
                "invoice_date": date(2026, 9, 4).isoformat(),
                "numbering_mode": "custom",
                "product_line": "BDR",
                "customer_name": "Acme Ltd",
                "currency": "USD",
            },
            format="json",
        )

        changed = self.client.patch(
            f"/api/v1/invoice/invoices/{created.data['id']}",
            {"invoice_date": date(2026, 9, 5).isoformat()},
            format="json",
        )

        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.data["invoice_no"], "CUSTOM-2026-001")

    def test_duplicate_custom_invoice_number_is_rejected(self):
        payload = {
            "invoice_no": "CUSTOM-2026-001",
            "invoice_date": date(2026, 9, 4).isoformat(),
            "numbering_mode": "custom",
            "customer_name": "Acme Ltd",
            "currency": "USD",
        }

        first = self.client.post(
            "/api/v1/invoice/invoices",
            payload,
            format="json",
        )
        duplicate = self.client.post(
            "/api/v1/invoice/invoices",
            payload,
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data["invoice_no"], "CUSTOM-2026-001")
        self.assertEqual(first.data["numbering_mode"], "custom")
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(Invoice.objects.count(), 1)

    def test_create_invoice_keeps_commercial_invoice_snapshot(self):
        response = self.client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_no": "BDR231025",
                "invoice_date": date(2026, 9, 4).isoformat(),
                "status": InvoiceStatus.ISSUED,
                "source_type": InvoiceSourceType.FEISHU,
                "currency": "usd",
                "seller_name": "OnePro Cloud Limited",
                "seller_address": "Unit 701A, 7/F, Railway Plaza",
                "seller_website": "www.oneprocloud.com",
                "seller_email": "enquiry@oneprocloud.com",
                "customer_name": "JICHO CONSULTING",
                "customer_tax_id": "4090263635",
                "customer_address": "584 Makou Street, Pretoria",
                "contact_person": "Lucy",
                "contact_email": "accounts@example.com",
                "purchase_order_no": "PO0000080",
                "payment_terms": "CIA",
                "additional_notes": "VAT not applicable.",
                "remarks": "Use the invoice number as reference.",
                "bank_account_name": "OnePro Cloud Limited",
                "bank_name": "DBS Bank Limited, Hong Kong Branch",
                "bank_address": "18th Floor, The Center, Hong Kong",
                "bank_account_number": "20000723088",
                "bank_code": "185",
                "bank_branch_code": "927",
                "bank_swift_code": "DBSSHKHH",
                "remittance_instruction": "Email remittance advice.",
                "signatory_name": "Lucy",
                "signatory_title": "Finance",
                "issuer_signature": (
                    "data:image/png;base64,"
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
                    "AAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
                ),
                "tax_rate": "0",
                "subtotal_amount": "1.00",
                "total_amount": "1.00",
                "items": [
                    {
                        "line_no": 1,
                        "product_name": "DR Software",
                        "description": "HyperBDR Cloud Disaster Recovery",
                        "quantity": "5",
                        "unit_price": "2100.00",
                        "net_amount": "1.00",
                        "total_amount": "1.00",
                    },
                    {
                        "line_no": 2,
                        "product_name": "Professional Service",
                        "description": "Remote installation and deployment",
                        "quantity": "1",
                        "unit_price": "2000.00",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["source_type"], "manual")
        self.assertEqual(response.data["currency"], "USD")
        self.assertEqual(response.data["customer_address"], (
            "584 Makou Street, Pretoria"
        ))
        self.assertEqual(response.data["purchase_order_no"], "PO0000080")
        self.assertEqual(response.data["bank_swift_code"], "DBSSHKHH")
        self.assertEqual(response.data["signatory_title"], "Finance")
        self.assertEqual(response.data["subtotal_amount"], "12500.00")
        self.assertEqual(response.data["tax_amount"], "0.00")
        self.assertEqual(response.data["total_amount"], "12500.00")
        self.assertEqual(response.data["items"][0]["net_amount"], "10500.00")

    def test_issue_generates_downloadable_english_pdf_and_audit_events(self):
        items = [
            {
                "line_no": index,
                "product_name": f"Internal Product {index}",
                "description": f"Public service line {index}",
                "quantity": "1",
                "unit_price": "100.00",
            }
            for index in range(1, 9)
        ]
        with TemporaryDirectory() as storage_root:
            with override_settings(INVOICE_STORAGE=storage_root):
                response = self.client.post(
                    "/api/v1/invoice/invoices",
                    {
                        "invoice_no": "INV/PDF 100",
                        "invoice_date": date(2026, 9, 4).isoformat(),
                        "status": InvoiceStatus.ISSUED,
                        "currency": "USD",
                        "seller_name": "OnePro Cloud Limited",
                        "customer_name": "PDF Customer",
                        "region": "INTERNAL-REGION",
                        "sales_owner": "INTERNAL-OWNER",
                        "items": items,
                    },
                    format="json",
                )

                self.assertEqual(response.status_code, 201)
                self.assertTrue(response.data["pdf_available"])
                invoice = Invoice.objects.get(pk=response.data["id"])
                document = invoice.documents.get(
                    purpose=InvoiceDocumentPurpose.ISSUED,
                )
                self.assertEqual(document.file_name, "INV-PDF-100.pdf")
                self.assertEqual(document.content_type, "application/pdf")

                download = self.client.get(
                    f"/api/v1/invoice/invoices/{invoice.id}/pdf"
                )
                content = b"".join(download.streaming_content)

        self.assertEqual(download.status_code, 200)
        self.assertIn("attachment", download["Content-Disposition"])
        self.assertTrue(content.startswith(b"%PDF-"))
        reader = PdfReader(BytesIO(content))
        self.assertEqual(len(reader.pages), 2)
        page_text = [page.extract_text() for page in reader.pages]
        self.assertTrue(
            all("Commercial Invoice" in text for text in page_text)
        )
        self.assertIn("Public service line 1", page_text[0])
        self.assertIn("Public service line 8", page_text[1])
        self.assertIn("Page 1 / 2", page_text[0])
        self.assertIn("Page 2 / 2", page_text[1])
        full_text = "\n".join(page_text)
        self.assertNotIn("INTERNAL-REGION", full_text)
        self.assertNotIn("INTERNAL-OWNER", full_text)
        self.assertNotIn("Internal Product", full_text)
        self.assertTrue(
            AuditEvent.objects.filter(
                event_name="invoice.generated",
                target_id=invoice.id,
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                event_name="invoice.downloaded",
                target_id=invoice.id,
            ).exists()
        )
        visible_audit = self.client.get(
            "/api/v1/quotation/audit-events?page_size=100"
        )
        self.assertEqual(visible_audit.status_code, 200)
        self.assertIn(
            "invoice.generated",
            [item["event_name"] for item in visible_audit.data["items"]],
        )

        quote_user = User.objects.create_user(
            username="quote-only-user",
            password="password123",
        )
        quote_role = Role.objects.create(
            name="Quote Only",
            visible_features=["quotation_management"],
        )
        quote_user.platform_roles.add(quote_role)
        quote_client = APIClient()
        quote_client.force_authenticate(quote_user)
        hidden_audit = quote_client.get(
            "/api/v1/quotation/audit-events?page_size=100"
        )
        self.assertEqual(hidden_audit.status_code, 200)
        self.assertNotIn(
            "invoice.generated",
            [item["event_name"] for item in hidden_audit.data["items"]],
        )

    def test_invalid_signature_does_not_create_issued_invoice(self):
        response = self.client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_no": "INV-BAD-SIGNATURE",
                "invoice_date": date(2026, 9, 4).isoformat(),
                "status": InvoiceStatus.ISSUED,
                "customer_name": "Acme Ltd",
                "issuer_signature": "data:image/png;base64,bm90LWEtcG5n",
                "items": [
                    {
                        "line_no": 1,
                        "product_name": "Service",
                        "description": "Service",
                        "quantity": "1",
                        "unit_price": "10.00",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            Invoice.objects.filter(invoice_no="INV-BAD-SIGNATURE").exists()
        )

    def test_issued_invoice_requires_at_least_one_item(self):
        response = self.client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_no": "INV-NO-ITEMS",
                "invoice_date": date(2026, 9, 4).isoformat(),
                "status": InvoiceStatus.ISSUED,
                "customer_name": "Acme Ltd",
                "items": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("items", response.data)

    def test_create_invoice_rejects_invalid_status_and_item_amounts(self):
        paid = self.client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_no": "INV-PAID",
                "invoice_date": date(2026, 9, 4).isoformat(),
                "status": InvoiceStatus.PAID,
                "customer_name": "Acme Ltd",
            },
            format="json",
        )
        negative_quantity = self.client.post(
            "/api/v1/invoice/invoices",
            {
                "invoice_no": "INV-BAD-ITEM",
                "invoice_date": date(2026, 9, 4).isoformat(),
                "customer_name": "Acme Ltd",
                "items": [
                    {
                        "line_no": 1,
                        "product_name": "Cloud migration",
                        "quantity": "-1",
                        "unit_price": "60.00",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(paid.status_code, 400)
        self.assertIn("status", paid.data)
        self.assertEqual(negative_quantity.status_code, 400)
        self.assertIn("items", negative_quantity.data)

    def test_patch_replaces_items_and_recalculates_totals(self):
        invoice = Invoice.objects.create(
            invoice_no="INV-PATCH",
            invoice_date=date(2026, 9, 4),
            customer_name="Acme Ltd",
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            line_no=1,
            product_name="Old service",
            quantity=Decimal("1"),
            unit_price=Decimal("10"),
            net_amount=Decimal("10"),
            total_amount=Decimal("10"),
        )

        response = self.client.patch(
            f"/api/v1/invoice/invoices/{invoice.id}",
            {
                "tax_rate": "10",
                "items": [
                    {
                        "line_no": 1,
                        "product_name": "New service",
                        "quantity": "2",
                        "unit_price": "50.00",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["items"][0]["product_name"], (
            "New service"
        ))
        self.assertEqual(response.data["subtotal_amount"], "100.00")
        self.assertEqual(response.data["tax_amount"], "10.00")
        self.assertEqual(response.data["total_amount"], "110.00")
        self.assertEqual(invoice.items.count(), 1)

    def test_patch_draft_to_issued_generates_downloadable_pdf(self):
        invoice = Invoice.objects.create(
            invoice_no="INV-DRAFT-ISSUE",
            invoice_date=date(2026, 9, 4),
            customer_name="Draft Customer",
            seller_name="OnePro Cloud Limited",
            status=InvoiceStatus.DRAFT,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            line_no=1,
            product_name="Migration service",
            description="Migration service",
            quantity=Decimal("1"),
            unit_price=Decimal("100"),
            net_amount=Decimal("100"),
            total_amount=Decimal("100"),
        )

        with TemporaryDirectory() as storage_root:
            with override_settings(INVOICE_STORAGE=storage_root):
                response = self.client.patch(
                    f"/api/v1/invoice/invoices/{invoice.id}",
                    {"status": InvoiceStatus.ISSUED},
                    format="json",
                )
                download = self.client.get(
                    f"/api/v1/invoice/invoices/{invoice.id}/pdf"
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], InvoiceStatus.ISSUED)
        self.assertTrue(response.data["pdf_available"])
        self.assertEqual(download.status_code, 200)
        content = b"".join(download.streaming_content)
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertTrue(
            AuditEvent.objects.filter(
                event_name="invoice.generated",
                target_id=invoice.id,
            ).exists()
        )

    def test_issued_invoice_edit_preserves_revision_history(self):
        invoice = Invoice.objects.create(
            invoice_no="INV-LOCKED",
            invoice_date=date(2026, 9, 4),
            customer_name="Original Customer",
            status=InvoiceStatus.ISSUED,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            line_no=1,
            product_name="Issued service",
            quantity=Decimal("1"),
            unit_price=Decimal("10"),
            net_amount=Decimal("10"),
            total_amount=Decimal("10"),
        )

        with TemporaryDirectory() as storage_root:
            with override_settings(INVOICE_STORAGE=storage_root):
                response = self.client.patch(
                    f"/api/v1/invoice/invoices/{invoice.id}",
                    {"customer_name": "Changed Customer"},
                    format="json",
                )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["invoice_no"], "INV-LOCKED_R1")
        invoice.refresh_from_db()
        self.assertEqual(invoice.customer_name, "Changed Customer")
        revision = InvoiceRevision.objects.get(invoice=invoice)
        self.assertEqual(revision.invoice_no, "INV-LOCKED")
        self.assertEqual(
            revision.snapshot_json["customer_name"], "Original Customer"
        )

    def test_issued_invoice_edit_creates_revision_number(self):
        invoice = Invoice.objects.create(
            invoice_no="INV-REVISION",
            invoice_date=date(2026, 9, 4),
            customer_name="Original Customer",
            seller_name="OnePro Cloud Limited",
            status=InvoiceStatus.ISSUED,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            line_no=1,
            product_name="Issued service",
            quantity=Decimal("1"),
            unit_price=Decimal("10"),
            net_amount=Decimal("10"),
            total_amount=Decimal("10"),
        )

        with TemporaryDirectory() as storage_root:
            with override_settings(INVOICE_STORAGE=storage_root):
                response = self.client.patch(
                    f"/api/v1/invoice/invoices/{invoice.id}",
                    {
                        "customer_name": "Updated Customer",
                        "items": [
                            {
                                "line_no": 1,
                                "product_name": "Updated service",
                                "quantity": "2",
                                "unit_price": "15.00",
                            }
                        ],
                    },
                    format="json",
                )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["invoice_no"], "INV-REVISION_R1")
        self.assertEqual(response.data["revision_no"], 1)
        self.assertEqual(response.data["customer_name"], "Updated Customer")
        self.assertEqual(
            response.data["items"][0]["product_name"],
            "Updated service",
        )

        second = self.client.patch(
            f"/api/v1/invoice/invoices/{invoice.id}",
            {"customer_name": "Final Customer"},
            format="json",
        )

        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data["invoice_no"], "INV-REVISION_R2")
        self.assertEqual(second.data["revision_no"], 2)

    def test_sales_dashboard_endpoint_returns_aggregates(self):
        Invoice.objects.create(
            invoice_no="INV-DASH",
            invoice_date=date(2026, 9, 4),
            customer_name="Dashboard Customer",
            region="APAC",
            currency="USD",
            status="issued",
            total_amount=Decimal("42.00"),
        )

        response = self.client.get(
            "/api/v1/invoice/dashboard/analytics?currency=USD"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["by_region"][0]["name"], "APAC")
