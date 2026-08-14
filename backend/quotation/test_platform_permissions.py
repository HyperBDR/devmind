from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role
from quotation.models import (
    DocumentAsset,
    DocumentType,
    QuotationMembership,
    QuotationMembershipRole,
    Quotation,
    QuotationSourceType,
)
from quotation.access import can_access_quotation
from quotation.permissions import (
    get_quotation_platform_role,
    is_quotation_platform_admin,
    is_quotation_platform_user,
)


class QuotationPlatformRoleTests(TestCase):
    def test_platform_access_user_defaults_to_quotation_user(self):
        user = User.objects.create_user("first-quotation-user")
        Role.objects.create(
            name="Quotation access",
            visible_features=["quotation_management"],
        ).users.add(user)

        self.assertEqual(
            get_quotation_platform_role(user),
            QuotationMembershipRole.USER,
        )
        self.assertTrue(
            QuotationMembership.objects.filter(
                user=user,
                role=QuotationMembershipRole.USER,
                is_active=True,
            ).exists()
        )

    def test_staff_user_is_an_admin_without_membership(self):
        user = User.objects.create_user("staff-user")
        user.is_staff = True
        user.save(update_fields=["is_staff"])

        self.assertTrue(is_quotation_platform_admin(user))
        self.assertTrue(is_quotation_platform_user(user))
        self.assertEqual(
            get_quotation_platform_role(user),
            QuotationMembershipRole.ADMIN,
        )

    def test_superuser_is_an_admin_without_membership(self):
        user = User.objects.create_superuser("root-user")

        self.assertTrue(is_quotation_platform_admin(user))
        self.assertEqual(
            get_quotation_platform_role(user),
            QuotationMembershipRole.ADMIN,
        )

    def test_active_membership_controls_internal_role(self):
        user = User.objects.create_user("quotation-user")
        QuotationMembership.objects.create(
            user=user,
            role=QuotationMembershipRole.USER,
        )

        self.assertFalse(is_quotation_platform_admin(user))
        self.assertTrue(is_quotation_platform_user(user))
        self.assertEqual(
            get_quotation_platform_role(user),
            QuotationMembershipRole.USER,
        )

    def test_inactive_membership_does_not_grant_access(self):
        user = User.objects.create_user("inactive-user")
        QuotationMembership.objects.create(
            user=user,
            role=QuotationMembershipRole.ADMIN,
            is_active=False,
        )

        self.assertFalse(is_quotation_platform_admin(user))
        self.assertFalse(is_quotation_platform_user(user))
        self.assertIsNone(get_quotation_platform_role(user))


class QuotationPlatformAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="password",
        )
        self.other_user = User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="password",
        )
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _quotation(self, quote_no, *, owner="", created_by=None):
        return Quotation.objects.create(
            quote_no=quote_no,
            source_type=QuotationSourceType.DOCUMENT_IMPORT,
            project_name=quote_no,
            currency="USD",
            payment_terms="CIA",
            quote_date="2026-08-01",
            expire_date="2026-09-01",
            issuer_contact_name=owner,
            issuer_contact_email="sales@example.com",
            client_company="Client",
            contact_person="Contact",
            email="client@example.com",
            created_by_email=created_by,
        )

    def _feishu_asset(self, quotation, folder_name):
        return DocumentAsset.objects.create(
            quotation=quotation,
            doc_type=DocumentType.PDF,
            file_name=f"{quotation.quote_no}.pdf",
            mime_type="application/pdf",
            storage_key=f"quotations/{quotation.quote_no}.pdf",
            source="feishu",
            feishu_file_token=f"token-{quotation.quote_no}",
            feishu_folder_token=f"folder-{folder_name}",
            feishu_folder_path=[
                {"token": "root", "name": "Quotation"},
                {"token": folder_name, "name": folder_name},
            ],
        )

    def test_sales_owner_is_compared_to_username_after_trim_and_casefold(self):
        visible = self._quotation("Q-OWNER", owner=" Alice ")
        hidden = self._quotation("Q-OTHER", owner="bob")

        response = self.api.get("/api/v1/quotation/quotations")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item["id"] for item in response.data["items"]},
            {visible.id},
        )
        self.assertTrue(can_access_quotation(self.user, visible))
        self.assertFalse(can_access_quotation(self.user, hidden))

    def test_empty_sales_owner_uses_last_feishu_folder_name(self):
        visible = self._quotation("Q-FOLDER")
        hidden = self._quotation("Q-FOLDER-OTHER")
        self._feishu_asset(visible, " Alice ")
        self._feishu_asset(hidden, "bob")

        response = self.api.get("/api/v1/quotation/quotations")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item["id"] for item in response.data["items"]},
            {visible.id},
        )

    def test_membership_admin_can_view_all_quotations(self):
        QuotationMembership.objects.create(
            user=self.user,
            role=QuotationMembershipRole.ADMIN,
        )
        first = self._quotation("Q-ADMIN-1", owner="alice")
        second = self._quotation("Q-ADMIN-2", owner="bob")

        response = self.api.get("/api/v1/quotation/quotations")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item["id"] for item in response.data["items"]},
            {first.id, second.id},
        )

    def test_non_matching_detail_is_not_revealed(self):
        quotation = self._quotation("Q-HIDDEN", owner="bob")

        response = self.api.get(
            f"/api/v1/quotation/quotations/{quotation.id}"
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_can_grant_and_revoke_folder_view_access(self):
        admin = User.objects.create_user("grant-admin")
        QuotationMembership.objects.create(
            user=admin,
            role=QuotationMembershipRole.ADMIN,
        )
        quotation = self._quotation("Q-GRANTED", owner="bob")
        asset = self._feishu_asset(quotation, "bob")
        admin_api = APIClient()
        admin_api.force_authenticate(admin)

        granted = admin_api.post(
            "/api/v1/quotation/view-permissions",
            {
                "user_id": self.user.id,
                "target_type": "folder",
                "target_id": asset.feishu_folder_token,
            },
            format="json",
        )

        self.assertEqual(granted.status_code, 201)
        response = self.api.get("/api/v1/quotation/quotations")
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["items"][0]["id"], quotation.id)

        revoked = admin_api.delete(
            f"/api/v1/quotation/view-permissions/{granted.data['id']}"
        )

        self.assertEqual(revoked.status_code, 204)
        response = self.api.get("/api/v1/quotation/quotations")
        self.assertEqual(response.data["total"], 0)

    def test_admin_can_grant_view_access_to_one_document(self):
        admin = User.objects.create_user("document-grant-admin")
        QuotationMembership.objects.create(
            user=admin,
            role=QuotationMembershipRole.ADMIN,
        )
        quotation = self._quotation("Q-DOCUMENT-GRANTED", owner="bob")
        asset = self._feishu_asset(quotation, "bob")
        admin_api = APIClient()
        admin_api.force_authenticate(admin)

        response = admin_api.post(
            "/api/v1/quotation/view-permissions",
            {
                "user_id": self.user.id,
                "target_type": "document",
                "target_id": asset.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        document_response = self.api.get(
            f"/api/v1/quotation/documents?source=feishu"
        )
        self.assertEqual(
            [item["id"] for item in document_response.data],
            [asset.id],
        )

    def test_view_access_context_lists_only_ordinary_users(self):
        admin = User.objects.create_user("context-admin")
        QuotationMembership.objects.create(
            user=admin,
            role=QuotationMembershipRole.ADMIN,
        )
        ordinary = User.objects.create_user("context-user")
        QuotationMembership.objects.create(
            user=ordinary,
            role=QuotationMembershipRole.USER,
        )
        platform_role = Role.objects.create(
            name="Context quotation access",
            visible_features=["quotation_management"],
        )
        platform_role.users.add(ordinary)
        admin_api = APIClient()
        admin_api.force_authenticate(admin)

        response = admin_api.get("/api/v1/quotation/view-permissions")

        self.assertEqual(response.status_code, 200)
        listed_ids = {item["id"] for item in response.data["users"]}
        self.assertIn(ordinary.id, listed_ids)
        self.assertNotIn(admin.id, listed_ids)

    def test_regular_user_cannot_manage_view_permissions(self):
        response = self.api.get("/api/v1/quotation/view-permissions")

        self.assertEqual(response.status_code, 403)
