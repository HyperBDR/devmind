from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from quotation.models import Quotation, QuotationVersion, QuoteStatus


class QuotationDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="dashboard-owner",
            email="owner@example.com",
            password="password",
        )
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _quote(
        self,
        quote_no: str,
        *,
        amount: str = "100.00",
        currency: str = "USD",
        owner: str = "owner@example.com",
        quote_date=None,
        status: str = QuoteStatus.GENERATED,
        source_quote_no: str = "",
    ) -> Quotation:
        return Quotation.objects.create(
            quote_no=quote_no,
            source_quote_no=source_quote_no,
            status=status,
            project_name=f"Project {quote_no}",
            currency=currency,
            payment_terms="CIA",
            quote_date=quote_date or "2026-07-01",
            expire_date="2026-08-01",
            grand_total=Decimal(amount),
            issuer_contact_name="Sales Person",
            issuer_contact_email="sales@example.com",
            client_company="Client Company",
            contact_person="Client Contact",
            email="client@example.com",
            created_by_email=owner,
        )

    def _accept(self, quotation: Quotation) -> None:
        QuotationVersion.objects.create(
            quotation=quotation,
            version_no=1,
            status=QuoteStatus.ACCEPTED,
            notes="Accepted",
            snapshot_json={"status": QuoteStatus.ACCEPTED},
        )

    def test_summary_uses_all_accessible_rows_and_separates_currency(self):
        accepted_usd = self._quote(
            "Q-USD-ACCEPTED",
            amount="44000.00",
            status=QuoteStatus.ACCEPTED,
        )
        self._accept(accepted_usd)
        accepted_cny = self._quote(
            "Q-CNY-ACCEPTED",
            amount="99999.00",
            currency="CNY",
            status=QuoteStatus.ACCEPTED,
        )
        self._accept(accepted_cny)
        self._quote("Q-OPEN")
        self._quote("Q-DRAFT", status=QuoteStatus.DRAFT)
        self._quote("Q-HIDDEN", owner="other@example.com")

        response = self.api.get(
            "/api/v1/quotation/dashboard/summary?currency=USD"
        )

        assert response.status_code == 200
        assert response.data["month_won_amount"] == "44000.00"
        assert response.data["success_rate_numerator"] == 1
        assert response.data["success_rate_denominator"] == 2
        assert response.data["success_rate"] == 50
        assert response.data["follow_up_count"] == 1
        assert response.data["draft_count"] == 1
        assert response.data["available_currencies"] == ["CNY", "USD"]

    def test_summary_is_not_limited_to_quotation_list_page_size(self):
        Quotation.objects.bulk_create(
            [
                Quotation(
                    quote_no=f"Q-BULK-{index:03d}",
                    status=QuoteStatus.GENERATED,
                    project_name="Bulk Project",
                    payment_terms="CIA",
                    quote_date="2026-07-01",
                    expire_date="2026-08-01",
                    grand_total=Decimal("1.00"),
                    issuer_contact_name="Sales Person",
                    issuer_contact_email="sales@example.com",
                    client_company="Client Company",
                    contact_person="Client Contact",
                    email="client@example.com",
                    created_by_email="owner@example.com",
                )
                for index in range(205)
            ]
        )

        response = self.api.get("/api/v1/quotation/dashboard/summary")

        assert response.status_code == 200
        assert response.data["follow_up_count"] == 205

    def test_summary_aggregates_current_and_previous_month_quotes(self):
        current_month = timezone.localdate().replace(day=1)
        previous_month = (current_month - timedelta(days=1)).replace(day=1)
        self._quote(
            "Q-CURRENT-1",
            amount="125.00",
            quote_date=current_month,
        )
        self._quote(
            "Q-CURRENT-2",
            amount="75.00",
            quote_date=timezone.localdate(),
        )
        self._quote(
            "Q-PREVIOUS",
            amount="80.00",
            quote_date=previous_month,
        )
        self._quote(
            "Q-CURRENT-CNY",
            amount="900.00",
            currency="CNY",
            quote_date=current_month,
        )
        self._quote(
            "Q-CURRENT-HIDDEN",
            amount="500.00",
            owner="other@example.com",
            quote_date=current_month,
        )

        response = self.api.get(
            "/api/v1/quotation/dashboard/summary?currency=USD"
        )

        assert response.status_code == 200
        assert response.data["current_period"] == current_month.strftime(
            "%Y-%m"
        )
        assert response.data["previous_period"] == previous_month.strftime(
            "%Y-%m"
        )
        assert response.data["month_quote_count"] == 2
        assert response.data["previous_month_quote_count"] == 1
        assert response.data["month_quote_amount"] == "200.00"
        assert response.data["previous_month_quote_amount"] == "80.00"

    def test_summary_uses_selected_calendar_month(self):
        self._quote(
            "Q-JUNE",
            amount="60.00",
            quote_date="2026-06-15",
        )
        self._quote(
            "Q-JULY-1",
            amount="125.00",
            quote_date="2026-07-01",
        )
        self._quote(
            "Q-JULY-2",
            amount="75.00",
            quote_date="2026-07-31",
        )

        response = self.api.get(
            "/api/v1/quotation/dashboard/summary"
            "?currency=USD&period=2026-07"
        )

        assert response.status_code == 200
        assert response.data["current_period"] == "2026-07"
        assert response.data["previous_period"] == "2026-06"
        assert response.data["month_quote_count"] == 2
        assert response.data["month_quote_amount"] == "200.00"
        assert response.data["previous_month_quote_count"] == 1
        assert response.data["previous_month_quote_amount"] == "60.00"
        assert response.data["available_periods"] == [
            "2026-07",
            "2026-06",
        ]

    def test_summary_month_stats_ignore_currency(self):
        self._quote(
            "Q-CNY-JULY",
            amount="180.00",
            currency="CNY",
            quote_date="2026-07-13",
        )
        self._quote(
            "Q-MYR-AUG",
            amount="90.00",
            currency="MYR",
            quote_date="2026-08-03",
        )

        response = self.api.get(
            "/api/v1/quotation/dashboard/summary"
            "?currency=CNY&period=2026-08"
        )

        assert response.status_code == 200
        assert response.data["month_quote_count"] == 0
        assert response.data["month_quote_amount"] == "0.00"
        assert response.data["available_periods"] == [
            "2026-08",
            "2026-07",
        ]

    def test_cny_dashboard_merges_rmb_alias_without_duplicate_option(self):
        current_month = timezone.localdate().replace(day=1)
        accepted_rmb = self._quote(
            "Q-RMB-ACCEPTED",
            amount="300.00",
            currency="RMB",
            quote_date=current_month,
            status=QuoteStatus.ACCEPTED,
        )
        self._accept(accepted_rmb)
        self._quote(
            "Q-CNY-CURRENT",
            amount="200.00",
            currency="CNY",
            quote_date=current_month,
        )
        self._quote(
            "Q-HKD-CURRENT",
            amount="900.00",
            currency="HKD",
            quote_date=current_month,
        )

        summary = self.api.get(
            "/api/v1/quotation/dashboard/summary?currency=CNY"
        )
        analytics = self.api.get(
            "/api/v1/quotation/dashboard/analytics?currency=CNY"
        )

        assert summary.status_code == 200
        assert summary.data["currency"] == "CNY"
        assert summary.data["available_currencies"] == ["CNY", "HKD"]
        assert summary.data["month_quote_count"] == 2
        assert summary.data["month_quote_amount"] == "500.00"
        assert summary.data["month_won_amount"] == "300.00"
        assert analytics.status_code == 200
        assert analytics.data["currency"] == "CNY"
        assert analytics.data["available_currencies"] == ["CNY", "HKD"]
        assert analytics.data["breakdown_total_amount"] == "500.00"
        assert {
            row["quote_no"] for row in analytics.data["amount_breakdown"]
        } == {"Q-CNY-CURRENT", "Q-RMB-ACCEPTED"}
        assert {
            row["currency"] for row in analytics.data["amount_breakdown"]
        } == {"CNY"}

    def test_analytics_breakdown_uses_range_and_keeps_currency(self):
        current_month = timezone.localdate().replace(day=1)
        previous_month = (current_month - timedelta(days=1)).replace(day=1)
        self._quote(
            "Q-CNY-CURRENT",
            amount="200.00",
            currency="CNY",
            quote_date=current_month,
        )
        self._quote(
            "Q-CNY-PREVIOUS",
            amount="900.00",
            currency="CNY",
            quote_date=previous_month,
        )
        self._quote(
            "Q-USD-CURRENT",
            amount="300.00",
            currency="USD",
            quote_date=current_month,
        )
        self._quote(
            "Q-IMP-1",
            amount="80.00",
            currency="CNY",
            quote_date=current_month,
            source_quote_no="Motion260326",
        )
        self._quote(
            "Q-IMP-2",
            amount="120.00",
            currency="CNY",
            quote_date=current_month,
            source_quote_no="Motion260326",
        )
        period = current_month.strftime("%Y-%m")

        response = self.api.get(
            "/api/v1/quotation/dashboard/analytics"
            f"?currency=CNY&date_from={period}&date_to={period}"
        )

        assert response.status_code == 200
        quote_nos = [
            row["quote_no"] for row in response.data["amount_breakdown"]
        ]
        assert "Q-CNY-PREVIOUS" not in quote_nos
        assert "Q-USD-CURRENT" not in quote_nos
        assert "Q-CNY-CURRENT" in quote_nos
        assert len(quote_nos) == len(set(quote_nos))
        assert {
            row["currency"] for row in response.data["amount_breakdown"]
        } == {"CNY"}
        assert response.data["breakdown_total_amount"] == "400.00"
        assert set(quote_nos) == {
            "Q-CNY-CURRENT",
            "Q-IMP-1",
            "Q-IMP-2",
        }

    def test_rmb_dashboard_request_is_normalized_to_cny(self):
        current_month = timezone.localdate().replace(day=1)
        self._quote(
            "Q-CNY",
            amount="125.00",
            currency="CNY",
            quote_date=current_month,
        )
        self._quote(
            "Q-RMB",
            amount="75.00",
            currency="RMB",
            quote_date=current_month,
        )

        response = self.api.get(
            "/api/v1/quotation/dashboard/summary?currency=RMB"
        )

        assert response.status_code == 200
        assert response.data["currency"] == "CNY"
        assert response.data["month_quote_amount"] == "200.00"
        assert response.data["available_currencies"] == ["CNY"]

    def test_analytics_returns_bounded_rows_and_fixed_period_counts(self):
        accepted = self._quote(
            "Q-ACCEPTED",
            amount="300.00",
            status=QuoteStatus.ACCEPTED,
        )
        self._accept(accepted)
        for index in range(12):
            self._quote(
                f"Q-CHART-{index:02d}",
                amount=str(200 - index),
            )
        self._quote(
            "Q-CANCELLED",
            amount="9999.00",
            status=QuoteStatus.CANCELLED,
        )
        self._quote(
            "Q-CNY",
            amount="9999.00",
            currency="CNY",
        )

        response = self.api.get(
            "/api/v1/quotation/dashboard/analytics?currency=USD"
        )

        assert response.status_code == 200
        assert len(response.data["amount_breakdown"]) == 8
        assert len(response.data["trends"]["monthly"]) == 6
        assert len(response.data["trends"]["weekly"]) == 8
        assert any(
            Decimal(row["created_amount"]) > 0
            for row in response.data["trends"]["monthly"]
        )
        assert any(
            Decimal(row["won_amount"]) == Decimal("300.00")
            for row in response.data["trends"]["monthly"]
        )
        assert any(
            Decimal(row["created_amount"]) > 0
            for row in response.data["trends"]["weekly"]
        )
        assert any(
            Decimal(row["won_amount"]) == Decimal("300.00")
            for row in response.data["trends"]["weekly"]
        )
        july = next(
            row
            for row in response.data["trends"]["monthly"]
            if row["period"] == "2026-07"
        )
        assert july["quote_count"] == 14
        assert Decimal(july["quote_amount"]) == Decimal("12633.00")
        quote_numbers = {
            row["quote_no"] for row in response.data["amount_breakdown"]
        }
        assert "Q-CANCELLED" not in quote_numbers
        assert "Q-CNY" not in quote_numbers
        assert response.data["breakdown_omitted_count"] == 5

    def test_eur_dashboard_merges_euro_aliases_and_excludes_hkd(self):
        self._quote(
            "Q-EUR",
            amount="3704.00",
            currency="EUR",
        )
        self._quote(
            "Q-EURO",
            amount="148.16",
            currency="EURO",
        )
        self._quote(
            "Q-EURO-SYMBOL",
            amount="703.76",
            currency="€",
        )
        self._quote(
            "Q-HKD",
            amount="22668.50",
            currency="HKD",
        )

        analytics = self.api.get(
            "/api/v1/quotation/dashboard/analytics?currency=EUR"
        )

        assert analytics.status_code == 200
        assert analytics.data["currency"] == "EUR"
        assert analytics.data["breakdown_total_amount"] == "4555.92"
        assert {
            row["quote_no"] for row in analytics.data["amount_breakdown"]
        } == {"Q-EUR", "Q-EURO", "Q-EURO-SYMBOL"}
        assert {
            row["currency"] for row in analytics.data["amount_breakdown"]
        } == {"EUR"}

    def test_recent_returns_updated_projection_and_honors_access(self):
        recently_updated = self._quote("Q-OLDER", amount="8143.75")
        self._quote("Q-NEWEST")
        self._quote("Q-HIDDEN", owner="other@example.com")
        Quotation.objects.filter(pk=recently_updated.pk).update(
            updated_at=timezone.now() + timedelta(minutes=1)
        )
        recently_updated.refresh_from_db()

        response = self.api.get(
            "/api/v1/quotation/dashboard/recent?limit=1"
        )

        assert response.status_code == 200
        assert response.data == {
            "items": [
                {
                    "id": recently_updated.id,
                    "quote_no": "Q-OLDER",
                    "project_name": "Project Q-OLDER",
                    "client_company": "Client Company",
                    "salesperson": "Sales Person",
                    "created_at": recently_updated.created_at.isoformat(),
                    "updated_at": recently_updated.updated_at.isoformat(),
                    "currency": "USD",
                    "grand_total": "8143.75",
                    "status": QuoteStatus.GENERATED,
                }
            ]
        }

    def test_dashboard_query_counts_remain_bounded(self):
        accepted = self._quote(
            "Q-PERF-ACCEPTED",
            status=QuoteStatus.ACCEPTED,
        )
        self._accept(accepted)
        for index in range(20):
            self._quote(f"Q-PERF-{index:02d}")

        with CaptureQueriesContext(connection) as summary_queries:
            summary = self.api.get(
                "/api/v1/quotation/dashboard/summary?currency=USD"
            )
        with CaptureQueriesContext(connection) as analytics_queries:
            analytics = self.api.get(
                "/api/v1/quotation/dashboard/analytics?currency=USD"
            )
        with CaptureQueriesContext(connection) as recent_queries:
            recent = self.api.get(
                "/api/v1/quotation/dashboard/recent?limit=5"
            )

        assert summary.status_code == 200
        assert analytics.status_code == 200
        assert recent.status_code == 200
        # Authorization performs a fixed set of profile and role lookups.
        assert len(summary_queries) <= 8
        assert len(analytics_queries) <= 12
        assert len(recent_queries) <= 6

    def test_dashboard_query_validation_rejects_unbounded_inputs(self):
        invalid_currency = self.api.get(
            "/api/v1/quotation/dashboard/summary?currency=usd"
        )
        invalid_limit = self.api.get(
            "/api/v1/quotation/dashboard/recent?limit=1000"
        )
        invalid_period = self.api.get(
            "/api/v1/quotation/dashboard/summary?period=2026-13"
        )

        assert invalid_currency.status_code == 400
        assert invalid_limit.status_code == 400
        assert invalid_period.status_code == 400
