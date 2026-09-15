"""Native PDF text extraction shared by document-oriented applications."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

try:
    import pymupdf
except ImportError:
    pymupdf = None


class PdfTextExtractionError(ValueError):
    """Raised when a PDF cannot be read as text."""


def extract_pdf_text(
    path: str | Path,
    *,
    layout: bool = False,
    prefer_pymupdf: bool = True,
) -> str:
    """Prefer PyMuPDF and fall back to pypdf when needed."""
    path = Path(path)
    if prefer_pymupdf and pymupdf is not None:
        try:
            with pymupdf.open(path) as document:
                text = "\n".join(
                    page.get_text("text", sort=True)
                    for page in document
                )
            if text.strip():
                return text
        except Exception:
            pass
    try:
        reader = PdfReader(str(path))
        mode = "layout" if layout else None
        return "\n".join(
            page.extract_text(extraction_mode=mode) or ""
            if mode
            else page.extract_text() or ""
            for page in reader.pages
        )
    except TimeoutError:
        raise
    except Exception as exc:
        raise PdfTextExtractionError(
            f"Unable to read PDF text: {type(exc).__name__}: {exc}"
        ) from exc
