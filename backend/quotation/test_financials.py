from decimal import Decimal

from django.test import SimpleTestCase

from quotation.services.financials import calculate_document_totals


class DocumentFinancialsTests(SimpleTestCase):
    def test_calculates_category_totals_and_vat(self):
        items = [
            type(
                "Item",
                (),
                {"type": "Software", "extended_price": "10.005"},
            )(),
            type(
                "Item",
                (),
                {"type": "Service", "extended_price": "5.00"},
            )(),
        ]

        self.assertEqual(
            calculate_document_totals(items, Decimal("10")),
            {
                "software_subtotal": Decimal("10.01"),
                "others_subtotal": Decimal("5.00"),
                "subtotal_before_vat": Decimal("15.01"),
                "vat_amount": Decimal("1.50"),
                "deduction_amount": Decimal("0.00"),
                "grand_total": Decimal("16.51"),
            },
        )

    def test_supports_one_shot_iterators(self):
        item = type(
            "Item",
            (),
            {"type": "Software", "extended_price": "12.00"},
        )()

        totals = calculate_document_totals(iter([item]), Decimal("0"))

        self.assertEqual(totals["grand_total"], Decimal("12.00"))

    def test_can_subtract_tax_from_subtotal(self):
        item = type(
            "Item",
            (),
            {"type": "Software", "extended_price": "100.00"},
        )()

        totals = calculate_document_totals(
            [item],
            Decimal("10"),
            tax_mode="subtract",
        )

        self.assertEqual(totals["vat_amount"], Decimal("10.00"))
        self.assertEqual(totals["grand_total"], Decimal("90.00"))

    def test_deducts_manual_amount_from_grand_total(self):
        item = type(
            "Item",
            (),
            {"type": "Software", "extended_price": "100.00"},
        )()

        totals = calculate_document_totals(
            [item],
            Decimal("10"),
            deduction_amount=Decimal("15"),
        )

        self.assertEqual(totals["vat_amount"], Decimal("10.00"))
        self.assertEqual(totals["deduction_amount"], Decimal("15.00"))
        self.assertEqual(totals["grand_total"], Decimal("95.00"))

    def test_deduction_cannot_make_grand_total_negative(self):
        item = type(
            "Item",
            (),
            {"type": "Software", "extended_price": "10.00"},
        )()

        totals = calculate_document_totals(
            [item],
            Decimal("0"),
            deduction_amount=Decimal("99"),
        )

        self.assertEqual(totals["deduction_amount"], Decimal("10.00"))
        self.assertEqual(totals["grand_total"], Decimal("0.00"))
