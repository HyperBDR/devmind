from datetime import date
from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from invoice.models import (
    Invoice,
    InvoiceDocumentKind,
    InvoiceDocument,
    InvoiceDocumentPurpose,
    InvoiceParseResult,
    InvoiceParseStatus,
    InvoiceSourceType,
    InvoiceStatus,
)
from invoice.parsing.schemas import (
    ParsedInvoice,
    ParsedInvoiceDocumentData,
)
from invoice.services.documents import invoice_storage
from invoice.services.imports import (
    _validate_required_fields,
    parse_and_create_invoice,
)


class InvoiceImportValidationTests(SimpleTestCase):
    def _valid_invoice(self) -> ParsedInvoice:
        return ParsedInvoice(
            invoice_no="INV-100",
            invoice_date=date(2026, 9, 9),
            customer_name="Acme Ltd",
            currency="MYR",
            total_amount=Decimal("100.00"),
        )

    def test_sales_critical_fields_must_come_from_the_pdf(self):
        invalid_values = {
            "invoice_no": "",
            "invoice_date": None,
            "customer_name": "",
            "currency": "",
            "total_amount": Decimal("0"),
        }

        for field, value in invalid_values.items():
            with self.subTest(field=field):
                invoice = self._valid_invoice().model_copy(
                    update={field: value},
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "Required invoice fields were not found",
                ):
                    _validate_required_fields(invoice)

    def test_complete_invoice_is_accepted(self):
        _validate_required_fields(self._valid_invoice())


class InvoiceImportCleanupTests(TestCase):
    def _linked_import(self) -> tuple[Invoice, InvoiceDocument]:
        invoice = Invoice.objects.create(
            invoice_no="OLD-PARSER-001",
            invoice_date=date(2026, 9, 9),
            status=InvoiceStatus.ISSUED,
            source_type=InvoiceSourceType.FEISHU,
            currency="USD",
            customer_name="Old parser value",
            total_amount=Decimal("100.00"),
        )
        document = InvoiceDocument.objects.create(
            invoice=invoice,
            file_name="source.pdf",
            storage_key="documents/source.pdf",
            content_type="application/pdf",
            size_bytes=4,
            content_hash="a" * 64,
        )
        invoice_storage().write_atomic(b"%PDF", document.storage_key)
        return invoice, document

    def test_delivery_note_keeps_an_independent_ledger_record(self):
        with TemporaryDirectory() as storage_root:
            with override_settings(INVOICE_STORAGE=storage_root):
                invoice, document = self._linked_import()
                parsed = ParsedInvoiceDocumentData(
                    invoice=ParsedInvoice(
                        invoice_no="DN270825_TIME",
                        invoice_date=date(2025, 8, 27),
                        customer_name="TT DOTCOM SDN BHD (TIME)",
                    ),
                    document_kind="delivery_note",
                    validation_warnings=[
                        {
                            "field": "document",
                            "code": "delivery_note_detected",
                            "detail": "Not an invoice.",
                        }
                    ],
                )
                with patch(
                    "invoice.services.imports.parse_invoice_pdf",
                    return_value=parsed,
                ):
                    result, reused = parse_and_create_invoice(document)

                self.assertEqual(result, invoice)
                self.assertTrue(reused)
                invoice.refresh_from_db()
                self.assertEqual(
                    invoice.document_kind,
                    InvoiceDocumentKind.DELIVERY_NOTE,
                )
                self.assertEqual(invoice.invoice_no, "DN270825_TIME")
                self.assertEqual(invoice.invoice_date, date(2025, 8, 27))
                document.refresh_from_db()
                self.assertEqual(document.invoice_id, invoice.id)
                self.assertTrue(
                    invoice_storage().resolve(document.storage_key).is_file()
                )
                parse_result = InvoiceParseResult.objects.get(
                    document=document,
                )
                self.assertEqual(
                    parse_result.status,
                    InvoiceParseStatus.CONFIRMED,
                )

    def test_zero_amount_invoice_is_kept_as_a_draft_ledger_record(self):
        with TemporaryDirectory() as storage_root:
            with override_settings(INVOICE_STORAGE=storage_root):
                invoice, document = self._linked_import()
                parsed = ParsedInvoiceDocumentData(
                    invoice=ParsedInvoice(
                        invoice_no="1E4ED772-0001",
                        invoice_date=date(2024, 11, 4),
                        customer_name="Carrol Yu",
                        currency="USD",
                        total_amount=Decimal("0.00"),
                    ),
                )
                with patch(
                    "invoice.services.imports.parse_invoice_pdf",
                    return_value=parsed,
                ):
                    result, reused = parse_and_create_invoice(document)

                self.assertEqual(result, invoice)
                self.assertTrue(reused)
                invoice.refresh_from_db()
                self.assertEqual(invoice.invoice_date, date(2024, 11, 4))
                self.assertEqual(invoice.total_amount, Decimal("0.00"))
                self.assertEqual(invoice.status, InvoiceStatus.DRAFT)
                document.refresh_from_db()
                self.assertEqual(document.invoice_id, invoice.id)
                self.assertTrue(
                    invoice_storage().resolve(document.storage_key).is_file()
                )

    def test_withholding_tax_keeps_its_own_ledger_record(self):
        with TemporaryDirectory() as storage_root:
            with override_settings(INVOICE_STORAGE=storage_root):
                stale_invoice, document = self._linked_import()
                document.purpose = InvoiceDocumentPurpose.SUPPORTING
                document.save(update_fields=["purpose", "updated_at"])
                target = Invoice.objects.create(
                    invoice_no="BDR030325",
                    invoice_date=date(2025, 3, 3),
                    status=InvoiceStatus.ISSUED,
                    source_type=InvoiceSourceType.FEISHU,
                    currency="USD",
                    customer_name="Sales customer",
                    total_amount=Decimal("1000.00"),
                )
                parsed = ParsedInvoiceDocumentData(
                    invoice=ParsedInvoice(
                        invoice_no="INV.BDR030325",
                        invoice_date=date(2025, 5, 13),
                        customer_name="OnePro Cloud Limited",
                        currency="THB",
                        total_amount=Decimal("2594.59"),
                    ),
                    document_kind="withholding_tax",
                    validation_warnings=[
                        {
                            "field": "document",
                            "code": "withholding_tax_detected",
                            "detail": "Supporting tax document.",
                        }
                    ],
                )
                with patch(
                    "invoice.services.imports.parse_invoice_pdf",
                    return_value=parsed,
                ):
                    result, reused = parse_and_create_invoice(document)

                self.assertNotEqual(result, stale_invoice)
                self.assertNotEqual(result, target)
                self.assertFalse(reused)
                result.refresh_from_db()
                self.assertEqual(
                    result.document_kind,
                    InvoiceDocumentKind.WITHHOLDING_TAX,
                )
                self.assertEqual(result.invoice_no, "INV.BDR030325")
                self.assertEqual(result.currency, "THB")
                self.assertEqual(
                    result.total_amount,
                    Decimal("2594.59"),
                )
                self.assertTrue(
                    Invoice.objects.filter(pk=stale_invoice.pk).exists()
                )
                self.assertTrue(Invoice.objects.filter(pk=target.pk).exists())
                document.refresh_from_db()
                self.assertEqual(document.invoice_id, result.pk)

    def test_valid_reparse_replaces_stale_invoice_date(self):
        with TemporaryDirectory() as storage_root:
            with override_settings(INVOICE_STORAGE=storage_root):
                invoice, document = self._linked_import()
                parsed = ParsedInvoiceDocumentData(
                    invoice=ParsedInvoice(
                        invoice_no=invoice.invoice_no,
                        invoice_date=date(2025, 3, 3),
                        customer_name="Correct customer",
                        currency="USD",
                        total_amount=Decimal("125.00"),
                    ),
                )
                with patch(
                    "invoice.services.imports.parse_invoice_pdf",
                    return_value=parsed,
                ):
                    result, reused = parse_and_create_invoice(document)

                self.assertEqual(result, invoice)
                self.assertTrue(reused)
                invoice.refresh_from_db()
                self.assertEqual(invoice.invoice_date, date(2025, 3, 3))
                self.assertEqual(invoice.customer_name, "Correct customer")
                parse_result = InvoiceParseResult.objects.get(
                    document=document,
                )
                self.assertEqual(
                    parse_result.status,
                    InvoiceParseStatus.CONFIRMED,
                )

    def test_reparse_preserves_existing_contacts_when_source_is_silent(self):
        with TemporaryDirectory() as storage_root:
            with override_settings(INVOICE_STORAGE=storage_root):
                invoice, document = self._linked_import()
                invoice.contact_person = "LUCY"
                invoice.contact_email = "ecosys@oneprocloud.com"
                invoice.customer_contact_person = "Vandana"
                invoice.customer_contact_email = "info@aitcs.co.za"
                invoice.save(
                    update_fields=[
                        "contact_person",
                        "contact_email",
                        "customer_contact_person",
                        "customer_contact_email",
                    ]
                )
                parsed = ParsedInvoiceDocumentData(
                    invoice=ParsedInvoice(
                        invoice_no=invoice.invoice_no,
                        invoice_date=date(2025, 3, 3),
                        customer_name="Correct customer",
                        currency="USD",
                        total_amount=Decimal("125.00"),
                    ),
                )
                with patch(
                    "invoice.services.imports.parse_invoice_pdf",
                    return_value=parsed,
                ):
                    parse_and_create_invoice(document)

                invoice.refresh_from_db()
                self.assertEqual(invoice.contact_person, "LUCY")
                self.assertEqual(
                    invoice.contact_email,
                    "ecosys@oneprocloud.com",
                )
                self.assertEqual(
                    invoice.customer_contact_person,
                    "Vandana",
                )

    def test_reparse_moves_old_invoice_contact_to_customer_when_role_is_clear(
        self,
    ):
        with TemporaryDirectory() as storage_root:
            with override_settings(INVOICE_STORAGE=storage_root):
                invoice, document = self._linked_import()
                invoice.contact_person = "VélifoF"
                invoice.contact_email = "buyer@example.com"
                invoice.save(
                    update_fields=["contact_person", "contact_email"]
                )
                parsed = ParsedInvoiceDocumentData(
                    invoice=ParsedInvoice(
                        invoice_no=invoice.invoice_no,
                        invoice_date=date(2025, 3, 3),
                        customer_name="Correct customer",
                        customer_contact_person="VélifoF",
                        customer_contact_email="buyer@example.com",
                        currency="USD",
                        total_amount=Decimal("125.00"),
                    ),
                )
                with patch(
                    "invoice.services.imports.parse_invoice_pdf",
                    return_value=parsed,
                ):
                    parse_and_create_invoice(document)

                invoice.refresh_from_db()
                self.assertEqual(invoice.contact_person, "")
                self.assertEqual(invoice.contact_email, "")
                self.assertEqual(
                    invoice.customer_contact_person,
                    "VélifoF",
                )
