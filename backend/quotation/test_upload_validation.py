from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from quotation.services.upload_validation import (
    validate_public_attachment_upload,
    validate_quotation_upload,
)


def xlsx_upload(
    entries: dict[str, bytes] | None = None,
) -> SimpleUploadedFile:
    """Build a minimal XLSX-shaped upload for archive validation tests."""
    content = BytesIO()
    workbook_entries = entries or {
        "[Content_Types].xml": b"<Types />",
        "xl/workbook.xml": b"<workbook />",
        "xl/worksheets/sheet1.xml": b"<worksheet />",
    }
    with ZipFile(content, "w", compression=ZIP_DEFLATED) as archive:
        for name, value in workbook_entries.items():
            archive.writestr(name, value)
    return SimpleUploadedFile(
        "quote.xlsx",
        content.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )


def docx_upload() -> SimpleUploadedFile:
    """Build a minimal DOCX-shaped upload for attachment validation."""
    content = BytesIO()
    with ZipFile(content, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types />")
        archive.writestr("word/document.xml", b"<document />")
    return SimpleUploadedFile(
        "scope.docx",
        content.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
    )


def encrypted_xlsx_upload() -> SimpleUploadedFile:
    """Build an upload whose ZIP headers carry the encryption flag."""
    upload = xlsx_upload()
    content = bytearray(upload.read())
    local_header = content.index(b"PK\x03\x04")
    central_header = content.index(b"PK\x01\x02")
    content[local_header + 6] |= 1
    content[central_header + 8] |= 1
    return SimpleUploadedFile("encrypted.xlsx", bytes(content))


class QuotationUploadValidationTests(SimpleTestCase):
    def test_accepts_supported_excel_and_pdf_files(self):
        excel = xlsx_upload()
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

    def test_restores_xlsx_position_after_archive_checks(self):
        upload = xlsx_upload()
        upload.seek(3)

        validate_quotation_upload(upload)

        self.assertEqual(upload.tell(), 3)

    def test_rejects_malformed_xlsx_archive(self):
        upload = SimpleUploadedFile("quote.xlsx", b"PK\x03\x04not-a-zip")

        with self.assertRaisesMessage(ValueError, "XLSX archive is invalid"):
            validate_quotation_upload(upload)

    def test_rejects_zip_without_required_xlsx_structure(self):
        upload = xlsx_upload({"document.txt": b"not a workbook"})

        with self.assertRaisesMessage(
            ValueError,
            "XLSX archive is missing required workbook entries",
        ):
            validate_quotation_upload(upload)

    @override_settings(QUOTATION_XLSX_MAX_ENTRIES=2)
    def test_rejects_xlsx_with_too_many_entries(self):
        upload = xlsx_upload()

        with self.assertRaisesMessage(
            ValueError,
            "XLSX archive has more than 2 entries",
        ):
            validate_quotation_upload(upload)

    def test_rejects_xlsx_path_traversal(self):
        for name in ("../escape.xml", "/absolute.xml", "C:/drive.xml"):
            with self.subTest(name=name):
                upload = xlsx_upload({name: b"unsafe"})

                with self.assertRaisesMessage(
                    ValueError,
                    "XLSX archive contains an unsafe path",
                ):
                    validate_quotation_upload(upload)

    def test_rejects_encrypted_xlsx_entry(self):
        with self.assertRaisesMessage(
            ValueError,
            "Encrypted XLSX entries are not supported",
        ):
            validate_quotation_upload(encrypted_xlsx_upload())

    @override_settings(QUOTATION_XLSX_MAX_ENTRY_BYTES=4)
    def test_rejects_oversized_xlsx_entry(self):
        upload = xlsx_upload({"xl/workbook.xml": b"12345"})

        with self.assertRaisesMessage(
            ValueError,
            "XLSX entry exceeds the 4 byte expanded size limit",
        ):
            validate_quotation_upload(upload)

    @override_settings(
        QUOTATION_XLSX_MAX_ENTRY_BYTES=20,
        QUOTATION_XLSX_MAX_EXPANDED_BYTES=8,
    )
    def test_rejects_oversized_total_xlsx_content(self):
        upload = xlsx_upload(
            {
                "xl/workbook.xml": b"12345",
                "xl/worksheets/sheet1.xml": b"67890",
            }
        )

        with self.assertRaisesMessage(
            ValueError,
            "XLSX expanded content exceeds the 8 byte limit",
        ):
            validate_quotation_upload(upload)

    @override_settings(QUOTATION_XLSX_MAX_COMPRESSION_RATIO=2)
    def test_rejects_abnormal_xlsx_compression_ratio(self):
        upload = xlsx_upload({"xl/workbook.xml": b"A" * 1000})

        with self.assertRaisesMessage(
            ValueError,
            "XLSX entry exceeds the 2:1 compression ratio limit",
        ):
            validate_quotation_upload(upload)

    @override_settings(QUOTATION_XLSX_MAX_WORKSHEETS=1)
    def test_rejects_too_many_xlsx_worksheets(self):
        upload = xlsx_upload(
            {
                "xl/worksheets/sheet1.xml": b"<worksheet />",
                "xl/worksheets/sheet2.xml": b"<worksheet />",
            }
        )

        with self.assertRaisesMessage(
            ValueError,
            "XLSX workbook has more than 1 worksheets",
        ):
            validate_quotation_upload(upload)

    @override_settings(QUOTATION_XLSX_MAX_SHARED_STRINGS_BYTES=4)
    def test_rejects_oversized_shared_strings(self):
        upload = xlsx_upload({"xl/sharedStrings.xml": b"12345"})

        with self.assertRaisesMessage(
            ValueError,
            "XLSX shared strings exceed the 4 byte limit",
        ):
            validate_quotation_upload(upload)

    @override_settings(QUOTATION_XLSX_MAX_SHARED_STRINGS=2)
    def test_rejects_too_many_shared_strings(self):
        upload = xlsx_upload(
            {
                "xl/sharedStrings.xml": (
                    b'<sst xmlns="urn:test"><si/><si/><si/></sst>'
                )
            }
        )

        with self.assertRaisesMessage(
            ValueError,
            "XLSX shared strings exceed the 2 item limit",
        ):
            validate_quotation_upload(upload)


class PublicAttachmentUploadValidationTests(SimpleTestCase):
    def test_accepts_pdf_word_and_excel_content(self):
        uploads = [
            SimpleUploadedFile("scope.pdf", b"%PDF-1.7 attachment"),
            SimpleUploadedFile("scope.doc", b"\xd0\xcf\x11\xe0document"),
            docx_upload(),
            SimpleUploadedFile("scope.xls", b"\xd0\xcf\x11\xe0workbook"),
            xlsx_upload(),
        ]

        for upload in uploads:
            with self.subTest(file_name=upload.name):
                validate_public_attachment_upload(upload)

    def test_rejects_image_attachments(self):
        upload = SimpleUploadedFile(
            "screenshot.png",
            b"\x89PNG\r\n\x1a\ncontent",
            content_type="image/png",
        )

        with self.assertRaisesMessage(
            ValueError,
            "Only PDF, Word, and Excel public attachments are supported",
        ):
            validate_public_attachment_upload(upload)

    def test_rejects_openxml_content_that_does_not_match_extension(self):
        workbook = xlsx_upload()
        upload = SimpleUploadedFile("renamed.docx", workbook.read())

        with self.assertRaisesMessage(
            ValueError,
            "File content does not match DOCX",
        ):
            validate_public_attachment_upload(upload)

    @override_settings(QUOTATION_XLSX_MAX_ENTRIES=1)
    def test_rejects_docx_archive_with_too_many_entries(self):
        upload = docx_upload()

        with self.assertRaisesMessage(
            ValueError,
            "DOCX archive has more than 1 entries",
        ):
            validate_public_attachment_upload(upload)
