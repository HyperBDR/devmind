from unittest.mock import patch

from django.test import SimpleTestCase

from core.pdf_ocr import PdfOcrError, extract_pdf_text_with_ocr


class PdfOcrTests(SimpleTestCase):
    def test_page_limit_is_enforced_before_ocr(self):
        document = type("Document", (), {"page_count": 31})()
        context = type(
            "OpenContext",
            (),
            {
                "__enter__": lambda self: document,
                "__exit__": lambda self, *args: None,
            },
        )()

        with patch("core.pdf_ocr.pymupdf.open", return_value=context):
            with self.assertRaises(PdfOcrError):
                extract_pdf_text_with_ocr("invoice.pdf")
