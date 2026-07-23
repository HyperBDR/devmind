from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.utils.http import content_disposition_header
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.services.pdf_renderer import (
    InvalidExcelDocumentError,
    PdfRendererInvalidResponseError,
    PdfRendererTimeoutError,
    PdfRendererUnavailableError,
    pdf_renderer_available,
    render_excel_to_pdf,
    render_html_to_pdf,
)


def _pdf_response(pdf_bytes: bytes, file_name: str) -> HttpResponse:
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = content_disposition_header(
        True,
        file_name,
    )
    return response


def _pdf_error_response(exc: Exception) -> Response:
    if isinstance(exc, PdfRendererTimeoutError):
        return Response({"detail": "PDF conversion timed out"}, status=504)
    if isinstance(exc, PdfRendererUnavailableError):
        return Response(
            {"detail": "PDF conversion service is unavailable"},
            status=503,
        )
    return Response({"detail": "PDF conversion failed"}, status=502)


def _pdf_file_name(source_name: str) -> str:
    source = Path(str(source_name or "quotation")).name
    source = source.replace("\r", "").replace("\n", "").replace("\x00", "")
    stem = Path(source).stem or "quotation"
    return f"{stem}.pdf"


class PdfHealthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok = pdf_renderer_available()
        payload = {
            "ok": ok,
            "engine": "gotenberg-libreoffice",
            "formats": ["html", "xlsx"],
        }
        if not ok:
            payload["detail"] = "PDF conversion service is unavailable"
        return Response(payload)


class PdfFromExcelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "Excel file is required"}, status=400)
        if not str(upload.name).lower().endswith(".xlsx"):
            return Response(
                {"detail": "Only XLSX files are supported"},
                status=400,
            )
        if upload.size > settings.QUOTATION_MAX_PDF_XLSX_BYTES:
            return Response(
                {"detail": "Excel file exceeds the configured size limit"},
                status=413,
            )

        excel_bytes = upload.read()
        if not excel_bytes:
            return Response({"detail": "Excel file is empty"}, status=400)
        try:
            pdf_bytes = render_excel_to_pdf(excel_bytes, upload.name)
        except InvalidExcelDocumentError as exc:
            return Response({"detail": str(exc)}, status=400)
        except (
            PdfRendererInvalidResponseError,
            PdfRendererTimeoutError,
            PdfRendererUnavailableError,
        ) as exc:
            return _pdf_error_response(exc)
        return _pdf_response(pdf_bytes, _pdf_file_name(upload.name))


class PdfFromHtmlView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        html = request.data.get("html") or ""
        file_name = _pdf_file_name(
            request.data.get("file_name") or "quotation.pdf"
        )
        if not str(html).strip():
            return Response({"detail": "HTML content is empty"}, status=400)
        if len(str(html).encode("utf-8")) > (
            settings.QUOTATION_MAX_PDF_HTML_BYTES
        ):
            return Response(
                {"detail": "HTML content exceeds the configured size limit"},
                status=413,
            )
        try:
            pdf_bytes = render_html_to_pdf(str(html))
        except (
            PdfRendererInvalidResponseError,
            PdfRendererTimeoutError,
            PdfRendererUnavailableError,
        ) as exc:
            return _pdf_error_response(exc)
        return _pdf_response(pdf_bytes, file_name)
