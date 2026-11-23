from io import BytesIO
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.access import get_access_profile
from accounts.models import Role
from quotation.models import (
    DocumentAsset,
    QuotationMembershipRole,
)


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
        self.assertTrue(
            get_access_profile(self.user)["can_manage_public_attachments"]
        )
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

    def test_quote_desk_admin_can_manage_attachments_until_revoked(self):
        user = User.objects.create_user(username="quote-desk-admin")
        role = Role.objects.create(
            name="Sales", visible_features=["quotation_management"],
        )
        role.users.add(user)
        admin_api = APIClient()
        admin_api.force_authenticate(self.user)
        members_url = "/api/v1/quotation/memberships"
        profile_url = "/api/v1/auth/user"
        url = "/api/v1/quotation/public-attachments"
        assigned = admin_api.post(
            members_url,
            {"user_id": user.pk, "role": QuotationMembershipRole.USER},
            format="json",
        )
        self.assertEqual(assigned.status_code, 201, assigned.data)
        membership_url = f"{members_url}/{assigned.data['id']}"

        self.api.force_authenticate(user=user)
        profile = self.api.get(profile_url)
        self.assertEqual(profile.status_code, 200, profile.data)
        self.assertFalse(
            profile.data["access_profile"]["can_manage_public_attachments"]
        )
        self.assertEqual(self.api.post(url, {}).status_code, 403)

        promoted = admin_api.patch(
            membership_url, {"role": QuotationMembershipRole.ADMIN},
            format="json",
        )
        self.assertEqual(promoted.status_code, 200, promoted.data)
        profile = self.api.get(profile_url)
        self.assertEqual(profile.status_code, 200, profile.data)
        self.assertEqual(profile.data["roles"][0]["name"], "Sales")
        self.assertTrue(
            profile.data["access_profile"]["can_manage_public_attachments"]
        )

        upload = SimpleUploadedFile(
            "support.pdf", b"%PDF-1.7 attachment", content_type="application/pdf",
        )
        response = self.api.post(
            url, {"file": upload, "scope": "All services"}, format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        attachment_id = response.data["id"]
        status_url = f"{url}/{attachment_id}/status"
        response = self.api.patch(status_url, {"status": "archived"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.api.get(url).data), 1)
        response = self.api.patch(status_url, {"status": "active"})
        self.assertEqual(response.status_code, 200)

        self.assertEqual(admin_api.delete(membership_url).status_code, 204)
        profile = self.api.get(profile_url)
        self.assertEqual(profile.status_code, 200, profile.data)
        self.assertFalse(
            profile.data["access_profile"]["can_manage_public_attachments"]
        )
        self.assertEqual(
            self.api.post(url, {}, format="multipart").status_code, 403,
        )
        response = self.api.patch(status_url, {"status": "archived"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(self.api.get(url).data), 1)

        archived = admin_api.patch(status_url, {"status": "archived"})
        self.assertEqual(archived.status_code, 200, archived.data)
        self.assertEqual(self.api.get(url).data, [])
