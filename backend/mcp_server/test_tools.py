import asyncio
import hashlib
import json
import secrets
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from subprocess import TimeoutExpired
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pymupdf
from django.contrib.auth.models import User
from django.test import TransactionTestCase, override_settings
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from starlette.testclient import TestClient

from accounts.models import Role
from core.pdf_ocr import PdfOcrError
from invoice.models import (
    Invoice,
    InvoiceAccessGrant,
    InvoiceAccessRole,
    InvoiceDocument,
    InvoiceItem,
)
from mcp_server import server as mcp_server_tools
from mcp_server.models import McpDocumentPage, McpOAuthToken
from quotation import models as quotation_models


class McpToolIdentityTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.auth_context_token = auth_context_var.set(None)
        self.users = [
            User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
            )
            for username in ("mcp-alice", "mcp-bob")
        ]
        feature_role = Role.objects.create(
            name="MCP quotation access",
            visible_features=["quotation_management"],
        )
        for user in self.users:
            user.platform_roles.add(feature_role)
            quotation_models.QuotationMembership.objects.create(
                user=user,
                role=quotation_models.QuotationMembershipRole.USER,
            )
        self.quotes = [
            self._quotation("Q-MCP-ALICE", self.users[0]),
            self._quotation("Q-MCP-BOB", self.users[1]),
        ]
        grantor = User.objects.create_user(username="mcp-grantor")
        for user in self.users:
            InvoiceAccessGrant.objects.create(
                user=user,
                granted_by=grantor,
                role=InvoiceAccessRole.USER,
            )
            Invoice.objects.create(
                invoice_no=f"INV-{user.username}",
                sales_owner=user.username,
                customer_name="Client",
            )
        self.settings = override_settings(
            DEBUG=True,
            MCP_OAUTH_ISSUER_URL="http://localhost:8000/",
            MCP_OAUTH_RESOURCE_URL="http://localhost:8000/mcp",
            MCP_OAUTH_AUTHORIZATION_ENDPOINT_URL=(
                "http://localhost:8000/authorize"
            ),
            MCP_OAUTH_TOKEN_ENDPOINT_URL="http://localhost:8000/token",
            MCP_OAUTH_REGISTRATION_ENDPOINT_URL=(
                "http://localhost:8000/register"
            ),
            MCP_OAUTH_REVOCATION_ENDPOINT_URL=(
                "http://localhost:8000/revoke"
            ),
            MCP_OAUTH_CONSENT_URL="http://localhost:8000/oauth/mcp/authorize",
            MCP_OAUTH_SCOPES=["mcp:read"],
            MCP_ALLOWED_HOSTS=["localhost:8000"],
        )
        self.settings.enable()

    def tearDown(self):
        self.settings.disable()
        auth_context_var.reset(self.auth_context_token)

    def _user_for_subject(self, subject):
        if isinstance(subject, User):
            return subject
        return self.users[1] if subject == "user-b" else self.users[0]

    def _context(self, subject="user-a"):
        user = self._user_for_subject(subject)
        token = AccessToken(
            token="test-token",
            client_id="test-client",
            scopes=["mcp:read"],
            resource="http://localhost:8000/mcp",
            subject=str(user.pk),
        )
        auth_context_var.set(AuthenticatedUser(token))
        return SimpleNamespace(headers={})

    def _bearer_token(self, subject="user-a"):
        user = self._user_for_subject(subject)
        token = secrets.token_urlsafe(32)
        McpOAuthToken.objects.create(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            family_id=uuid4(),
            token_type=McpOAuthToken.ACCESS,
            client_id="test-client",
            user=user,
            scopes=["mcp:read"],
            resource="http://localhost:8000/mcp",
            issuer="http://localhost:8000/",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        return token

    def _quotation(
        self,
        quote_no,
        user,
        quote_date="2026-08-01",
        expire_date="2026-09-01",
        client_company="Client",
    ):
        return quotation_models.Quotation.objects.create(
            quote_no=quote_no,
            source_type="manual",
            project_name=quote_no,
            currency="USD",
            payment_terms="CIA",
            quote_date=quote_date,
            expire_date=expire_date,
            issuer_contact_name=user.username,
            issuer_contact_email=user.email,
            client_company=client_company,
            contact_person="Contact",
            email="client@example.com",
            created_by_email=user.email,
        )

    def _search_quotations(self, query, *, limit=10, subject="user-a"):
        return self._search_quotation_page(
            query,
            limit=limit,
            subject=subject,
        )["results"]

    def _search_quotation_page(
        self,
        query,
        *,
        limit=10,
        offset=0,
        salesperson="",
        subject="user-a",
    ):
        context = self._context(subject)
        return json.loads(
            mcp_server_tools.search_quotations(
                query=query,
                limit=limit,
                offset=offset,
                salesperson=salesperson,
                ctx=context,
            )
        )

    def _invoice(self, invoice_no, user, *, invoice_date=None, **fields):
        return Invoice.objects.create(
            invoice_no=invoice_no,
            invoice_date=invoice_date,
            sales_owner=fields.pop("sales_owner", user.username),
            customer_name=fields.pop("customer_name", "Client"),
            **fields,
        )

    def _search_invoice_page(
        self,
        query,
        *,
        limit=10,
        offset=0,
        salesperson="",
        subject="user-a",
        summary=False,
    ):
        context = self._context(subject)
        return json.loads(
            mcp_server_tools.search_invoices(
                query=query,
                limit=limit,
                offset=offset,
                salesperson=salesperson,
                summary=summary,
                ctx=context,
            )
        )

    def _pdf_asset(self, quote, **fields):
        return quotation_models.DocumentAsset.objects.create(
            quotation=quote,
            doc_type=quotation_models.DocumentType.PDF,
            file_name=f"{quote.quote_no}.pdf",
            mime_type="application/pdf",
            storage_key=f"test/{quote.id}.pdf",
            content_hash="a" * 64,
            **fields,
        )

    def test_missing_pdf_marks_search_incomplete_without_leaking_other_user(
        self,
    ):
        visible = self._pdf_asset(self.quotes[0])
        hidden = self._pdf_asset(self.quotes[1])
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "quotation.services.storage.resolve_document_path",
                return_value=Path(directory) / "missing.pdf",
            ) as resolve:
                result = json.loads(
                    mcp_server_tools.search_pdf_content(
                        "keyword", "quotations", ctx=self._context()
                    )
                )
        resolve.assert_called_once_with(visible.storage_key)
        self.assertEqual(result["results"], [])
        self.assertFalse(result["search_complete"])
        self.assertEqual(result["document_count"], 1)
        self.assertEqual(result["unavailable_document_count"], 1)
        self.assertEqual(
            result["unavailable_documents"][0]["reason"], "file_missing"
        )
        self.assertNotIn(hidden.pk, json.dumps(result))

    def test_partial_pdf_search_keeps_valid_matches(self):
        cached = self._pdf_asset(self.quotes[0])
        quote = self._quotation("Q-MISSING", self.users[0])
        self._pdf_asset(quote)
        McpDocumentPage.objects.create(
            quotation_asset=cached,
            content_hash=cached.content_hash,
            page_number=1,
            text="keyword remains searchable",
        )
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "quotation.services.storage.resolve_document_path",
                return_value=Path(directory) / "missing.pdf",
            ):
                result = json.loads(
                    mcp_server_tools.search_pdf_content(
                        "keyword", "quotations", ctx=self._context()
                    )
                )
        self.assertFalse(result["search_complete"])
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["document_id"], cached.pk)

    def test_pdf_extraction_failures_are_reported(self):
        self._pdf_asset(self.quotes[0])
        cases = (
            (PdfOcrError("unreadable scan"), "ocr_failed"),
            (TimeoutExpired("tesseract", 30), "ocr_timeout"),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scan.pdf"
            with pymupdf.open() as pdf:
                pdf.new_page()
                pdf.save(path)
            for error, reason in cases:
                with self.subTest(reason=reason):
                    with patch(
                        "quotation.services.storage.resolve_document_path",
                        return_value=path,
                    ), patch.object(
                        mcp_server_tools,
                        "extract_pdf_text_with_ocr",
                        side_effect=error,
                    ):
                        result = json.loads(
                            mcp_server_tools.search_pdf_content(
                                "keyword",
                                "quotations",
                                ctx=self._context(),
                            )
                        )
                    self.assertFalse(result["search_complete"])
                    self.assertEqual(
                        result["unavailable_documents"][0]["reason"], reason
                    )

    def test_unreadable_pdf_reports_partial_search(self):
        self._pdf_asset(self.quotes[0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.pdf"
            path.write_bytes(b"not a pdf")
            with patch(
                "quotation.services.storage.resolve_document_path",
                return_value=path,
            ):
                result = json.loads(
                    mcp_server_tools.search_pdf_content(
                        "keyword", "quotations", ctx=self._context()
                    )
                )
        self.assertFalse(result["search_complete"])
        self.assertEqual(
            result["unavailable_documents"][0]["reason"], "pdf_unreadable"
        )

    def test_missing_invoice_pdf_marks_search_incomplete(self):
        invoice = Invoice.objects.get(invoice_no="INV-mcp-alice")
        document = InvoiceDocument.objects.create(
            invoice=invoice,
            file_name="missing.pdf",
            storage_key="missing.pdf",
            document_type="pdf",
            status="active",
        )
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(INVOICE_STORAGE=directory):
                result = json.loads(
                    mcp_server_tools.search_pdf_content(
                        "keyword", "invoices", ctx=self._context()
                    )
                )
        self.assertFalse(result["search_complete"])
        self.assertEqual(
            result["unavailable_documents"][0]["document_id"], document.pk
        )
        self.assertEqual(
            result["unavailable_documents"][0]["reason"], "file_missing"
        )

    def test_pdf_search_returns_authorized_quotation_pages(self):
        assets = []
        for quote in self.quotes:
            asset = quotation_models.DocumentAsset.objects.create(
                quotation=quote,
                doc_type=quotation_models.DocumentType.PDF,
                file_name=f"{quote.quote_no}.pdf",
                mime_type="application/pdf",
                storage_key=f"test/{quote.id}.pdf",
                content_hash="a" * 64,
            )
            McpDocumentPage.objects.create(
                quotation_asset=asset,
                content_hash=asset.content_hash,
                page_number=2,
                text="Authorized quotation contains searchablekeyword.",
            )
            assets.append(asset)

        for document_type in ("quotations", "all"):
            with self.subTest(document_type=document_type):
                result = json.loads(
                    mcp_server_tools.search_pdf_content(
                        query="searchablekeyword",
                        document_type=document_type,
                        ctx=self._context(),
                    )
                )
                self.assertEqual(len(result["results"]), 1)
                hit = result["results"][0]
                self.assertEqual(hit["document_id"], assets[0].pk)
                self.assertEqual(hit["record_id"], self.quotes[0].pk)
                self.assertEqual(hit["page"], 2)
                self.assertIn("searchablekeyword", hit["snippet"])
                self.assertTrue(result["search_complete"])

    def test_first_pdf_search_indexes_only_authorized_quotation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quotation.pdf"
            with pymupdf.open() as pdf:
                pdf.new_page().insert_text((72, 72), "searchablekeyword")
                pdf.save(path)
            assets = [
                quotation_models.DocumentAsset.objects.create(
                    quotation=quote,
                    doc_type=quotation_models.DocumentType.PDF,
                    file_name=f"{quote.quote_no}.pdf",
                    mime_type="application/pdf",
                    storage_key=f"test/{quote.id}.pdf",
                    content_hash="b" * 64,
                )
                for quote in self.quotes
            ]
            with patch(
                "quotation.services.storage.resolve_document_path",
                return_value=path,
            ) as resolve:
                result = json.loads(
                    mcp_server_tools.search_pdf_content(
                        query="searchablekeyword",
                        document_type="quotations",
                        ctx=self._context(),
                    )
                )
            resolve.assert_called_once_with(assets[0].storage_key)
            self.assertEqual(len(result["results"]), 1)
            self.assertTrue(result["search_complete"])
            self.assertEqual(
                result["results"][0]["document_id"], assets[0].pk
            )
            self.assertFalse(
                McpDocumentPage.objects.filter(
                    quotation_asset=assets[1]
                ).exists()
            )

    def test_quotation_search_accepts_chinese_and_numeric_dates(self):
        quote = self._quotation(
            "BDR280926.2",
            self.users[0],
            quote_date="2026-09-28",
        )

        for query in (
            "9月28日",
            "2026年9月28日",
            "2026-09-28",
            "2026/09/28",
            "28/09/2026",
        ):
            with self.subTest(query=query):
                results = self._search_quotations(query)
                self.assertIn(
                    quote.quote_no, [item["quote_no"] for item in results]
                )

    def test_quotation_search_accepts_english_and_spanish_dates(self):
        quote = self._quotation(
            "BDR280926.3",
            self.users[0],
            quote_date="2026-09-28",
        )

        for query in (
            "September 28, 2026",
            "Sep 28 2026",
            "28 September 2026",
            "28th September 2026",
            "28 de septiembre de 2026",
            "28 de setiembre de 2026",
            "28 sept. 2026",
            "September 28",
            "28 September",
            "28 de septiembre",
        ):
            with self.subTest(query=query):
                results = self._search_quotations(query)
                self.assertIn(
                    quote.quote_no,
                    [item["quote_no"] for item in results],
                )

    def test_english_and_spanish_month_names_and_customer_filters(self):
        acme = self._quotation(
            "Q-ACME-AUG-2025",
            self.users[0],
            quote_date="2025-08-10",
            client_company="Acme",
        )
        self._quotation(
            "Q-OTHER-AUG-2025",
            self.users[0],
            quote_date="2025-08-11",
            client_company="Other",
        )

        for query in (
            "August 2025",
            "Aug 2025",
            "August of 2025",
            "agosto de 2025",
            "agosto del 2025",
            "ago 2025",
            "2025 agosto",
            "How many quotations are there in August 2025",
            "¿Cuántas cotizaciones hay en agosto de 2025?",
            "Show all quotations for Acme in August 2025",
            "Muéstrame todas las cotizaciones de Acme en agosto de 2025",
        ):
            with self.subTest(query=query):
                results = self._search_quotations(query)
                numbers = [item["quote_no"] for item in results]
                if "Acme" in query:
                    self.assertEqual(numbers, [acme.quote_no])
                else:
                    self.assertCountEqual(
                        numbers,
                        [acme.quote_no, "Q-OTHER-AUG-2025"],
                    )

    def test_yearless_date_matches_all_years_newest_first(self):
        older = self._quotation(
            "BDR280925.1",
            self.users[0],
            quote_date="2025-09-28",
        )
        newer = self._quotation(
            "BDR280926.1",
            self.users[0],
            quote_date="2026-09-28",
        )

        results = self._search_quotations("9月28日")

        self.assertEqual(
            [item["quote_no"] for item in results[:2]],
            [newer.quote_no, older.quote_no],
        )

    def test_quotation_month_formats_filter_left_closed_range(self):
        first = self._quotation(
            "Q-AUG-FIRST",
            self.users[0],
            quote_date="2026-08-01",
        )
        last = self._quotation(
            "Q-AUG-LAST",
            self.users[0],
            quote_date="2026-08-31",
        )
        before = self._quotation(
            "Q-JUL-LAST",
            self.users[0],
            quote_date="2026-07-31",
        )
        after = self._quotation(
            "Q-SEP-FIRST",
            self.users[0],
            quote_date="2026-09-01",
        )

        for query in (
            "2026-08",
            "2026-8",
            "2026/08",
            "2026年8月",
            "2026年08月",
            "2026年8月份",
            "查询 2026 年 8 月的所有报价单",
        ):
            with self.subTest(query=query):
                response = json.loads(
                    mcp_server_tools.search_quotations(
                        query=query,
                        limit=20,
                        ctx=self._context("user-a"),
                    )
                )
                numbers = [item["quote_no"] for item in response["results"]]
                self.assertIn(first.quote_no, numbers)
                self.assertIn(last.quote_no, numbers)
                self.assertNotIn(before.quote_no, numbers)
                self.assertNotIn(after.quote_no, numbers)

    def test_month_query_combines_date_range_with_customer_filter(self):
        acme = self._quotation(
            "Q-ACME-AUG",
            self.users[0],
            quote_date="2026-08-10",
            client_company="Acme",
        )
        other = self._quotation(
            "Q-OTHER-AUG",
            self.users[0],
            quote_date="2026-08-11",
            client_company="Other",
        )

        results = self._search_quotations("查询2026年8月Acme的所有报价单")

        self.assertEqual(
            [item["quote_no"] for item in results], [acme.quote_no]
        )
        self.assertNotIn(
            other.quote_no, [item["quote_no"] for item in results]
        )

    def test_natural_language_month_query_ignores_filler_words(self):
        quote = self._quotation(
            "Motion080825",
            self.users[0],
            quote_date="2025-08-08",
        )

        response = self._search_quotation_page("查询一下2025年8月份的报价单")

        self.assertEqual(response["total"], 1)
        self.assertEqual(
            [item["quote_no"] for item in response["results"]],
            [quote.quote_no],
        )

    def test_month_query_handles_year_boundary_invalid_month_and_leap_day(
        self,
    ):
        december = self._quotation(
            "Q-DEC-LAST",
            self.users[0],
            quote_date="2026-12-31",
        )
        january = self._quotation(
            "Q-JAN-NEXT",
            self.users[0],
            quote_date="2027-01-01",
        )
        leap_day = self._quotation(
            "Q-LEAP-DAY",
            self.users[0],
            quote_date="2024-02-29",
        )
        march = self._quotation(
            "Q-MARCH-FIRST",
            self.users[0],
            quote_date="2024-03-01",
        )

        december_results = self._search_quotations("2026-12")
        february_results = self._search_quotations("2024年2月")
        invalid_results = self._search_quotation_page("2026-13")

        self.assertEqual(
            [item["quote_no"] for item in december_results],
            [december.quote_no],
        )
        self.assertNotIn(
            january.quote_no, [item["quote_no"] for item in december_results]
        )
        self.assertEqual(
            [item["quote_no"] for item in february_results],
            [leap_day.quote_no],
        )
        self.assertNotIn(
            march.quote_no, [item["quote_no"] for item in february_results]
        )
        self.assertEqual(invalid_results["results"], [])
        self.assertEqual(invalid_results["total"], 0)

    def test_month_query_pagination_returns_every_record_once_in_stable_order(
        self,
    ):
        expected = []
        for index in range(45):
            quote_date = date(2026, 8, 1 + index % 31)
            quote = self._quotation(
                f"Q-AUG-PAGE-{index:02d}",
                self.users[0],
                quote_date=quote_date.isoformat(),
                client_company="PageClient",
            )
            expected.append(quote)

        pages = [
            self._search_quotation_page(
                "2026-08 PageClient",
                limit=20,
                offset=offset,
            )
            for offset in (0, 20, 40)
        ]
        numbers = [
            item["quote_no"] for page in pages for item in page["results"]
        ]

        self.assertTrue(all(page["total"] == 45 for page in pages))
        self.assertEqual(
            [page["has_more"] for page in pages], [True, True, False]
        )
        self.assertEqual([page["offset"] for page in pages], [0, 20, 40])
        self.assertEqual(len(numbers), 45)
        self.assertEqual(len(set(numbers)), 45)
        self.assertEqual(set(numbers), {quote.quote_no for quote in expected})
        result_dates = [
            item["quote_date"] for page in pages for item in page["results"]
        ]
        self.assertEqual(result_dates, sorted(result_dates, reverse=True))

    def test_month_search_still_applies_user_access_filter(self):
        visible = self._quotation(
            "Q-MONTH-ALICE",
            self.users[0],
            quote_date="2026-08-28",
        )
        hidden = self._quotation(
            "Q-MONTH-BOB",
            self.users[1],
            quote_date="2026-08-28",
        )

        results = self._search_quotations("2026-08")
        numbers = [item["quote_no"] for item in results]

        self.assertIn(visible.quote_no, numbers)
        self.assertNotIn(hidden.quote_no, numbers)

    def test_quote_number_date_is_only_fallback_when_quote_date_is_missing(
        self,
    ):
        dated = self._quotation(
            "BDR280926.2",
            self.users[0],
            quote_date="2026-09-27",
        )
        undated = self._quotation(
            "BDR280926.1",
            self.users[0],
            quote_date=None,
        )
        other_product_line = self._quotation(
            "MOTION280926_R1",
            self.users[0],
            quote_date=None,
        )

        results = self._search_quotations("2026-09-28")
        result_numbers = [item["quote_no"] for item in results]

        self.assertIn(undated.quote_no, result_numbers)
        self.assertIn(other_product_line.quote_no, result_numbers)
        self.assertNotIn(dated.quote_no, result_numbers)
        self.assertIsNone(
            next(
                item["quote_date"]
                for item in results
                if item["quote_no"] == undated.quote_no
            )
        )

    def test_expiry_date_does_not_count_as_quotation_date(self):
        expiring = self._quotation(
            "Q-EXPIRY-ONLY",
            self.users[0],
            quote_date="2026-09-27",
            expire_date="2026-09-28",
        )

        results = self._search_quotations("9月28日")

        self.assertNotIn(
            expiring.quote_no, [item["quote_no"] for item in results]
        )

    def test_date_search_still_filters_inaccessible_quotations(self):
        visible = self._quotation(
            "BDR280926.2",
            self.users[0],
            quote_date="2026-09-28",
        )
        hidden = self._quotation(
            "BDR280926.1",
            self.users[1],
            quote_date="2026-09-28",
        )

        results = self._search_quotations("9月28日")
        result_numbers = [item["quote_no"] for item in results]

        self.assertIn(visible.quote_no, result_numbers)
        self.assertNotIn(hidden.quote_no, result_numbers)

    def test_empty_keyword_and_limit_search_behaviors_remain(self):
        empty_results = self._search_quotations("", limit=10)
        keyword_results = self._search_quotations("Q-MCP-ALICE")
        limited_results = self._search_quotations("", limit=1)
        capped_page = self._search_quotation_page("", limit=100, offset=-1)

        self.assertIn(
            "Q-MCP-ALICE", [item["quote_no"] for item in empty_results]
        )
        self.assertEqual(
            [item["quote_no"] for item in keyword_results],
            ["Q-MCP-ALICE"],
        )
        self.assertEqual(len(limited_results), 1)
        self.assertEqual(capped_page["limit"], 20)
        self.assertEqual(capped_page["offset"], 0)

    def test_quotation_salesperson_filter_is_exact_and_combines_filters(self):
        first = self._quotation(
            "Q-SALES-ALICE-1",
            self.users[0],
            quote_date="2025-09-10",
            client_company="Huawei International",
        )
        second = self._quotation(
            "Q-SALES-ALICE-2",
            self.users[0],
            quote_date="2025-09-20",
            client_company="Huawei International",
        )
        wrong_client = self._quotation(
            "Q-SALES-ALICE-3",
            self.users[0],
            quote_date="2025-09-21",
            client_company="Other Client",
        )
        quotation_models.Quotation.objects.filter(
            pk__in=[first.pk, second.pk, wrong_client.pk]
        ).update(issuer_contact_name="Carrol Yu")

        page = self._search_quotation_page(
            "2025-09 Huawei International",
            limit=1,
            salesperson="  cARROL yU  ",
        )
        next_page = self._search_quotation_page(
            "2025-09 Huawei International",
            limit=1,
            offset=1,
            salesperson="Carrol Yu",
        )
        partial_name = self._search_quotation_page(
            "",
            salesperson="Carrol",
        )
        bob_view = self._search_quotation_page(
            "",
            salesperson="Carrol Yu",
            subject="user-b",
        )

        self.assertEqual(page["total"], 2)
        self.assertTrue(page["has_more"])
        self.assertFalse(next_page["has_more"])
        self.assertEqual(
            {page["results"][0]["quote_no"],
             next_page["results"][0]["quote_no"]},
            {first.quote_no, second.quote_no},
        )
        self.assertEqual(partial_name["total"], 0)
        self.assertEqual(bob_view["total"], 0)

    def test_quotation_search_returns_summary_and_detail_tool_returns_full_data(
        self,
    ):
        quote = self.quotes[0]
        summary = self._search_quotations(quote.quote_no)[0]
        context = self._context("user-a")
        details = json.loads(
            mcp_server_tools.get_quotation(
                quotation_id=str(quote.pk),
                ctx=context,
            )
        )

        self.assertEqual(summary["id"], quote.pk)
        self.assertEqual(summary["quote_no"], quote.quote_no)
        self.assertEqual(summary["client_company"], quote.client_company)
        self.assertNotIn("items", summary)
        self.assertNotIn("issuer_contact_email", summary)
        self.assertIn("issuer_contact_email", details)
        self.assertIn("items", details)

    def test_tool_acl_uses_authorized_user_not_supplied_user_id(self):
        alice_context = self._context("user-a")
        result = mcp_server_tools.search_quotations(
            query="",
            limit=10,
            ctx=alice_context,
        )

        self.assertIn("Q-MCP-ALICE", result)
        self.assertNotIn("Q-MCP-BOB", result)

    def test_invoice_acl_uses_the_authorized_user_too(self):
        context = self._context("user-a")
        result = mcp_server_tools.search_invoices(
            query="", limit=10, ctx=context
        )

        self.assertIn("INV-mcp-alice", result)
        self.assertNotIn("INV-mcp-bob", result)

    def test_invoice_handler_and_sales_owner_queries_are_equivalent(self):
        handler_invoice = self._invoice(
            "INV-HANDLER-2025",
            self.users[0],
            invoice_date=date(2025, 7, 15),
            contact_person=self.users[0].username,
        )
        handler_invoice.sales_owner = ""
        handler_invoice.save(update_fields=["sales_owner"])
        owner_invoice = self._invoice(
            "INV-OWNER-2025",
            self.users[0],
            invoice_date=date(2025, 7, 16),
            contact_person="",
        )
        self._invoice(
            "INV-OTHER-2025",
            self.users[1],
            invoice_date=date(2025, 7, 17),
            contact_person=self.users[1].username,
        )
        Invoice.objects.filter(invoice_no="INV-OTHER-2025").update(
            sales_owner=""
        )
        self._invoice(
            "INV-HANDLER-2024",
            self.users[0],
            invoice_date=date(2024, 7, 15),
            contact_person=self.users[0].username,
        )
        Invoice.objects.filter(invoice_no="INV-HANDLER-2024").update(
            sales_owner=""
        )

        by_handler = self._search_invoice_page(
            "查询票据经办人为mcp-alice的2025年票据"
        )
        by_owner = self._search_invoice_page(
            "查询票据负责人为mcp-alice的2025年票据"
        )
        by_salesperson = self._search_invoice_page(
            "2025年", salesperson="  MCP-ALICE  "
        )
        expected = {handler_invoice.invoice_no, owner_invoice.invoice_no}

        def all_invoice_numbers(query, first_page, salesperson=""):
            numbers = {
                item["invoice_no"] for item in first_page["results"]
            }
            offset = first_page["limit"]
            page = first_page
            while page["has_more"]:
                page = self._search_invoice_page(
                    query, offset=offset, salesperson=salesperson
                )
                numbers.update(item["invoice_no"] for item in page["results"])
                offset += page["limit"]
            return numbers

        self.assertEqual(by_handler["total"], 2)
        self.assertEqual(by_owner["total"], 2)
        self.assertEqual(by_salesperson["total"], 2)
        self.assertTrue(by_salesperson["responsibility_fields_equivalent"])
        self.assertEqual(
            all_invoice_numbers(
                "2025年", by_salesperson, salesperson="mcp-alice"
            ),
            expected,
        )
        self.assertEqual(
            all_invoice_numbers(
                "查询票据经办人为mcp-alice的2025年票据", by_handler
            ),
            expected,
        )
        self.assertEqual(
            all_invoice_numbers(
                "查询票据负责人为mcp-alice的2025年票据", by_owner
            ),
            expected,
        )

    def test_invoice_month_formats_and_left_closed_date_range(self):
        july = self._invoice(
            "INV-JULY-2025",
            self.users[0],
            invoice_date=date(2025, 7, 15),
        )
        june = self._invoice(
            "INV-JUNE-2025",
            self.users[0],
            invoice_date=date(2025, 6, 30),
        )
        august = self._invoice(
            "INV-AUGUST-2025",
            self.users[0],
            invoice_date=date(2025, 8, 1),
        )

        for query in (
            "2025年7月",
            "2025年07月",
            "2025年7月份",
            "2025-07",
            "2025-7",
            "2025/07",
        ):
            with self.subTest(query=query):
                response = self._search_invoice_page(query)
                numbers = [item["invoice_no"] for item in response["results"]]
                self.assertEqual(response["total"], 1)
                self.assertIn(july.invoice_no, numbers)
                self.assertNotIn(june.invoice_no, numbers)
                self.assertNotIn(august.invoice_no, numbers)

    def test_invoice_exact_date_and_leap_day(self):
        target = self._invoice(
            "INV-2024-LEAP",
            self.users[0],
            invoice_date=date(2024, 2, 29),
        )
        other_day = self._invoice(
            "INV-2024-MARCH",
            self.users[0],
            invoice_date=date(2024, 3, 1),
        )

        for query in (
            "2024年2月29日",
            "2024-02-29",
            "2024/02/29",
        ):
            with self.subTest(query=query):
                response = self._search_invoice_page(query)
                self.assertEqual(response["total"], 1)
                self.assertEqual(
                    [item["invoice_no"] for item in response["results"]],
                    [target.invoice_no],
                )

        self.assertNotIn(
            other_day.invoice_no,
            [
                item["invoice_no"]
                for item in self._search_invoice_page("2024-02-29")["results"]
            ],
        )
        february = self._search_invoice_page("2024-02")
        self.assertEqual(
            [item["invoice_no"] for item in february["results"]],
            [target.invoice_no],
        )
        self.assertEqual(
            self._search_invoice_page("2025-02-29")["total"],
            0,
        )
        self.assertEqual(
            self._search_invoice_page("2025-07-32")["total"],
            0,
        )

    def test_invoice_december_month_range_crosses_year_boundary(self):
        december = self._invoice(
            "INV-DECEMBER-2025",
            self.users[0],
            invoice_date=date(2025, 12, 31),
        )
        january = self._invoice(
            "INV-JANUARY-2026",
            self.users[0],
            invoice_date=date(2026, 1, 1),
        )

        response = self._search_invoice_page("2025-12")
        numbers = [item["invoice_no"] for item in response["results"]]

        self.assertIn(december.invoice_no, numbers)
        self.assertNotIn(january.invoice_no, numbers)

    def test_invoice_invalid_month_and_due_date_only_do_not_match(self):
        due_date_only = self._invoice(
            "INV-DUE-DATE-ONLY",
            self.users[0],
            invoice_date=None,
            due_date=date(2025, 7, 15),
        )

        for query in ("2025年13月", "2025-13", "2025年7月15日"):
            with self.subTest(query=query):
                response = self._search_invoice_page(query)
                self.assertEqual(response["results"], [])
                self.assertEqual(response["total"], 0)
        self.assertIsNotNone(due_date_only.pk)

    def test_invoice_date_query_combines_with_customer_and_invoice_terms(
        self,
    ):
        acme = self._invoice(
            "INV-ACME-JULY",
            self.users[0],
            invoice_date=date(2025, 7, 8),
            customer_name="Acme",
        )
        other_customer = self._invoice(
            "INV-OTHER-JULY",
            self.users[0],
            invoice_date=date(2025, 7, 9),
            customer_name="Other",
        )
        other_month = self._invoice(
            "INV-ACME-JUNE",
            self.users[0],
            invoice_date=date(2025, 6, 8),
            customer_name="Acme",
        )

        for query in (
            "查询2025年7月Acme的所有发票",
            "2025-07 Acme invoice",
            "busca facturas de Acme en 2025-07",
        ):
            with self.subTest(query=query):
                response = self._search_invoice_page(query)
                self.assertEqual(
                    [item["invoice_no"] for item in response["results"]],
                    [acme.invoice_no],
                )
        self.assertNotEqual(acme.invoice_no, other_customer.invoice_no)
        self.assertNotEqual(acme.invoice_no, other_month.invoice_no)

    def test_invoice_summary_pagination_is_compact_and_authorized(self):
        expected = {
            self._invoice(
                f"INV-SUMMARY-{index:02d}",
                self.users[0],
                invoice_date=date(2025, 7, 1),
            ).invoice_no
            for index in range(25)
        }
        hidden = self._invoice(
            "INV-SUMMARY-HIDDEN",
            self.users[1],
            invoice_date=date(2025, 7, 1),
        )
        first = self._search_invoice_page(
            "2025年7月", limit=100, summary=True
        )
        second = self._search_invoice_page(
            "2025年7月", limit=20, offset=20, summary=True
        )
        self.assertEqual(first["total"], 25)
        self.assertEqual(first["limit"], 20)
        self.assertEqual(len(first["results"]), 20)
        self.assertTrue(first["has_more"])
        self.assertEqual(len(second["results"]), 5)
        self.assertFalse(second["has_more"])
        numbers = {
            item["invoice_no"]
            for item in first["results"] + second["results"]
        }
        self.assertEqual(numbers, expected)
        self.assertNotIn(hidden.invoice_no, numbers)
        self.assertNotIn("items", first["results"][0])
        self.assertNotIn("bank_account_number", first["results"][0])
        self.assertEqual(
            first["query_context"]["date_filter"],
            {
                "type": "month",
                "start": "2025-07-01",
                "end_exclusive": "2025-08-01",
            },
        )

    def test_invoice_summary_keeps_detail_tool_and_legacy_response(self):
        invoice = self._invoice(
            "INV-SUMMARY-DETAIL",
            self.users[0],
            invoice_date=date(2025, 7, 1),
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            line_no=1,
            product_name="License",
            quantity=2,
            unit_price=100,
            total_amount=200,
        )
        summary = self._search_invoice_page(
            "2025年7月", summary=True
        )
        legacy = self._search_invoice_page("2025年7月")
        self.assertNotIn("items", summary["results"][0])
        self.assertEqual(legacy["limit"], 1)
        self.assertEqual(
            legacy["results"][0]["items"][0]["product_name"], "License"
        )
        detail = json.loads(
            mcp_server_tools.get_invoice(
                invoice.pk, ctx=self._context()
            )
        )
        self.assertEqual(detail["items"], legacy["results"][0]["items"])

    def test_empty_search_describes_applied_date_and_visibility(self):
        for query in ("2025年7月", "2025-07", "July 2025"):
            with self.subTest(query=query):
                response = self._search_invoice_page(query, summary=True)
                self.assertEqual(response["total"], 0)
                self.assertEqual(response["result_status"], "complete")
                self.assertEqual(
                    response["query_context"]["visibility_scope"],
                    "authorized_user",
                )
                self.assertEqual(
                    response["query_context"]["date_filter"]["start"],
                    "2025-07-01",
                )
        quote_page = self._search_quotation_page("2025年7月")
        self.assertEqual(quote_page["result_status"], "complete")
        self.assertEqual(
            quote_page["query_context"]["date_filter"]["start"],
            "2025-07-01",
        )
        invalid = self._search_invoice_page("2025年13月", summary=True)
        self.assertEqual(invalid["result_status"], "invalid_date")

    def test_invoice_month_pagination_returns_every_record_once(self):
        expected = {
            self._invoice(
                f"INV-JULY-PAGE-{index:02d}",
                self.users[0],
                invoice_date=date(2025, 7, index % 28 + 1),
            ).invoice_no
            for index in range(45)
        }

        pages = []
        offset = 0
        while True:
            page = self._search_invoice_page(
                "2025年7月",
                limit=20,
                offset=offset,
            )
            pages.append(page)
            if not page["has_more"]:
                break
            offset += page["limit"]
        numbers = [
            item["invoice_no"] for page in pages for item in page["results"]
        ]

        self.assertTrue(all(page["total"] == 45 for page in pages))
        self.assertTrue(all(page["has_more"] for page in pages[:-1]))
        self.assertFalse(pages[-1]["has_more"])
        self.assertEqual([page["offset"] for page in pages], list(range(45)))
        self.assertEqual(len(numbers), 45)
        self.assertEqual(len(set(numbers)), 45)
        self.assertEqual(set(numbers), expected)
        self.assertTrue(all("items" in item for item in pages[0]["results"]))

    def test_invoice_permissions_and_empty_results_remain_distinct(self):
        visible = self._invoice(
            "INV-ALICE-JULY",
            self.users[0],
            invoice_date=date(2025, 7, 3),
        )
        hidden = self._invoice(
            "INV-BOB-JULY",
            self.users[1],
            invoice_date=date(2025, 7, 4),
        )
        denied_user = User.objects.create_user("mcp-no-invoice")
        allowed = self._search_invoice_page("2025年7月")
        denied = self._search_invoice_page(
            "2025年7月",
            subject=denied_user,
        )
        empty = self._search_invoice_page("2040年7月")

        allowed_numbers = [item["invoice_no"] for item in allowed["results"]]
        self.assertIn(visible.invoice_no, allowed_numbers)
        self.assertNotIn(hidden.invoice_no, allowed_numbers)
        self.assertIn("error", denied)
        self.assertNotIn("total", denied)
        self.assertEqual(empty["total"], 0)
        self.assertNotIn("error", empty)

    def test_invoice_keyword_search_compatibility_and_page_limit(self):
        invoice_no_results = self._search_invoice_page("INV-mcp-alice")
        customer_results = self._search_invoice_page("Client")
        capped = self._search_invoice_page("", limit=100, offset=-1)

        self.assertEqual(invoice_no_results["total"], 1)
        self.assertEqual(
            invoice_no_results["results"][0]["invoice_no"],
            "INV-mcp-alice",
        )
        self.assertEqual(customer_results["total"], 1)
        self.assertEqual(capped["limit"], 1)
        self.assertEqual(capped["offset"], 0)

    def test_invoice_salesperson_filter_is_exact_and_combines_filters(self):
        first = self._invoice(
            "INV-SALES-ALICE-1",
            self.users[0],
            invoice_date=date(2025, 7, 10),
            sales_owner="",
            contact_person="Carrol Yu",
            created_by=self.users[0],
        )
        second = self._invoice(
            "INV-SALES-ALICE-2",
            self.users[0],
            invoice_date=date(2025, 7, 20),
            sales_owner="Carrol Yu",
            contact_person="Carrol Yu",
            created_by=self.users[0],
        )
        _wrong_owner = self._invoice(
            "INV-SALES-ALICE-3",
            self.users[0],
            invoice_date=date(2025, 7, 21),
            sales_owner="Carol Yu",
            created_by=self.users[0],
        )

        page = self._search_invoice_page(
            "2025年7月 Client",
            salesperson="  cARROL yU  ",
        )
        next_page = self._search_invoice_page(
            "2025年7月 Client",
            offset=1,
            salesperson="Carrol Yu",
        )
        other_user = self._search_invoice_page(
            "2025年7月",
            salesperson="Carrol Yu",
            subject="user-b",
        )
        partial_name = self._search_invoice_page(
            "2025年7月", salesperson="Carrol"
        )
        other_month = self._search_invoice_page(
            "2025年8月", salesperson="Carrol Yu"
        )

        self.assertEqual(page["total"], 2)
        self.assertTrue(page["has_more"])
        self.assertFalse(next_page["has_more"])
        self.assertEqual(
            {page["results"][0]["invoice_no"],
             next_page["results"][0]["invoice_no"]},
            {first.invoice_no, second.invoice_no},
        )
        self.assertEqual(other_user["total"], 0)
        self.assertEqual(partial_name["total"], 0)
        self.assertEqual(other_month["total"], 0)

    def test_tools_list_exposes_salesperson_filter_for_both_search_tools(self):
        app = mcp_server_tools.build_asgi_app()
        request = {
            "jsonrpc": "2.0",
            "id": "tools-list-salesperson",
            "method": "tools/list",
        }

        with TestClient(app, base_url="http://localhost:8000") as client:
            response = client.post(
                "/mcp",
                json=request,
                headers={
                    "accept": "application/json, text/event-stream",
                    "host": "localhost:8000",
                    "authorization": f"Bearer {self._bearer_token()}",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        event = json.loads(response.text.split("data: ", 1)[1])
        tools = {
            tool["name"]: tool for tool in event["result"]["tools"]
        }
        for name in ("search_quotations", "search_invoices"):
            with self.subTest(tool=name):
                self.assertIn(
                    "salesperson",
                    tools[name]["inputSchema"]["properties"],
                )
        self.assertIn(
            "total is authoritative for BOTH",
            tools["search_invoices"]["description"],
        )

    def test_concurrent_calls_keep_each_request_identity_isolated(self):
        async def call_as(subject):
            context = self._context(subject)
            return await asyncio.to_thread(
                mcp_server_tools.search_quotations,
                query="",
                limit=10,
                ctx=context,
            )

        async def run_calls():
            return await asyncio.gather(
                call_as("user-a"),
                call_as("user-b"),
            )

        alice_result, bob_result = asyncio.run(run_calls())

        self.assertIn("Q-MCP-ALICE", alice_result)
        self.assertNotIn("Q-MCP-BOB", alice_result)
        self.assertIn("Q-MCP-BOB", bob_result)
        self.assertNotIn("Q-MCP-ALICE", bob_result)

    def test_actual_tools_call_uses_bearer_user_per_request(self):
        app = mcp_server_tools.build_asgi_app()

        def call_as(client, subject):
            request = {
                "jsonrpc": "2.0",
                "id": subject,
                "method": "tools/call",
                "params": {
                    "name": "search_quotations",
                    "arguments": {
                        "query": "",
                        "user_id": self.users[1].id,
                    },
                },
            }
            return client.post(
                "/mcp",
                json=request,
                headers={
                    "accept": "application/json, text/event-stream",
                    "host": "localhost:8000",
                    "authorization": f"Bearer {self._bearer_token(subject)}",
                },
            )

        with TestClient(app, base_url="http://localhost:8000") as client:
            with ThreadPoolExecutor(max_workers=2) as executor:
                responses = list(
                    executor.map(
                        lambda subject: call_as(client, subject),
                        ("user-a", "user-b"),
                    )
                )
            for response in responses:
                self.assertEqual(response.status_code, 200, response.text)
            bodies = [response.text for response in responses]

        self.assertIn("Q-MCP-ALICE", bodies[0])
        self.assertNotIn("Q-MCP-BOB", bodies[0])
        self.assertIn("Q-MCP-BOB", bodies[1])
        self.assertNotIn("Q-MCP-ALICE", bodies[1])

    def test_actual_mcp_invoice_month_call_returns_authorized_july_invoice(
        self,
    ):
        invoice = self._invoice(
            "INV-MCP-JULY-2025",
            self.users[0],
            invoice_date=date(2025, 7, 15),
        )
        app = mcp_server_tools.build_asgi_app()
        request = {
            "jsonrpc": "2.0",
            "id": "invoice-july",
            "method": "tools/call",
            "params": {
                "name": "search_invoices",
                "arguments": {
                    "query": "2025年7月",
                    "limit": 20,
                    "offset": 0,
                },
            },
        }

        with TestClient(app, base_url="http://localhost:8000") as client:
            response = client.post(
                "/mcp",
                json=request,
                headers={
                    "accept": "application/json, text/event-stream",
                    "host": "localhost:8000",
                    "authorization": f"Bearer {self._bearer_token('user-a')}",
                },
            )
            request["params"]["arguments"]["summary"] = True
            summary_response = client.post(
                "/mcp",
                json=request,
                headers={
                    "accept": "application/json, text/event-stream",
                    "host": "localhost:8000",
                    "authorization": f"Bearer {self._bearer_token('user-a')}",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        event = json.loads(response.text.split("data: ", 1)[1])
        result = json.loads(event["result"]["content"][0]["text"])

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["offset"], 0)
        self.assertEqual(result["limit"], 1)
        self.assertFalse(result["has_more"])
        self.assertEqual(
            [item["invoice_no"] for item in result["results"]],
            [invoice.invoice_no],
        )
        self.assertEqual(summary_response.status_code, 200)
        summary_event = json.loads(
            summary_response.text.split("data: ", 1)[1]
        )
        summary_result = json.loads(
            summary_event["result"]["content"][0]["text"]
        )
        self.assertEqual(summary_result["limit"], 20)
        self.assertNotIn("items", summary_result["results"][0])

    def test_initialize_requires_oauth_bearer(self):
        app = mcp_server_tools.build_asgi_app()
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1"},
            },
        }
        with TestClient(app, base_url="http://localhost:8000") as client:
            denied = client.post(
                "/mcp",
                json=request,
                headers={"accept": "application/json, text/event-stream"},
            )
            accepted = client.post(
                "/mcp",
                json=request,
                headers={
                    "accept": "application/json, text/event-stream",
                    "authorization": f"Bearer {self._bearer_token()}",
                },
            )
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(accepted.status_code, 200, accepted.text)
