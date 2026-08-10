from datetime import date

from django.test import SimpleTestCase


class QuoteDateParsingTests(SimpleTestCase):
    def test_parses_day_first_numeric_and_compact_dates(self):
        from quotation.services.document_parsing.business_fields import (
            parse_quote_date,
        )

        self.assertEqual(
            parse_quote_date("23.04.2025"),
            date(2025, 4, 23),
        )
        self.assertEqual(
            parse_quote_date("22.05.2025"),
            date(2025, 5, 22),
        )
        self.assertEqual(
            parse_quote_date("29-Apr-26"),
            date(2026, 4, 29),
        )
        self.assertEqual(
            parse_quote_date("14th May, 2026"),
            date(2026, 5, 14),
        )
        self.assertEqual(
            parse_quote_date("2026-08-03"),
            date(2026, 8, 3),
        )
        self.assertEqual(
            parse_quote_date("23042025"),
            date(2025, 4, 23),
        )


class CurrencyNormalizationTests(SimpleTestCase):
    def test_normalizes_document_currency_aliases(self):
        from quotation.services.document_parsing.business_fields import (
            normalize_currency_code,
        )

        self.assertEqual(normalize_currency_code("€"), "EUR")
        self.assertEqual(normalize_currency_code("EURO"), "EUR")
        self.assertEqual(normalize_currency_code("euro"), "EUR")
        self.assertEqual(normalize_currency_code("£"), "GBP")
        self.assertEqual(normalize_currency_code("RMB"), "CNY")
        self.assertEqual(normalize_currency_code("RM"), "MYR")
        self.assertEqual(normalize_currency_code("USD/MYR"), "USD")
        self.assertEqual(normalize_currency_code("HKD"), "HKD")
        self.assertEqual(normalize_currency_code(""), "USD")


class SalespersonRecoveryTests(SimpleTestCase):
    def test_repairs_truncated_onepro_email(self):
        from quotation.services.document_parsing.business_fields import (
            find_issuer_email,
        )

        found = find_issuer_email(
            "evelyn.chee@oneproclo Evelyn Chee HyperBDR"
        )

        self.assertIsNotNone(found)
        self.assertEqual(found[0], "evelyn.chee@oneprocloud.com")

    def test_uses_email_local_part_for_three_part_salesperson(self):
        from quotation.services.document_parsing.business_fields import (
            split_salesperson_after_email,
        )

        name, remaining = split_salesperson_after_email(
            "farid.wajdi.yahaya@oneprocloud.com",
            [
                "FARID",
                "Wajdi",
                "Yahaya",
                "HyperBDR",
                "Renewal",
            ],
        )

        self.assertEqual(name, "FARID Wajdi Yahaya")
        self.assertEqual(remaining, ["HyperBDR", "Renewal"])
