from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
import httpx
from rest_framework.test import APIRequestFactory, force_authenticate

from quotation.services.pdf_renderer import (
    InvalidExcelDocumentError,
    PdfRendererInvalidResponseError,
    PdfRendererTimeoutError,
    PdfRendererUnavailableError,
    render_excel_to_pdf,
    render_html_to_pdf,
    validate_excel_document,
)
from quotation.views.pdf import (
    PdfFromExcelView,
    PdfFromHtmlView,
    PdfHealthView,
)


XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def xlsx_bytes(*, macro: bool = False, payload: bytes = b"workbook") -> bytes:
    """Build the smallest archive needed for converter boundary tests."""
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"types")
        archive.writestr("xl/workbook.xml", payload)
        if macro:
            archive.writestr("xl/vbaProject.bin", b"macro")
    return output.getvalue()


class PdfRendererTests(SimpleTestCase):
    @patch("quotation.services.pdf_renderer.httpx.post")
    def test_excel_conversion_uses_libreoffice_route(self, post):
        post.return_value = httpx.Response(
            200,
            headers={"content-type": "application/pdf"},
            content=b"%PDF-converted",
        )

        result = render_excel_to_pdf(xlsx_bytes(), "Quote.xlsx")

        assert result == b"%PDF-converted"
        args, kwargs = post.call_args
        assert args[0].endswith("/forms/libreoffice/convert")
        assert kwargs["files"]["files"][0] == "Quote.xlsx"
        assert kwargs["files"]["files"][2] == XLSX_CONTENT_TYPE

    @patch("quotation.services.pdf_renderer.httpx.post")
    def test_legacy_html_conversion_uses_libreoffice_route(self, post):
        post.return_value = httpx.Response(
            200,
            headers={"content-type": "application/pdf"},
            content=b"%PDF-html",
        )

        result = render_html_to_pdf("<html>Quote</html>")

        assert result == b"%PDF-html"
        args, kwargs = post.call_args
        assert args[0].endswith("/forms/libreoffice/convert")
        assert kwargs["files"]["files"][0] == "index.html"
        assert kwargs["files"]["files"][2] == "text/html; charset=utf-8"

    @patch("quotation.services.pdf_renderer.httpx.post")
    def test_conversion_timeout_has_stable_exception(self, post):
        post.side_effect = httpx.ReadTimeout("slow converter")

        with self.assertRaises(PdfRendererTimeoutError):
            render_excel_to_pdf(xlsx_bytes(), "Quote.xlsx")

    @patch("quotation.services.pdf_renderer.httpx.post")
    def test_connection_failure_has_stable_exception(self, post):
        post.side_effect = httpx.ConnectError("converter unavailable")

        with self.assertRaises(PdfRendererUnavailableError):
            render_excel_to_pdf(xlsx_bytes(), "Quote.xlsx")

    @patch("quotation.services.pdf_renderer.httpx.post")
    def test_invalid_converter_response_is_rejected(self, post):
        post.return_value = httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            content=b"not a pdf",
        )

        with self.assertRaises(PdfRendererInvalidResponseError):
            render_excel_to_pdf(xlsx_bytes(), "Quote.xlsx")

    def test_invalid_and_macro_enabled_excel_files_are_rejected(self):
        with self.assertRaises(InvalidExcelDocumentError):
            validate_excel_document(b"not an archive")
        with self.assertRaises(InvalidExcelDocumentError):
            validate_excel_document(xlsx_bytes(macro=True))

    @override_settings(QUOTATION_MAX_XLSX_EXPANDED_BYTES=4)
    def test_expanded_excel_size_is_limited(self):
        with self.assertRaises(InvalidExcelDocumentError):
            validate_excel_document(xlsx_bytes(payload=b"large payload"))


class PdfConversionApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(is_authenticated=True)

    def post_excel(self, upload):
        request = self.factory.post(
            "/api/v1/quotation/pdf/from-excel",
            {"file": upload},
            format="multipart",
        )
        force_authenticate(request, user=self.user)
        return PdfFromExcelView.as_view()(request)

    @patch("quotation.views.pdf.render_excel_to_pdf")
    def test_excel_endpoint_returns_downloadable_pdf(self, render):
        render.return_value = b"%PDF-converted"
        upload = SimpleUploadedFile(
            "Quote-001.xlsx",
            xlsx_bytes(),
            content_type=XLSX_CONTENT_TYPE,
        )

        response = self.post_excel(upload)

        assert response.status_code == 200
        assert response.content == b"%PDF-converted"
        assert response["Content-Type"] == "application/pdf"
        assert "Quote-001.pdf" in response["Content-Disposition"]
        render.assert_called_once()

    @override_settings(QUOTATION_MAX_PDF_XLSX_BYTES=4)
    def test_excel_endpoint_rejects_oversized_upload(self):
        upload = SimpleUploadedFile(
            "Quote.xlsx",
            b"PK oversized",
            content_type=XLSX_CONTENT_TYPE,
        )

        response = self.post_excel(upload)

        assert response.status_code == 413

    @patch("quotation.views.pdf.render_excel_to_pdf")
    def test_excel_endpoint_maps_converter_failures(self, render):
        cases = [
            (PdfRendererUnavailableError(), 503),
            (PdfRendererTimeoutError(), 504),
            (PdfRendererInvalidResponseError(), 502),
        ]
        for error, expected_status in cases:
            with self.subTest(expected_status=expected_status):
                render.side_effect = error
                upload = SimpleUploadedFile(
                    "Quote.xlsx",
                    xlsx_bytes(),
                    content_type=XLSX_CONTENT_TYPE,
                )
                response = self.post_excel(upload)
                assert response.status_code == expected_status

    @patch("quotation.views.pdf.render_html_to_pdf")
    def test_existing_html_endpoint_contract_is_preserved(self, render):
        render.return_value = b"%PDF-html"

        request = self.factory.post(
            "/api/v1/quotation/pdf/from-html",
            {
                "html": "<html>Quote</html>",
                "file_name": "Quote-legacy.pdf",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = PdfFromHtmlView.as_view()(request)

        assert response.status_code == 200
        assert response.content == b"%PDF-html"
        assert "Quote-legacy.pdf" in response["Content-Disposition"]

    @patch("quotation.views.pdf.pdf_renderer_available")
    def test_health_reports_libreoffice_availability(self, available):
        available.return_value = True

        request = self.factory.get("/api/v1/quotation/pdf/health")
        force_authenticate(request, user=self.user)
        response = PdfHealthView.as_view()(request)

        assert response.status_code == 200
        assert response.data == {
            "ok": True,
            "engine": "gotenberg-libreoffice",
            "formats": ["html", "xlsx"],
        }

    @patch("quotation.views.pdf.pdf_renderer_available")
    def test_unavailable_health_keeps_existing_http_contract(self, available):
        available.return_value = False

        request = self.factory.get("/api/v1/quotation/pdf/health")
        force_authenticate(request, user=self.user)
        response = PdfHealthView.as_view()(request)

        assert response.status_code == 200
        assert response.data["ok"] is False
