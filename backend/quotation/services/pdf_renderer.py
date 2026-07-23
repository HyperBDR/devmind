from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.conf import settings
import httpx


XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
REQUIRED_XLSX_PARTS = {
    "[Content_Types].xml",
    "xl/workbook.xml",
}
MAX_XLSX_ENTRY_COUNT = 2000


class PdfRendererError(Exception):
    """Base exception for quotation PDF conversion failures."""


class PdfRendererUnavailableError(PdfRendererError):
    """Raised when the isolated converter cannot be reached."""


class PdfRendererTimeoutError(PdfRendererError):
    """Raised when conversion exceeds the configured deadline."""


class PdfRendererInvalidResponseError(PdfRendererError):
    """Raised when the converter does not return a valid PDF."""


class InvalidExcelDocumentError(ValueError):
    """Raised when an upload is not a safe XLSX document."""


def _gotenberg_url(path: str) -> str:
    base_url = settings.GOTENBERG_URL.rstrip("/")
    return f"{base_url}{path}"


def _request_timeout() -> httpx.Timeout:
    seconds = settings.GOTENBERG_TIMEOUT_SECONDS
    return httpx.Timeout(seconds, connect=min(seconds, 5))


def _safe_xlsx_name(file_name: str) -> str:
    name = Path(str(file_name or "quotation.xlsx")).name
    name = name.replace("\r", "").replace("\n", "").replace("\x00", "")
    if not name.lower().endswith(".xlsx"):
        name = f"{name}.xlsx"
    return name or "quotation.xlsx"


def _validate_pdf_response(response: httpx.Response) -> bytes:
    if response.status_code == 503:
        raise PdfRendererUnavailableError("PDF converter is unavailable")
    if not response.is_success:
        raise PdfRendererInvalidResponseError(
            "PDF converter rejected the document"
        )

    content_type = response.headers.get("content-type", "")
    if content_type.split(";", 1)[0].strip().lower() != "application/pdf":
        raise PdfRendererInvalidResponseError(
            "PDF converter returned an invalid content type"
        )

    pdf_bytes = response.content
    if not pdf_bytes.startswith(b"%PDF-"):
        raise PdfRendererInvalidResponseError(
            "PDF converter returned invalid document bytes"
        )
    if len(pdf_bytes) > settings.QUOTATION_MAX_PDF_BYTES:
        raise PdfRendererInvalidResponseError(
            "Converted PDF exceeds the configured size limit"
        )
    return pdf_bytes


def _convert(
    path: str,
    *,
    files: dict,
    data: dict[str, str] | None = None,
) -> bytes:
    try:
        response = httpx.post(
            _gotenberg_url(path),
            files=files,
            data=data,
            timeout=_request_timeout(),
        )
    except httpx.TimeoutException as exc:
        raise PdfRendererTimeoutError(
            "PDF conversion timed out"
        ) from exc
    except httpx.RequestError as exc:
        raise PdfRendererUnavailableError(
            "PDF converter is unavailable"
        ) from exc
    return _validate_pdf_response(response)


def validate_excel_document(excel_bytes: bytes) -> None:
    """Reject malformed, macro-enabled, or oversized XLSX archives."""
    if not excel_bytes.startswith(b"PK"):
        raise InvalidExcelDocumentError("File is not a valid XLSX document")

    try:
        with ZipFile(BytesIO(excel_bytes)) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
    except BadZipFile as exc:
        raise InvalidExcelDocumentError(
            "File is not a valid XLSX document"
        ) from exc

    if not REQUIRED_XLSX_PARTS.issubset(names):
        raise InvalidExcelDocumentError("File is not a valid XLSX document")
    if "xl/vbaProject.bin" in names:
        raise InvalidExcelDocumentError("Macro-enabled files are not allowed")
    if len(entries) > MAX_XLSX_ENTRY_COUNT:
        raise InvalidExcelDocumentError("XLSX document has too many entries")

    uncompressed_size = sum(entry.file_size for entry in entries)
    if uncompressed_size > settings.QUOTATION_MAX_XLSX_EXPANDED_BYTES:
        raise InvalidExcelDocumentError(
            "Expanded XLSX document exceeds the configured size limit"
        )


def render_excel_to_pdf(excel_bytes: bytes, file_name: str) -> bytes:
    """Convert an Excel quotation through the LibreOffice-only service."""
    validate_excel_document(excel_bytes)
    safe_name = _safe_xlsx_name(file_name)
    return _convert(
        "/forms/libreoffice/convert",
        files={
            "files": (
                safe_name,
                excel_bytes,
                XLSX_CONTENT_TYPE,
            )
        },
    )


def render_html_to_pdf(html: str) -> bytes:
    """Preserve the legacy HTML conversion contract through LibreOffice."""
    if not html or not html.strip():
        raise ValueError("HTML content is empty")
    return _convert(
        "/forms/libreoffice/convert",
        files={
            "files": (
                "index.html",
                html.encode("utf-8"),
                "text/html; charset=utf-8",
            )
        },
    )


def pdf_renderer_available() -> bool:
    """Return whether the isolated LibreOffice service is healthy."""
    seconds = min(settings.GOTENBERG_TIMEOUT_SECONDS, 3)
    try:
        response = httpx.get(
            _gotenberg_url("/health"),
            timeout=httpx.Timeout(seconds, connect=min(seconds, 2)),
        )
    except httpx.RequestError:
        return False
    return response.is_success
