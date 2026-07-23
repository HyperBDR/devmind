from __future__ import annotations

import subprocess
from pathlib import Path

import pymupdf


class QuotationOcrError(ValueError):
    """Raised when a scanned quotation cannot be recognized safely."""


def extract_pdf_text_with_ocr(
    path: Path,
    *,
    max_pages: int = 30,
    page_timeout: int = 30,
) -> str:
    """OCR bounded PDF pages using the isolated Tesseract executable."""
    texts = []
    try:
        with pymupdf.open(path) as document:
            if document.page_count > max_pages:
                raise QuotationOcrError(
                    f"OCR page limit exceeded: {document.page_count}"
                )
            for page in document:
                pixmap = page.get_pixmap(dpi=150, alpha=False)
                process = subprocess.run(
                    [
                        "tesseract",
                        "stdin",
                        "stdout",
                        "-l",
                        "eng",
                        "--psm",
                        "6",
                    ],
                    input=pixmap.tobytes("png"),
                    capture_output=True,
                    check=False,
                    timeout=page_timeout,
                )
                if process.returncode != 0:
                    raise QuotationOcrError(
                        "Tesseract failed to recognize a PDF page"
                    )
                texts.append(process.stdout.decode("utf-8", errors="replace"))
    except (QuotationOcrError, subprocess.TimeoutExpired):
        raise
    except Exception as exc:
        raise QuotationOcrError(
            f"Unable to OCR PDF: {type(exc).__name__}: {exc}"
        ) from exc
    text = "\n".join(texts).strip()
    if not text:
        raise QuotationOcrError("OCR returned no text")
    return text
