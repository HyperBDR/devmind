import importlib
from contextlib import redirect_stdout
from datetime import date
from decimal import Decimal
from io import StringIO
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pymupdf
from django.apps import apps as django_apps
from django.test import SimpleTestCase, TestCase, override_settings

from invoice.models import (
    Invoice,
    InvoiceDocument,
    InvoiceDocumentPurpose,
    InvoiceDocumentStatus,
    InvoiceItem,
    InvoiceStatus,
)
from invoice.services.documents import (
    invoice_storage,
    latest_downloadable_document,
)
from invoice.services.pdf_renderer import render_invoice_pdf

migration = importlib.import_module(
    "invoice.migrations.0016_regenerate_bdr111126_pdf"
)

QUEENS = "99 Queen\u2019s Road Central, Central, Hong Kong"


class _Items(list):
    def all(self):
        return self


def _item(index: int, description: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        description=description or f"Service line {index}",
        product_name=f"Product {index}",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        net_amount=Decimal("100.00"),
    )


def _invoice(**overrides) -> SimpleNamespace:
    values = {
        "document_kind": "invoice",
        "invoice_no": "INV-2026-1111",
        "invoice_date": date(2026, 11, 11),
        "currency": "USD",
        "seller_name": "OnePro Cloud Limited",
        "seller_address": "Sheung Wan, Hong Kong",
        "seller_website": "www.oneprocloud.com",
        "seller_email": "enquiry@oneprocloud.com",
        "customer_name": "VONOSIS COMPANY LIMITED",
        "customer_tax_id": "",
        "customer_address": "9/197 Soi. Ratchapracha 4, Bangkok 10900",
        "customer_contact_person": "",
        "customer_contact_email": "",
        "customer_contact_phone": "",
        "contact_person": "Somchai Wong",
        "contact_email": "somchai@vonosis.co.th",
        "purchase_order_no": "",
        "payment_terms": "Net 30",
        "additional_notes": "",
        "remarks": "",
        "bank_account_name": "OnePro Cloud Limited",
        "bank_name": "DBS Bank Limited, Hong Kong Branch",
        "bank_address": f"18th Floor, The Center, {QUEENS}",
        "bank_account_number": "20000723088",
        "bank_code": "185",
        "bank_branch_code": "927",
        "bank_swift_code": "DBSSHKHH",
        "remittance_instruction": "Please use the Invoice number.",
        "signatory_name": "Natalie Chan",
        "signatory_title": "Sales Director",
        "issuer_signature": "",
        "total_amount": Decimal("100.00"),
        "items": _Items([_item(1)]),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _pages(invoice) -> list[str]:
    document = pymupdf.open(stream=render_invoice_pdf(invoice))
    try:
        return [page.get_text() for page in document]
    finally:
        document.close()


class InvoicePdfRendererTests(SimpleTestCase):
    def test_bill_to_matches_preview_and_keeps_typography(self):
        text = "\n".join(_pages(_invoice()))

        self.assertIn("Name:", text)
        self.assertIn("Somchai Wong", text)
        self.assertIn("Email:", text)
        self.assertIn("somchai@vonosis.co.th", text)
        self.assertNotIn("VAT NO", text)
        self.assertIn("Queen\u2019s Road Central", text)
        self.assertIn("\u2014", text)
        self.assertNotIn("?", text)

    def test_customer_contact_fields_take_priority(self):
        text = "\n".join(
            _pages(
                _invoice(
                    customer_contact_person="Anong Chai",
                    customer_contact_email="anong@vonosis.co.th",
                    customer_contact_phone="+66 2 123 4567",
                    customer_tax_id="0105559012345",
                )
            )
        )

        self.assertIn("Anong Chai", text)
        self.assertIn("anong@vonosis.co.th", text)
        self.assertIn("Contact:", text)
        self.assertIn("+66 2 123 4567", text)
        self.assertIn("VAT NO:", text)
        self.assertIn("0105559012345", text)

    def test_euro_amounts_render(self):
        text = "\n".join(_pages(_invoice(currency="EUR")))

        self.assertIn("\u20ac 100.00", text)
        self.assertNotIn("?", text)

    def test_proforma_invoice_uses_its_own_title(self):
        text = _pages(_invoice(document_kind="proforma_invoice"))[0]

        self.assertIn("Proforma Invoice", text)
        self.assertIn("Proforma Invoice Number:", text)
        self.assertNotIn("Commercial Invoice", text)

    def test_remarks_are_printed_above_bank_details(self):
        text = _pages(_invoice(remarks="Payment due within 30 days."))[0]

        self.assertLess(
            text.index("Payment due within 30 days."),
            text.index("Account Name:"),
        )

    def test_full_bill_to_with_seven_items_still_fits(self):
        invoice = _invoice(
            customer_contact_person="Anong Chai",
            customer_contact_email="anong@vonosis.co.th",
            customer_contact_phone="+66 2 123 4567",
            customer_tax_id="0105559012345",
            customer_address=(
                "9/197 Soi. Ratchapracha 4 Chatuchak, Chatuchak, "
                "Bangkok 10900, Thailand, Building B, Floor 12"
            ),
            remarks="Payment due within 30 days.",
            items=_Items([_item(index) for index in range(1, 8)]),
        )

        pages = _pages(invoice)

        self.assertEqual(len(pages), 2)
        text = "\n".join(pages)
        for index in range(1, 8):
            self.assertEqual(text.count(f"Service line {index}\n"), 1)
        self.assertIn("Invoice items continued on next page", pages[0])
        self.assertIn("Total Amount:", pages[1])
        self.assertIn("Page 2 / 2", pages[1])

    def test_default_layout_keeps_seven_items_on_one_page(self):
        invoice = _invoice(
            contact_person="",
            contact_email="",
            items=_Items([_item(index) for index in range(1, 8)]),
        )

        pages = _pages(invoice)

        self.assertEqual(len(pages), 1)
        self.assertIn("Total Amount:", pages[0])

    def test_long_descriptions_do_not_run_off_continuation_pages(self):
        description = "\n".join(f"Detail line {line}" for line in range(9))
        invoice = _invoice(
            items=_Items(
                [_item(index, description) for index in range(1, 8)]
            ),
        )

        pages = _pages(invoice)

        self.assertGreater(len(pages), 1)
        document = pymupdf.open(stream=render_invoice_pdf(invoice))
        try:
            for page in document:
                for block in page.get_text("blocks"):
                    self.assertLessEqual(block[3], 830)
        finally:
            document.close()


class RegenerateBdr111126PdfMigrationTests(TestCase):
    def setUp(self):
        self.storage_root = TemporaryDirectory()
        self.addCleanup(self.storage_root.cleanup)
        settings_override = override_settings(
            INVOICE_STORAGE=self.storage_root.name
        )
        settings_override.enable()
        self.addCleanup(settings_override.disable)

    def _issued(self, number: str) -> tuple[Invoice, InvoiceDocument]:
        invoice = Invoice.objects.create(
            invoice_no=number,
            invoice_date=date(2026, 11, 11),
            status=InvoiceStatus.ISSUED,
            customer_name="VONOSIS COMPANY LIMITED",
            contact_person="Somchai Wong",
            contact_email="somchai@vonosis.co.th",
            bank_address=f"18th Floor, The Center, {QUEENS}",
            total_amount=Decimal("1200.00"),
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            line_no=1,
            description="HyperBDR Yearly License",
            quantity=Decimal("1"),
            unit_price=Decimal("1200.00"),
            net_amount=Decimal("1200.00"),
        )
        storage_key = f"issued/{invoice.id}/old.pdf"
        invoice_storage().write_atomic(b"%PDF-old", storage_key)
        document = InvoiceDocument.objects.create(
            invoice=invoice,
            file_name=f"{number}.pdf",
            storage_key=storage_key,
            content_type="application/pdf",
            purpose=InvoiceDocumentPurpose.ISSUED,
        )
        return invoice, document

    def _run(self) -> str:
        with redirect_stdout(StringIO()) as log:
            migration.regenerate_pdf(django_apps, None)
        return log.getvalue()

    def test_replaces_only_the_listed_invoice_pdf(self):
        invoice, old_document = self._issued("BDR111126")
        other, other_document = self._issued("BDR999999")
        before = Invoice.objects.get(pk=invoice.pk)

        log = self._run()

        self.assertIn("invoice pdf BDR111126: regenerated", log)
        old_document.refresh_from_db()
        self.assertEqual(
            old_document.status, InvoiceDocumentStatus.ARCHIVED
        )
        self.assertTrue(
            invoice_storage().resolve(old_document.storage_key).is_file()
        )
        current = latest_downloadable_document(invoice)
        self.assertNotEqual(current.pk, old_document.pk)
        self.assertEqual(current.file_name, "BDR111126.pdf")
        content = invoice_storage().resolve(current.storage_key).read_bytes()
        text = "\n".join(
            page.get_text() for page in pymupdf.open(stream=content)
        )
        self.assertIn("Somchai Wong", text)
        self.assertIn("somchai@vonosis.co.th", text)
        self.assertIn("Queen\u2019s Road Central", text)
        self.assertNotIn("VAT NO", text)
        self.assertNotIn("?", text)
        after = Invoice.objects.get(pk=invoice.pk)
        self.assertEqual(after.invoice_no, before.invoice_no)
        self.assertEqual(after.revision_no, before.revision_no)
        self.assertEqual(after.updated_at, before.updated_at)
        self.assertEqual(latest_downloadable_document(other), other_document)

    def test_skips_when_there_is_no_generated_pdf(self):
        Invoice.objects.create(
            invoice_no="BDR111126",
            invoice_date=date(2026, 11, 11),
            status=InvoiceStatus.ISSUED,
            customer_name="VONOSIS COMPANY LIMITED",
        )

        log = self._run()

        self.assertIn("no generated pdf, skipped", log)
        self.assertFalse(InvoiceDocument.objects.exists())

    def test_skips_when_the_invoice_is_missing(self):
        self.assertIn("not found, skipped", self._run())
