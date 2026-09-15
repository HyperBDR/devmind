"""Quote Desk compatibility exports for shared PDF OCR."""

from core.pdf_ocr import PdfOcrError, extract_pdf_text_with_ocr

QuotationOcrError = PdfOcrError

__all__ = ["QuotationOcrError", "extract_pdf_text_with_ocr"]
