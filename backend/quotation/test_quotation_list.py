from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from quotation.models import (
    DocumentAsset,
    DocumentParseResult,
    DocumentParseStatus,
    Quotation,
    QuotationItem,
    QuotationMembership,
    QuotationSourceType,
    QuotationVersion,
    QuoteStatus,
)


class QuotationListAPITests(TestCase):
    url = "/api/v1/quotation/quotations"
    form_context_url = "/api/v1/quotation/quotations/form-context"

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
        product_line_name: str = "HyperBDR",
        source_type: str = QuotationSourceType.MANUAL,
        quote_date: str = "2026-07-01",
        salesperson: str = "Sales Person",
        salesperson_email: str = "sales@example.com",
        created_at=None,
    ) -> Quotation:
        if (
            source_type == QuotationSourceType.DOCUMENT_IMPORT
            and salesperson == "Sales Person"
        ):
            salesperson = self.user.username
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
            product_line_name=product_line_name,
            project_name=f"Project Alpha {index}",
            currency="USD",
            payment_terms="CIA",
            quote_date=quote_date,
            expire_date="2026-08-01",
            grand_total=Decimal(index + 1),
            issuer_contact_name=salesperson,
            issuer_contact_email=salesperson_email,
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

    def test_form_context_returns_all_imported_quotes(self):
        imported = self._quote(
            1,
            owner="other@example.com",
            status=QuoteStatus.GENERATED,
            source_type=QuotationSourceType.DOCUMENT_IMPORT,
        )
        QuotationItem.objects.create(
            quotation=imported,
            line_no=1,
            type="Software",
            description="Parsed HyperBDR License",
            list_price=35,
        )
        self._quote(
            2,
            owner="owner@example.com",
            source_type=QuotationSourceType.MANUAL,
        )

        response = self.api.get(self.form_context_url)

        assert response.status_code == 200
        assert [item["id"] for item in response.data["items"]] == [
            imported.id
        ]
        assert response.data["line_item_history"] == [
            {
                "type": "Software",
                "description": "Parsed HyperBDR License",
                "list_price": "35.00",
                "currency": "USD",
            }
        ]
        assert set(response.data["quote_numbers"]) == {
            imported.quote_no,
        }

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

    def test_list_facets_include_currencies_across_all_pages(self):
        self._quote(1)
        cny = self._quote(2)
        Quotation.objects.filter(pk=cny.pk).update(currency="CNY")

        response = self.api.get(self.url)

        assert response.status_code == 200
        assert response.data["facets"]["currencies"] == ["CNY", "USD"]

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

    def test_copy_creates_independent_unnumbered_draft(self):
        source = self._quote(1, status=QuoteStatus.ACCEPTED)
        source.remarks_disclaimer = "Customer-specific notes"
        source.save(update_fields=["remarks_disclaimer"])
        QuotationItem.objects.create(
            quotation=source,
            line_no=1,
            type="Service",
            name="Migration",
            description="Migration service",
            qty=Decimal("2"),
            list_price=Decimal("50"),
            discount_percent=Decimal("10"),
            net_unit_price=Decimal("45"),
            extended_price=Decimal("90"),
        )
        QuotationVersion.objects.create(
            quotation=source,
            version_no=1,
            status=source.status,
            snapshot_json={"quote_no": source.quote_no},
        )
        self._quote(2, quote_date="2026-07-01")
        Quotation.objects.filter(quote_no="Q-LIST-002").update(
            quote_no="BDR010726"
        )

        response = self.api.post(f"{self.url}/{source.pk}/copy")

        assert response.status_code == 201
        copied = Quotation.objects.get(pk=response.data["id"])
        assert copied.pk != source.pk
        assert copied.quote_no is None
        copied_date = timezone.localdate()
        expected_draft_no = (
            f"BDR{copied_date.day:02d}{copied_date.month:02d}"
            f"{copied_date.year % 100:02d}"
        )
        assert copied.draft_quote_no == expected_draft_no
        assert copied.quote_date == copied_date
        assert copied.status == QuoteStatus.DRAFT
        assert copied.source_type == QuotationSourceType.MANUAL
        assert copied.client_company == source.client_company
        assert copied.email == source.email
        assert copied.remarks_disclaimer == source.remarks_disclaimer
        assert copied.created_by_email == self.user.email
        assert copied.versions.count() == 0
        assert list(
            copied.items.values_list(
                "line_no", "description", "extended_price"
            )
        ) == [(1, "Migration service", Decimal("90.00"))]

    def test_copy_rejects_document_imported_quotation(self):
        imported = self._quote(
            3,
            source_type=QuotationSourceType.DOCUMENT_IMPORT,
        )

        response = self.api.post(f"{self.url}/{imported.pk}/copy")

        assert response.status_code == 409
        assert response.data["detail"] == (
            "document-imported quotations cannot be copied"
        )
        assert Quotation.objects.filter(
            pk=imported.pk,
        ).count() == 1

    def test_repeated_copy_uses_distinct_draft_numbers_without_revision(self):
        copied_date = timezone.localdate()
        base = (
            f"BDR{copied_date.day:02d}{copied_date.month:02d}"
            f"{copied_date.year % 100:02d}"
        )
        source = self._quote(4, status=QuoteStatus.ACCEPTED)
        source.quote_no = f"{base}_R1"
        source.save(update_fields=["quote_no"])

        first = self.api.post(f"{self.url}/{source.pk}/copy")
        second = self.api.post(f"{self.url}/{source.pk}/copy")

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.data["display_quote_no"] == f"{base}.1"
        assert second.data["display_quote_no"] == f"{base}.2"
        assert "_R1" not in first.data["display_quote_no"]
        assert "_R1" not in second.data["display_quote_no"]

    def test_form_context_includes_automatic_draft_numbers(self):
        draft = self._quote(5)
        draft.quote_no = None
        draft.draft_quote_no = "BDR010726.1"
        draft.numbering_mode = "auto"
        draft.save(
            update_fields=[
                "quote_no",
                "draft_quote_no",
                "numbering_mode",
            ]
        )

        response = self.api.get(self.form_context_url)

        assert response.status_code == 200
        assert response.data["quote_numbers"] == ["BDR010726.1"]

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
            "facets": {
                "product_lines": [],
                "currencies": [],
                "creators": [],
            },
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

    def test_quote_date_range_is_inclusive_and_ignores_created_time(self):
        inside = self._quote(
            1,
            quote_date="2026-07-15",
            created_at=timezone.now() - timedelta(days=365),
        )
        self._quote(2, quote_date="2026-07-14")
        self._quote(3, quote_date="2026-07-16")

        response = self.api.get(
            self.url,
            {
                "created_from": "2026-07-15",
                "created_to": "2026-07-15",
            },
        )

        assert [row["id"] for row in response.data["items"]] == [
            inside.id
        ]

    def test_filters_by_current_or_selected_quote_creator(self):
        own = self._quote(
            1,
            salesperson=self.user.username,
            salesperson_email=self.user.email,
        )
        other_user = User.objects.create_user(
            username="other-creator",
            email="other@example.com",
        )
        other = self._quote(
            2,
            owner=other_user.email,
            salesperson=other_user.username,
            salesperson_email=other_user.email,
        )
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])

        mine = self.api.get(self.url, {"quoted_by": "me"})
        selected = self.api.get(
            self.url,
            {"quoted_by": "OTHER@example.com"},
        )

        assert [row["id"] for row in mine.data["items"]] == [own.id]
        assert [row["id"] for row in selected.data["items"]] == [
            other.id
        ]
        assert selected.data["facets"]["creators"] == [
            {
                "email": "owner@example.com",
                "name": "list-owner",
                "is_me": True,
            },
            {
                "email": "other@example.com",
                "name": "other-creator",
                "is_me": False,
            },
        ]

    def test_creator_facets_do_not_expose_inaccessible_quotes(self):
        self._quote(
            1,
            salesperson=self.user.username,
            salesperson_email=self.user.email,
        )
        self._quote(2, owner="private@example.com")

        response = self.api.get(self.url)

        assert response.data["facets"]["creators"] == [
            {
                "email": "owner@example.com",
                "name": "list-owner",
                "is_me": True,
            }
        ]

    def test_creator_facets_include_active_members_without_quotes(self):
        member = User.objects.create_user(
            username="member-without-quotes",
            email="member@example.com",
        )
        QuotationMembership.objects.create(user=member)
        self._quote(
            1,
            salesperson=self.user.username,
            salesperson_email=self.user.email,
        )

        response = self.api.get(self.url)

        assert response.data["facets"]["creators"] == [
            {
                "email": "owner@example.com",
                "name": "list-owner",
                "is_me": True,
            },
            {
                "email": "member@example.com",
                "name": "member-without-quotes",
                "is_me": False,
            },
        ]

    def test_list_returns_quote_date_salesperson_and_business_product_line(self):
        quotation = self._quote(
            1,
            product_line="Motion",
            product_line_name="HyperMotion",
            quote_date="2026-07-12",
            salesperson="Taylor Sales",
        )

        response = self.api.get(self.url)
        row = response.data["items"][0]

        assert row["id"] == quotation.id
        assert row["quote_date"] == "2026-07-12"
        assert row["issuer_contact_name"] == "Taylor Sales"
        assert row["product_line_name"] == "HyperMotion"

    def test_product_line_facets_cover_accessible_rows_beyond_page(self):
        self._create_quotes(11)
        matching = self._quote(
            20,
            product_line="Motion",
            product_line_name="HyperMotion",
        )
        self._quote(
            21,
            owner="other@example.com",
            product_line="Private",
            product_line_name="Private Line",
        )

        response = self.api.get(self.url)
        filtered = self.api.get(
            self.url,
            {"product_line_name": "HyperMotion"},
        )

        assert "HyperMotion" in response.data["facets"]["product_lines"]
        assert "Private Line" not in response.data["facets"]["product_lines"]
        assert [row["id"] for row in filtered.data["items"]] == [
            matching.id
        ]
        assert "HyperBDR" in filtered.data["facets"]["product_lines"]

    def test_product_line_facets_fall_back_to_legacy_prefix(self):
        legacy = self._quote(
            1,
            product_line="Legacy",
            product_line_name="",
        )

        response = self.api.get(self.url)
        filtered = self.api.get(
            self.url,
            {"product_line_name": "Legacy"},
        )

        assert "Legacy" in response.data["facets"]["product_lines"]
        assert [row["id"] for row in filtered.data["items"]] == [
            legacy.id
        ]

    def test_owner_permission_and_staff_visibility(self):
        own = self._quote(1)
        other = self._quote(
            2,
            owner="other@example.com",
            product_line="Private",
            product_line_name="Private Line",
        )
        imported = self._quote(
            3,
            owner="other@example.com",
            source_type=QuotationSourceType.DOCUMENT_IMPORT,
            product_line="Parsed",
            product_line_name="Parsed Line",
        )

        owner_response = self.api.get(self.url)
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        staff_response = self.api.get(self.url)

        assert "Private Line" not in owner_response.data["facets"][
            "product_lines"
        ]
        assert {row["id"] for row in owner_response.data["items"]} == {
            own.id,
            imported.id,
        }
        assert {row["id"] for row in staff_response.data["items"]} == {
            own.id,
            other.id,
            imported.id,
        }
        assert "Private Line" in staff_response.data["facets"][
            "product_lines"
        ]

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

    def test_imported_quote_lists_original_document_and_revision_summaries(
        self,
    ):
        quotation = self._quote(
            1,
            source_type=QuotationSourceType.DOCUMENT_IMPORT,
        )
        source = DocumentAsset.objects.create(
            quotation=quotation,
            doc_type="excel",
            file_name="Original quote.xlsx",
            mime_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            storage_key="documents/original/quote.xlsx",
            source="local",
            created_by_email=self.user.email,
        )
        DocumentParseResult.objects.create(
            asset=source,
            quotation=quotation,
            status=DocumentParseStatus.CONFIRMED,
            parser_name="test-parser",
            parser_version="1",
            content_hash="source-hash",
        )
        for version_no in (1, 2):
            QuotationVersion.objects.create(
                quotation=quotation,
                version_no=version_no,
                status=QuoteStatus.GENERATED,
                snapshot_json={"private": f"snapshot-{version_no}"},
            )

        response = self.api.get(self.url)

        assert response.status_code == 200
        row = response.data["items"][0]
        assert row["source_document_type"] == "excel"
        assert row["source_document"] == {
            "id": source.id,
            "doc_type": "excel",
            "file_name": "Original quote.xlsx",
            "version_no": 1,
        }
        assert [
            version["version_no"]
            for version in row["available_versions"]
        ] == [2, 1]
        assert all(
            "snapshot" not in version
            for version in row["available_versions"]
        )

    def test_imported_quote_ignores_unconfirmed_and_generated_documents(
        self,
    ):
        quotation = self._quote(
            1,
            source_type=QuotationSourceType.DOCUMENT_IMPORT,
        )
        for source, status in (
            ("local", DocumentParseStatus.READY),
            ("generated", DocumentParseStatus.CONFIRMED),
        ):
            asset = DocumentAsset.objects.create(
                quotation=quotation,
                doc_type="pdf",
                file_name=f"{source}.pdf",
                mime_type="application/pdf",
                storage_key=f"documents/{source}/quote.pdf",
                source=source,
                created_by_email=self.user.email,
            )
            DocumentParseResult.objects.create(
                asset=asset,
                quotation=quotation,
                status=status,
                parser_name="test-parser",
                parser_version="1",
                content_hash=f"{source}-hash",
            )

        response = self.api.get(self.url)

        row = response.data["items"][0]
        assert row["source_document_type"] is None
        assert row["source_document"] is None
        assert row["available_versions"] == []

    def test_detail_still_returns_items_versions_and_snapshots(self):
        quotation = self._quote(1, status=QuoteStatus.EXPIRED)
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
        assert response.data["status"] == QuoteStatus.EXPIRED

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
