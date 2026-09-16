from datetime import date
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase

from invoice.models import (
    Invoice,
    InvoiceDocumentKind,
    InvoiceDocument,
    InvoiceItem,
    InvoiceParseResult,
    InvoiceParseStatus,
)


class InvoiceModelTests(TestCase):
    def test_non_sales_documents_can_keep_only_fields_found_in_pdf(self):
        first = Invoice.objects.create(
            invoice_no="",
            invoice_date=None,
            customer_name="",
            currency="",
            document_kind=InvoiceDocumentKind.DELIVERY_NOTE,
        )
        second = Invoice.objects.create(
            invoice_no="",
            invoice_date=None,
            customer_name="",
            currency="",
            document_kind=InvoiceDocumentKind.WITHHOLDING_TAX,
        )

        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(first.invoice_no, "")
        self.assertIsNone(second.invoice_date)

    def test_invoice_keeps_analytics_dimensions_and_line_items(self):
        invoice = Invoice.objects.create(
            invoice_no="INV-2026-0001",
            invoice_date=date(2026, 9, 4),
            customer_name="Acme Ltd",
            region="APAC",
            currency="USD",
            total_amount=Decimal("120.00"),
        )
        item = InvoiceItem.objects.create(
            invoice=invoice,
            line_no=1,
            product_code="P-1",
            product_name="Cloud migration",
            quantity=Decimal("2"),
            unit_price=Decimal("60"),
            net_amount=Decimal("120"),
            total_amount=Decimal("120"),
        )

        self.assertEqual(invoice.items.get(), item)
        self.assertEqual(invoice.region, "APAC")
        self.assertEqual(invoice.total_amount, Decimal("120.00"))

    def test_invoice_keeps_formal_document_snapshot_fields(self):
        invoice = Invoice.objects.create(
            invoice_no="INV-SNAPSHOT",
            invoice_date=date(2026, 9, 4),
            customer_name="Acme Ltd",
            customer_address="1 Example Street",
            contact_person="Alex",
            contact_email="alex@example.com",
            purchase_order_no="PO-100",
            payment_terms="CIA",
            additional_notes="VAT not applicable.",
            bank_account_name="OnePro Cloud Limited",
            bank_swift_code="DBSSHKHH",
            signatory_name="Lucy",
            signatory_title="Finance",
        )

        self.assertEqual(invoice.customer_address, "1 Example Street")
        self.assertEqual(invoice.contact_email, "alex@example.com")
        self.assertEqual(invoice.payment_terms, "CIA")
        self.assertEqual(invoice.bank_swift_code, "DBSSHKHH")
        self.assertEqual(invoice.signatory_name, "Lucy")

    def test_document_parse_result_is_versioned_by_content_and_parser(self):
        document = InvoiceDocument.objects.create(
            file_name="invoice.pdf",
            storage_key="documents/invoice-1.pdf",
        )
        result = InvoiceParseResult.objects.create(
            document=document,
            parser_name="invoice_pdf",
            parser_version="1.0.0",
            content_hash="a" * 64,
            status=InvoiceParseStatus.READY,
        )

        self.assertEqual(document.parse_results.get(), result)
        with self.assertRaises(IntegrityError):
            InvoiceParseResult.objects.create(
                document=document,
                parser_name="invoice_pdf",
                parser_version="1.0.0",
                content_hash="a" * 64,
            )
