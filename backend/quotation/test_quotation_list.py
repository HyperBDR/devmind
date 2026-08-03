from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from quotation.models import (
    Quotation,
    QuotationItem,
    QuotationSourceType,
    QuotationVersion,
    QuoteStatus,
)


class QuotationListAPITests(TestCase):
    url = "/api/v1/quotation/quotations"

    def setUp(self):
        self.user = User.objects.create_user(
            username="list-owner",
            email="owner@example.com",
            password="password",
        )
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _quote(
        self,
        index: int,
        *,
        owner: str = "owner@example.com",
        status: str = QuoteStatus.DRAFT,
        product_line: str = "BDR",
        source_type: str = QuotationSourceType.MANUAL,
        created_at=None,
    ) -> Quotation:
        quotation = Quotation.objects.create(
            quote_no=f"Q-LIST-{index:03d}",
            source_quote_no=(
                f"SOURCE-{index:03d}"
                if source_type == QuotationSourceType.DOCUMENT_IMPORT
                else ""
            ),
            status=status,
            source_type=source_type,
            product_line=product_line,
            project_name=f"Project Alpha {index}",
            currency="USD",
            payment_terms="CIA",
            quote_date="2026-07-01",
            expire_date="2026-08-01",
            grand_total=Decimal(index + 1),
            issuer_contact_name="Sales Person",
            issuer_contact_email="sales@example.com",
            client_company=f"Client {index}",
            contact_person=f"Contact {index}",
            email=f"client-{index}@example.com",
            created_by_email=owner,
        )
        if created_at:
            Quotation.objects.filter(pk=quotation.pk).update(
                created_at=created_at,
                updated_at=created_at,
            )
            quotation.refresh_from_db()
        return quotation

    def _create_quotes(self, count: int) -> list[Quotation]:
        now = timezone.now()
        return [
            self._quote(
                index,
                created_at=now + timedelta(seconds=index),
            )
            for index in range(count)
        ]

    def test_default_page_size_and_stable_second_page(self):
        quotes = self._create_quotes(12)

        first = self.api.get(self.url)
        second = self.api.get(f"{self.url}?page=2")

        assert first.status_code == 200
        assert len(first.data["items"]) == 10
        assert first.data["total"] == 12
        assert first.data["page"] == 1
        assert first.data["page_size"] == 10
        assert first.data["total_pages"] == 2
        assert first.data["items"][0]["quote_date"] == "2026-07-01"
        assert len(second.data["items"]) == 2
        assert second.data["page"] == 2
        expected = sorted(
            quotes,
            key=lambda quote: (quote.created_at, quote.id),
            reverse=True,
        )
        assert [row["id"] for row in first.data["items"]] == [
            quote.id for quote in expected[:10]
        ]
        assert [row["id"] for row in second.data["items"]] == [
            quote.id for quote in expected[10:]
        ]

    def test_allowed_page_sizes(self):
        self._create_quotes(55)

        for page_size in (20, 50):
            with self.subTest(page_size=page_size):
                response = self.api.get(
                    f"{self.url}?page_size={page_size}"
                )
                assert response.status_code == 200
                assert len(response.data["items"]) == page_size
                assert response.data["page_size"] == page_size

    def test_invalid_page_and_page_size(self):
        for query in (
            "page=0",
            "page=-1",
            "page=abc",
            "page_size=11",
            "page_size=all",
        ):
            with self.subTest(query=query):
                response = self.api.get(f"{self.url}?{query}")
                assert response.status_code == 400
                assert response.data == {"detail": "invalid pagination"}

    def test_empty_result_and_page_beyond_result_are_valid(self):
        empty = self.api.get(f"{self.url}?search=does-not-exist")
        beyond = self.api.get(f"{self.url}?page=3")

        assert empty.data == {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 10,
            "total_pages": 0,
        }
        assert beyond.status_code == 200
        assert beyond.data["items"] == []

    def test_searches_only_supported_list_fields(self):
        quote = self._quote(
            1,
            source_type=QuotationSourceType.DOCUMENT_IMPORT,
        )
        values = (
            quote.quote_no,
            quote.source_quote_no,
            quote.project_name,
            quote.client_company,
            quote.contact_person,
        )

        for value in values:
            with self.subTest(value=value):
                response = self.api.get(
                    self.url,
                    {"search": value.lower()},
                )
                assert response.data["total"] == 1
        email_search = self.api.get(
            self.url,
            {"search": quote.email},
        )
        assert email_search.data["total"] == 0

    def test_status_product_source_and_combined_filters(self):
        matching = self._quote(
            1,
            status=QuoteStatus.SENT,
            product_line="MOTION",
            source_type=QuotationSourceType.DOCUMENT_IMPORT,
        )
        self._quote(2, status=QuoteStatus.SENT, product_line="BDR")

        status_result = self.api.get(self.url, {"status": "sent"})
        product_result = self.api.get(
            self.url,
            {"product_line": "MOTION"},
        )
        source_result = self.api.get(
            self.url,
            {"source_type": "document_import"},
        )
        combined = self.api.get(
            self.url,
            {
                "search": matching.client_company,
                "status": "sent",
                "product_line": "MOTION",
                "source_type": "document_import",
            },
        )

        assert status_result.data["total"] == 2
        assert product_result.data["total"] == 1
        assert source_result.data["total"] == 1
        assert [row["id"] for row in combined.data["items"]] == [
            matching.id
        ]

    def test_created_date_range_includes_the_whole_end_date(self):
        local_tz = timezone.get_current_timezone()
        selected_date = timezone.localdate()
        start = timezone.make_aware(
            datetime.combine(selected_date, time.min),
            local_tz,
        )
        inside = self._quote(
            1,
            created_at=start + timedelta(hours=23, minutes=59),
        )
        self._quote(2, created_at=start - timedelta(seconds=1))
        self._quote(3, created_at=start + timedelta(days=1))

        response = self.api.get(
            self.url,
            {
                "created_from": selected_date.isoformat(),
                "created_to": selected_date.isoformat(),
            },
        )

        assert [row["id"] for row in response.data["items"]] == [
            inside.id
        ]

    def test_owner_permission_and_staff_visibility(self):
        own = self._quote(1)
        other = self._quote(2, owner="other@example.com")

        owner_response = self.api.get(self.url)
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        staff_response = self.api.get(self.url)

        assert [row["id"] for row in owner_response.data["items"]] == [
            own.id
        ]
        assert {row["id"] for row in staff_response.data["items"]} == {
            own.id,
            other.id,
        }

    def test_list_is_lightweight_and_item_count_is_annotated(self):
        quotation = self._quote(1)
        for line_no in (1, 2):
            QuotationItem.objects.create(
                quotation=quotation,
                line_no=line_no,
                type="Software",
                qty=1,
                list_price=10,
                discount_percent=0,
                net_unit_price=10,
                extended_price=10,
            )
        QuotationVersion.objects.create(
            quotation=quotation,
            version_no=1,
            status=QuoteStatus.DRAFT,
            snapshot_json={"items": [{"secret": "large"}]},
        )

        response = self.api.get(self.url)
        row = response.data["items"][0]

        assert row["item_count"] == 2
        assert "items" not in row
        assert "versions" not in row
        assert "snapshot_json" not in row
        assert "documents" not in row

    def test_detail_still_returns_items_versions_and_snapshots(self):
        quotation = self._quote(1)
        QuotationItem.objects.create(
            quotation=quotation,
            line_no=1,
            type="Software",
            qty=1,
            list_price=10,
            discount_percent=0,
            net_unit_price=10,
            extended_price=10,
        )
        QuotationVersion.objects.create(
            quotation=quotation,
            version_no=1,
            status=QuoteStatus.DRAFT,
            snapshot_json={"status": "draft"},
        )

        response = self.api.get(f"{self.url}/{quotation.id}")

        assert response.status_code == 200
        assert len(response.data["items"]) == 1
        assert len(response.data["versions"]) == 1
        assert response.data["versions"][0]["snapshot"] == {
            "status": "draft"
        }

    def test_list_query_count_does_not_grow_with_page_size(self):
        self._create_quotes(50)

        with CaptureQueriesContext(connection) as ten_queries:
            ten = self.api.get(f"{self.url}?page_size=10")
        with CaptureQueriesContext(connection) as fifty_queries:
            fifty = self.api.get(f"{self.url}?page_size=50")

        assert ten.status_code == 200
        assert fifty.status_code == 200
        assert len(ten.data["items"]) == 10
        assert len(fifty.data["items"]) == 50
        assert len(fifty_queries) <= len(ten_queries) + 1
