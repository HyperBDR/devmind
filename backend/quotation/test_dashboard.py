from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
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
        status: str = QuoteStatus.GENERATED,
    ) -> Quotation:
        return Quotation.objects.create(
            quote_no=quote_no,
            status=status,
            project_name=f"Project {quote_no}",
            currency=currency,
            payment_terms="CIA",
            quote_date="2026-07-01",
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
        assert response.data["success_rate_numerator"] == 2
        assert response.data["success_rate_denominator"] == 3
        assert response.data["success_rate"] == 67
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
        assert Decimal(
            response.data["trends"]["monthly"][-1]["created_amount"]
        ) > 0
        assert Decimal(
            response.data["trends"]["monthly"][-1]["won_amount"]
        ) == Decimal("300.00")
        assert Decimal(
            response.data["trends"]["weekly"][-1]["created_amount"]
        ) > 0
        assert Decimal(
            response.data["trends"]["weekly"][-1]["won_amount"]
        ) == Decimal("300.00")
        quote_numbers = {
            row["quote_no"] for row in response.data["amount_breakdown"]
        }
        assert "Q-CANCELLED" not in quote_numbers
        assert "Q-CNY" not in quote_numbers
        assert response.data["breakdown_omitted_count"] == 5

    def test_recent_returns_projection_and_honors_access_and_limit(self):
        self._quote("Q-OLDER")
        newest = self._quote("Q-NEWEST", amount="8143.75")
        self._quote("Q-HIDDEN", owner="other@example.com")

        response = self.api.get(
            "/api/v1/quotation/dashboard/recent?limit=1"
        )

        assert response.status_code == 200
        assert response.data == {
            "items": [
                {
                    "id": newest.id,
                    "quote_no": "Q-NEWEST",
                    "project_name": "Project Q-NEWEST",
                    "client_company": "Client Company",
                    "salesperson": "Sales Person",
                    "created_at": newest.created_at.isoformat(),
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

        assert invalid_currency.status_code == 400
        assert invalid_limit.status_code == 400
