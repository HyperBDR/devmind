from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from quotation.services.upload_validation import validate_quotation_upload


class QuotationUploadValidationTests(SimpleTestCase):
    def test_accepts_supported_excel_and_pdf_files(self):
        excel = SimpleUploadedFile(
            "quote.xlsx",
            b"PK\x03\x04workbook",
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        pdf = SimpleUploadedFile(
            "quote.pdf",
            b"%PDF-1.7",
            content_type="application/pdf",
        )

        validate_quotation_upload(excel)
        validate_quotation_upload(pdf)

    def test_rejects_unsupported_extension(self):
        upload = SimpleUploadedFile("quote.exe", b"binary")

        with self.assertRaisesMessage(
            ValueError, "Only XLSX and PDF files are supported"
        ):
            validate_quotation_upload(upload)

    @override_settings(QUOTATION_MAX_UPLOAD_BYTES=4)
    def test_rejects_oversized_file(self):
        upload = SimpleUploadedFile("quote.pdf", b"%PDF-1.7")

        with self.assertRaisesMessage(
            ValueError, "File must be 4 bytes or smaller"
        ):
            validate_quotation_upload(upload)

    def test_rejects_empty_file(self):
        upload = SimpleUploadedFile("quote.pdf", b"")

        with self.assertRaisesMessage(ValueError, "File is empty"):
            validate_quotation_upload(upload)

    def test_rejects_file_content_that_does_not_match_extension(self):
        fake_pdf = SimpleUploadedFile("quote.pdf", b"not a pdf")
        fake_excel = SimpleUploadedFile("quote.xlsx", b"not an xlsx")

        with self.assertRaisesMessage(
            ValueError, "File content does not match PDF"
        ):
            validate_quotation_upload(fake_pdf)
        with self.assertRaisesMessage(
            ValueError, "File content does not match XLSX"
        ):
            validate_quotation_upload(fake_excel)

    def test_restores_upload_position_after_signature_check(self):
        upload = SimpleUploadedFile("quote.pdf", b"%PDF-1.7 payload")
        upload.seek(3)

        validate_quotation_upload(upload)

        self.assertEqual(upload.tell(), 3)
