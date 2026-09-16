from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from invoice.parsing.schemas import (
    ParsedInvoice,
    ParsedInvoiceDocumentData,
    ParsedInvoiceItem,
)


class InvoiceParsingSchemaTests(SimpleTestCase):
    def test_invoice_schema_keeps_business_dimensions_and_items(self):
        parsed = ParsedInvoiceDocumentData(
            invoice=ParsedInvoice(
                invoice_no="INV-100",
                invoice_date=date(2026, 9, 4),
                customer_name="Acme Ltd",
                customer_address="1 Example Street",
                purchase_order_no="PO-100",
                bank_swift_code="DBSSHKHH",
                signatory_name="Lucy",
                region="EMEA",
                total_amount=Decimal("120.00"),
                items=[
                    ParsedInvoiceItem(
                        line_no=1,
                        product_name="Migration service",
                        total_amount=Decimal("120.00"),
                    )
                ],
            ),
            field_confidence={"invoice_no": 0.99},
            confidence=Decimal("0.95"),
        )

        payload = parsed.model_dump(mode="json")

        self.assertEqual(payload["invoice"]["region"], "EMEA")
        self.assertEqual(payload["invoice"]["items"][0]["line_no"], 1)
        self.assertEqual(payload["invoice"]["total_amount"], "120.00")
        self.assertEqual(
            payload["invoice"]["customer_address"],
            "1 Example Street",
        )
        self.assertEqual(payload["invoice"]["purchase_order_no"], "PO-100")
        self.assertEqual(payload["invoice"]["bank_swift_code"], "DBSSHKHH")

    def test_invoice_schema_supplies_safe_defaults_for_missing_fields(self):
        parsed = ParsedInvoiceDocumentData(invoice=ParsedInvoice())

        self.assertEqual(parsed.invoice.currency, "USD")
        self.assertEqual(parsed.invoice.items, [])
        self.assertEqual(parsed.validation_errors, [])
