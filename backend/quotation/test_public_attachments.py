from io import BytesIO
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from quotation.models import DocumentAsset


def docx_bytes() -> bytes:
    """Build a minimal Word OpenXML package for upload tests."""
    content = BytesIO()
    with ZipFile(content, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types />")
        archive.writestr("word/document.xml", b"<document />")
    return content.getvalue()


class PublicAttachmentUploadTests(TestCase):
    def setUp(self):
        self.storage = TemporaryDirectory()
        self.settings_override = self.settings(
            QUOTATION_STORAGE=self.storage.name,
        )
        self.settings_override.enable()
        self.user = User.objects.create_user(
            username="attachment-admin",
            email="attachment-admin@example.com",
            password="password",
            is_staff=True,
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def tearDown(self):
        self.settings_override.disable()
        self.storage.cleanup()

    def test_word_upload_preserves_word_mime_type(self):
        upload = SimpleUploadedFile(
            "service-scope.docx",
            docx_bytes(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )

        response = self.api.post(
            "/api/v1/quotation/public-attachments",
            {"file": upload, "scope": "All services"},
            format="multipart",
        )

        expected = (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["mime_type"], expected)
        self.assertEqual(
            DocumentAsset.objects.get(pk=response.data["asset_id"]).mime_type,
            expected,
        )
