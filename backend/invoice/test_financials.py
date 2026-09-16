from decimal import Decimal

from django.test import SimpleTestCase

from invoice.services.financials import calculate_invoice_amounts


class InvoiceFinancialTests(SimpleTestCase):
    def test_amounts_use_half_up_currency_rounding(self):
        items, totals = calculate_invoice_amounts(
            [
                {
                    "line_no": 1,
                    "product_name": "Usage",
                    "quantity": Decimal("3"),
                    "unit_price": Decimal("0.335"),
                }
            ],
            Decimal("7.25"),
        )

        self.assertEqual(items[0]["net_amount"], Decimal("1.01"))
        self.assertEqual(items[0]["tax_amount"], Decimal("0.07"))
        self.assertEqual(items[0]["total_amount"], Decimal("1.08"))
        self.assertEqual(totals["total_amount"], Decimal("1.08"))
