from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.access import get_access_profile
from accounts.models import Role
from invoice.models import (
    Invoice,
    InvoiceAccessGrant,
    InvoiceAccessRole,
    InvoiceDocument,
    InvoiceDocumentPurpose,
    InvoiceDocumentType,
    InvoiceSourceType,
)
from invoice.permissions import has_invoice_upload_access
from invoice.services.feishu_upload import (
    InvoiceFeishuUploadError,
    upload_invoice_to_feishu,
)
from quotation.models import (
    AuditEvent,
    QuotationMembership,
    QuotationMembershipRole,
    QuotationUploadPermission,
    QuotationViewPermission,
    QuotationViewPermissionTarget,
)


class InvoiceAccessPermissionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("quote-access-admin")
        self.quote_role = Role.objects.create(
            name="Quote access for Invoice grants",
            visible_features=["quotation_management"],
        )
        self.admin.platform_roles.add(self.quote_role)
        QuotationMembership.objects.create(
            user=self.admin,
            role=QuotationMembershipRole.ADMIN,
            assigned_by=self.admin,
        )
        self.grantee = User.objects.create_user(
            "invoice-grantee",
            email="grantee@example.com",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_quote_admin_can_grant_and_revoke_invoice_access(self):
        response = self.client.post(
            "/api/v1/invoice/access-permissions",
            {
                "user_id": self.grantee.id,
                "expires_at": None,
                "role": InvoiceAccessRole.USER,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        grant = InvoiceAccessGrant.objects.get(user=self.grantee)
        self.assertEqual(grant.granted_by, self.admin)
        self.assertEqual(grant.role, InvoiceAccessRole.USER)
        self.assertEqual(response.data["role"], InvoiceAccessRole.USER)
        self.assertIn(
            "quotation_management",
            get_access_profile(self.grantee)["visible_features"],
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                event_name="permissions.invoice_access_granted"
            ).exists()
        )

        invoice_client = APIClient()
        invoice_client.force_authenticate(self.grantee)
        self.assertEqual(
            invoice_client.get("/api/v1/invoice/invoices").status_code,
            200,
        )

        revoked = self.client.delete(
            f"/api/v1/invoice/access-permissions/{grant.id}"
        )

        self.assertEqual(revoked.status_code, 204)
        grant.refresh_from_db()
        self.assertFalse(grant.is_active)
        self.assertNotIn(
            "quotation_management",
            get_access_profile(self.grantee)["visible_features"],
        )
        self.assertEqual(
            invoice_client.get("/api/v1/invoice/invoices").status_code,
            403,
        )

    def test_grant_context_lists_users_and_active_permissions(self):
        grant = InvoiceAccessGrant.objects.create(
            user=self.grantee,
            granted_by=self.admin,
        )

        response = self.client.get("/api/v1/invoice/access-permissions")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            self.grantee.id,
            {user["id"] for user in response.data["users"]},
        )
        self.assertEqual(response.data["permissions"][0]["id"], grant.id)
        self.assertEqual(
            response.data["permissions"][0]["status"],
            "active",
        )

    def test_quote_admin_can_change_invoice_access_expiry(self):
        grant = InvoiceAccessGrant.objects.create(
            user=self.grantee,
            granted_by=self.admin,
        )
        expires_at = timezone.now() + timedelta(days=30)

        response = self.client.patch(
            f"/api/v1/invoice/access-permissions/{grant.id}",
            {"expires_at": expires_at.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        grant.refresh_from_db()
        self.assertAlmostEqual(
            grant.expires_at.timestamp(),
            expires_at.timestamp(),
            delta=1,
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                event_name="permissions.invoice_access_expiry_changed"
            ).exists()
        )

    def test_quote_admin_can_change_invoice_role(self):
        grant = InvoiceAccessGrant.objects.create(
            user=self.grantee,
            granted_by=self.admin,
            role=InvoiceAccessRole.USER,
        )

        response = self.client.patch(
            f"/api/v1/invoice/access-permissions/{grant.id}",
            {"role": InvoiceAccessRole.ADMIN},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        grant.refresh_from_db()
        self.assertEqual(grant.role, InvoiceAccessRole.ADMIN)
        self.assertEqual(response.data["role"], InvoiceAccessRole.ADMIN)
        self.assertTrue(
            AuditEvent.objects.filter(
                event_name="permissions.invoice_access_role_changed"
            ).exists()
        )

    def test_invoice_access_rejects_unknown_role(self):
        response = self.client.post(
            "/api/v1/invoice/access-permissions",
            {
                "user_id": self.grantee.id,
                "role": "owner",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.data)

    def test_regular_user_cannot_manage_invoice_access(self):
        client = APIClient()
        client.force_authenticate(self.grantee)

        response = client.get("/api/v1/invoice/access-permissions")

        self.assertEqual(response.status_code, 403)

    def test_staff_user_has_invoice_access_without_platform_role(self):
        staff_user = User.objects.create_user(
            "system-staff",
            is_staff=True,
            is_superuser=True,
        )
        client = APIClient()
        client.force_authenticate(staff_user)

        response = client.get("/api/v1/invoice/invoices")

        self.assertEqual(response.status_code, 200)

    def test_feishu_folder_view_grant_exposes_imported_invoice(self):
        InvoiceAccessGrant.objects.create(
            user=self.grantee,
            granted_by=self.admin,
            role=InvoiceAccessRole.USER,
        )
        invoice = Invoice.objects.create(
            invoice_no="INV-GRANTED-FOLDER",
            customer_name="Granted customer",
            source_type=InvoiceSourceType.FEISHU,
        )
        InvoiceDocument.objects.create(
            invoice=invoice,
            file_name="granted.pdf",
            storage_key="documents/granted.pdf",
            feishu_file_token="granted-file",
            feishu_folder_token="granted-folder",
        )
        QuotationViewPermission.objects.create(
            user=self.grantee,
            target_type=QuotationViewPermissionTarget.FOLDER,
            folder_token="granted-folder",
            granted_by=self.admin,
        )

        client = APIClient()
        client.force_authenticate(self.grantee)
        response = client.get("/api/v1/invoice/invoices")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["id"] for row in response.data["items"]],
            [invoice.id],
        )

    def test_feishu_file_view_grant_exposes_one_imported_invoice(self):
        InvoiceAccessGrant.objects.create(
            user=self.grantee,
            granted_by=self.admin,
            role=InvoiceAccessRole.USER,
        )
        invoice = Invoice.objects.create(
            invoice_no="INV-GRANTED-FILE",
            customer_name="Granted file customer",
            source_type=InvoiceSourceType.FEISHU,
        )
        document = InvoiceDocument.objects.create(
            invoice=invoice,
            file_name="granted-file.pdf",
            storage_key="documents/granted-file.pdf",
            feishu_file_token="granted-file-token",
            feishu_folder_token="granted-folder",
        )
        response = self.client.post(
            "/api/v1/quotation/view-permissions",
            {
                "user_id": self.grantee.id,
                "target_type": "document",
                "target_id": f"invoice:{document.id}",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        client = APIClient()
        client.force_authenticate(self.grantee)
        response = client.get("/api/v1/invoice/invoices")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["id"] for row in response.data["items"]],
            [invoice.id],
        )

    def test_feishu_upload_rejects_ungranted_folder_for_invoice_user(self):
        InvoiceAccessGrant.objects.create(
            user=self.grantee,
            granted_by=self.admin,
            role=InvoiceAccessRole.USER,
        )
        invoice = Invoice.objects.create(
            invoice_no="INV-UPLOAD-GRANT",
            status="issued",
            source_type=InvoiceSourceType.MANUAL,
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "invoice.pdf"
            path.write_bytes(b"pdf")
            document = InvoiceDocument.objects.create(
                invoice=invoice,
                file_name="invoice.pdf",
                storage_key="issued/invoice.pdf",
                document_type=InvoiceDocumentType.PDF,
                purpose=InvoiceDocumentPurpose.ISSUED,
            )
            fake_route = SimpleNamespace(
                mount=SimpleNamespace(root_folder_token="invoice-root"),
                connection=SimpleNamespace(id="connection"),
                provider=SimpleNamespace(
                    access_token=lambda: "token",
                    client=SimpleNamespace(
                        get_folder_meta=lambda *_args: {},
                    ),
                    upload=lambda *_args, **_kwargs: {
                        "file_token": "uploaded",
                    },
                ),
            )
            with patch(
                "invoice.services.feishu_upload.invoice_storage"
            ) as storage_factory, patch(
                "invoice.services.feishu_upload.StorageRouter.resolve",
                return_value=fake_route,
            ):
                storage_factory.return_value.resolve.return_value = path
                with self.assertRaisesRegex(
                    InvoiceFeishuUploadError,
                    "Upload access",
                ):
                    upload_invoice_to_feishu(
                        invoice,
                        actor=self.grantee,
                        folder_token="invoice-root",
                    )
            document.refresh_from_db()
            self.assertEqual(document.feishu_file_token, "")

    def test_invoice_upload_grant_allows_exact_folder_for_user(self):
        InvoiceAccessGrant.objects.create(
            user=self.grantee,
            granted_by=self.admin,
            role=InvoiceAccessRole.USER,
        )
        QuotationUploadPermission.objects.create(
            user=self.grantee,
            folder_token="invoice-folder",
            folder_name="Invoice folder",
            granted_by=self.admin,
        )

        self.assertTrue(
            has_invoice_upload_access(self.grantee, "invoice-folder")
        )
        self.assertFalse(
            has_invoice_upload_access(self.grantee, "other-folder")
        )

    def test_invoice_admin_bypasses_folder_upload_grants(self):
        InvoiceAccessGrant.objects.create(
            user=self.grantee,
            granted_by=self.admin,
            role=InvoiceAccessRole.ADMIN,
        )

        self.assertTrue(
            has_invoice_upload_access(self.grantee, "invoice-folder")
        )
