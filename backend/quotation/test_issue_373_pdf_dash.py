from decimal import Decimal

from django.test import SimpleTestCase

from quotation.services.document_parsing.excel_parser import (
    QuotationExcelParseError,
    _decimal,
)
from quotation.services.document_parsing.pdf_parser import (
    _parse_currency_item_line,
)


class Issue373PdfDashTests(SimpleTestCase):
    def test_decimal_treats_standalone_dash_as_zero(self):
        self.assertEqual(_decimal(" "), Decimal("0"))
        self.assertEqual(_decimal("-"), Decimal("0"))
        self.assertEqual(_decimal("-12.5"), Decimal("-12.5"))
        self.assertEqual(_decimal("(12.5)"), Decimal("-12.5"))
        self.assertEqual(_decimal("1,234.50%"), Decimal("1234.50"))

        for value in ("abc", "1-2", "not-a-number"):
            with self.subTest(value=value):
                with self.assertRaisesMessage(
                    QuotationExcelParseError,
                    f"Invalid numeric value: {value}",
                ):
                    _decimal(value)

    def test_parses_pdf_currency_item_with_zero_price_placeholder(self):
        item = _parse_currency_item_line(
            "1 Support 1 $ 5,300.0 100% $ - $0.0",
            "",
        )

        self.assertIsNotNone(item)
        self.assertEqual(item.list_price, Decimal("5300.0"))
        self.assertEqual(item.discount_percent, Decimal("100"))
        self.assertEqual(item.net_unit_price, Decimal("0"))
        self.assertEqual(item.extended_price, Decimal("0.0"))
