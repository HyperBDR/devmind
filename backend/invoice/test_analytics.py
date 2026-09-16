from datetime import date
from decimal import Decimal

from django.test import TestCase

from invoice.models import (
    Invoice,
    InvoiceDocumentKind,
    InvoiceItem,
    InvoiceStatus,
)
from invoice.services.analytics import sales_dashboard
from invoice.services.regions import derive_customer_region


class SalesDashboardTests(TestCase):
    def setUp(self):
        first = Invoice.objects.create(
            invoice_no="INV-1",
            invoice_date=date(2026, 1, 15),
            customer_name="Acme",
            region="APAC",
            currency="USD",
            status=InvoiceStatus.ISSUED,
            total_amount=Decimal("100"),
        )
        InvoiceItem.objects.create(
            invoice=first,
            line_no=1,
            product_name="Migration",
            total_amount=Decimal("100"),
        )
        Invoice.objects.create(
            invoice_no="INV-2",
            invoice_date=date(2026, 4, 10),
            customer_name="Beta",
            region="EMEA",
            currency="USD",
            status=InvoiceStatus.PAID,
            total_amount=Decimal("250"),
        )
        Invoice.objects.create(
            invoice_no="INV-MYR",
            invoice_date=date(2026, 4, 12),
            customer_name="Gamma",
            region="APAC",
            currency="MYR",
            status=InvoiceStatus.ISSUED,
            total_amount=Decimal("480"),
        )
        Invoice.objects.create(
            invoice_no="DRAFT-1",
            invoice_date=date(2026, 4, 11),
            customer_name="Ignored",
            currency="USD",
            status=InvoiceStatus.DRAFT,
            total_amount=Decimal("999"),
        )
        Invoice.objects.create(
            invoice_no="PF-1",
            invoice_date=date(2026, 4, 12),
            customer_name="Proforma customer",
            currency="USD",
            status=InvoiceStatus.ISSUED,
            document_kind=InvoiceDocumentKind.PROFORMA_INVOICE,
            total_amount=Decimal("5000"),
        )
        Invoice.objects.create(
            invoice_no="REFUND-1",
            invoice_date=date(2026, 4, 13),
            customer_name="Refund customer",
            currency="USD",
            status=InvoiceStatus.ISSUED,
            document_kind=InvoiceDocumentKind.REFUND,
            total_amount=Decimal("-50"),
        )

    def test_dashboard_aggregates_periods_dimensions_and_to_date(self):
        result = sales_dashboard(
            as_of=date(2026, 4, 30),
            currency="USD",
            granularity="quarter",
        )

        self.assertEqual(result["series"][0]["period"], "2026-Q1")
        self.assertEqual(result["series"][1]["amount"], "250.00")
        self.assertEqual(result["quarter_to_date"][0]["amount"], "250.00")
        self.assertEqual(result["year_to_date"][0]["amount"], "350.00")
        self.assertEqual(result["top_customers"][0]["name"], "Beta")
        self.assertEqual(result["by_product"][0]["name"], "Migration")

    def test_dashboard_excludes_non_sales_document_types(self):
        result = sales_dashboard(
            as_of=date(2026, 4, 30),
            currency="USD",
        )

        total = sum(Decimal(row["amount"]) for row in result["series"])
        self.assertEqual(total, Decimal("350.00"))

    def test_dashboard_rejects_unknown_granularity(self):
        with self.assertRaises(ValueError):
            sales_dashboard(granularity="week")

    def test_dashboard_rejects_unsupported_comparison_years(self):
        with self.assertRaises(ValueError):
            sales_dashboard(comparison_years=3)

    def test_dashboard_filters_selected_date_range(self):
        result = sales_dashboard(
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
            currency="USD",
        )

        self.assertEqual(len(result["series"]), 1)
        self.assertEqual(result["series"][0]["amount"], "250.00")
        self.assertEqual(result["start_date"], "2026-04-01")
        self.assertEqual(result["end_date"], "2026-04-30")

    def test_dashboard_top_customers_include_region(self):
        result = sales_dashboard(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 30),
            currency="USD",
        )

        self.assertEqual(result["top_customers"][0]["name"], "Beta")
        self.assertEqual(result["top_customers"][0]["region"], "EMEA")

    def test_customer_region_is_derived_from_customer_address(self):
        invoice = Invoice.objects.create(
            invoice_no="INV-MY-ADDRESS",
            invoice_date=date(2026, 4, 20),
            customer_name="Address customer",
            customer_address="Kuala Lumpur, Malaysia",
            region="APAC",
            currency="USD",
            status=InvoiceStatus.ISSUED,
            total_amount=Decimal("300"),
        )

        result = sales_dashboard(
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
            currency="USD",
        )

        region_names = {
            row["name"] for row in result["by_region"]
        }
        self.assertIn("Malaysia", region_names)
        customer = next(
            row
            for row in result["top_customers"]
            if row["name"] == "Address customer"
        )
        self.assertEqual(customer["region"], "Malaysia")
        self.assertEqual(
            derive_customer_region("10 Anson Road, Singapore 079903"),
            "Singapore",
        )

    def test_customer_region_falls_back_when_address_has_no_country(self):
        Invoice.objects.create(
            invoice_no="INV-ADDRESS-REGION",
            invoice_date=date(2026, 4, 21),
            customer_name="Parsed region customer",
            customer_address="Taman Palem Lestari Ruko Galaxy",
            region="Indonesia",
            currency="USD",
            status=InvoiceStatus.ISSUED,
            total_amount=Decimal("200"),
        )

        result = sales_dashboard(
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
            currency="USD",
        )

        region_names = {row["name"] for row in result["by_region"]}
        self.assertIn("Indonesia", region_names)

    def test_customer_region_uses_country_specific_address_markers(self):
        self.assertEqual(
            derive_customer_region("No. 12, Jalan Meranti, Sdn Bhd 50450"),
            "Malaysia",
        )
        self.assertEqual(
            derive_customer_region("PT Nusantara, Jl. Sudirman 1020"),
            "Indonesia",
        )
        self.assertEqual(
            derive_customer_region("70 Nathan Road, TST, Kowloon"),
            "Hong Kong",
        )
        self.assertEqual(
            derive_customer_region("Makati City 1205, Philippines"),
            "Philippines",
        )
        self.assertEqual(
            derive_customer_region("Morningside, Sandton 2057"),
            "South Africa",
        )

    def test_dashboard_excludes_landing_zone_detail_lines(self):
        invoice = Invoice.objects.create(
            invoice_no="INV-LANDING-ZONE",
            invoice_date=date(2026, 4, 22),
            customer_name="Landing zone customer",
            currency="USD",
            status=InvoiceStatus.ISSUED,
            total_amount=Decimal("300"),
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            line_no=1,
            product_name="Landing zone design",
            description="Landing zone design",
            quantity=1,
            unit_price=Decimal("100"),
            total_amount=Decimal("100"),
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            line_no=2,
            product_name="Landing zone build",
            description="Landing zone build",
            quantity=1,
            unit_price=Decimal("200"),
            total_amount=Decimal("200"),
        )

        result = sales_dashboard(
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
            currency="USD",
        )

        product_names = {row["name"] for row in result["by_product"]}
        self.assertNotIn("Landing zone design", product_names)
        self.assertNotIn("Landing zone build", product_names)

    def test_dashboard_comparison_matches_selected_period(self):
        Invoice.objects.create(
            invoice_no="INV-2025",
            invoice_date=date(2025, 4, 8),
            customer_name="Prior",
            region="APAC",
            currency="USD",
            status=InvoiceStatus.ISSUED,
            total_amount=Decimal("80"),
        )

        result = sales_dashboard(
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
            currency="USD",
            comparison_years=1,
        )

        self.assertEqual(result["comparison"][0]["year"], 2025)
        self.assertEqual(result["comparison"][0]["series"][0]["amount"], "80.00")

    def test_dashboard_filters_amounts_and_lists_available_currencies(self):
        usd = sales_dashboard(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 30),
            currency="USD",
        )
        myr = sales_dashboard(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 30),
            currency="MYR",
        )

        self.assertEqual(
            sum(Decimal(row["amount"]) for row in usd["series"]),
            Decimal("350.00"),
        )
        self.assertEqual(myr["series"][0]["amount"], "480.00")
        self.assertEqual(usd["available_currencies"], ["MYR", "USD"])

    def test_dashboard_growth_periods_do_not_depend_on_chart_granularity(self):
        Invoice.objects.create(
            invoice_no="INV-2025-Q2",
            invoice_date=date(2025, 4, 10),
            customer_name="Prior",
            currency="USD",
            status=InvoiceStatus.ISSUED,
            total_amount=Decimal("125"),
        )

        result = sales_dashboard(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 30),
            currency="USD",
            granularity="year",
            comparison_years=1,
        )

        self.assertEqual(result["quarter_to_date"][0]["amount"], "250.00")
        self.assertEqual(
            result["comparison"][0]["quarter_to_date_amount"],
            "125.00",
        )
        self.assertEqual(
            result["comparison"][0]["year_to_date_amount"],
            "125.00",
        )

    def test_dashboard_year_over_year_uses_matching_rolling_years(self):
        Invoice.objects.create(
            invoice_no="INV-ROLLING-PRIOR",
            invoice_date=date(2025, 4, 10),
            customer_name="Prior",
            currency="USD",
            status=InvoiceStatus.ISSUED,
            total_amount=Decimal("125"),
        )

        result = sales_dashboard(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 30),
            currency="USD",
        )

        self.assertEqual(result["year_over_year"]["amount"], "350.00")
        self.assertEqual(
            result["year_over_year"]["previous_amount"],
            "125.00",
        )
        self.assertEqual(
            result["year_over_year"]["start_date"],
            "2025-05-01",
        )
        self.assertEqual(
            result["year_over_year"]["previous_start_date"],
            "2024-05-01",
        )
