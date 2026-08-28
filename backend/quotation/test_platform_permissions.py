from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role
from quotation.access import can_access_quotation
from quotation.models import (
    AuditEvent,
    DocumentAsset,
    DocumentType,
    Quotation,
    QuotationMembership,
    QuotationMembershipRole,
    QuotationSourceType,
    QuotationViewPermission,
    QuotationViewPermissionTarget,
)
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
        self.platform_role = Role.objects.create(
            name="Quotation platform access",
            visible_features=["quotation_management"],
        )
        self.platform_role.users.add(self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _quotation(
        self,
        quote_no,
        *,
        owner="",
        created_by=None,
        source_type=QuotationSourceType.DOCUMENT_IMPORT,
    ):
        return Quotation.objects.create(
            quote_no=quote_no,
            source_type=source_type,
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

    def test_manual_sales_owner_can_open_detail(self):
        quotation = self._quotation(
            "Q-MANUAL-OWNER",
            owner=" Alice ",
            created_by="admin@example.com",
            source_type=QuotationSourceType.MANUAL,
        )

        response = self.api.get(
            f"/api/v1/quotation/quotations/{quotation.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], quotation.id)

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
        self.platform_role.users.add(admin)
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
        self.platform_role.users.add(admin)
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
            "/api/v1/quotation/documents?source=feishu"
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
        platform_role.users.add(admin, ordinary)
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


class QuotationPermissionLifecycleTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("permission-admin")
        QuotationMembership.objects.create(
            user=self.admin,
            role=QuotationMembershipRole.ADMIN,
            assigned_by=self.admin,
        )
        self.member = User.objects.create_user("permission-member")
        self.outsider = User.objects.create_user("permission-outsider")
        self.platform_role = Role.objects.create(
            name="Quote Desk access",
            visible_features=["quotation_management"],
        )
        self.platform_role.users.add(self.admin, self.member)
        self.api = APIClient()
        self.api.force_authenticate(self.admin)

    def _feishu_asset(self):
        quotation = Quotation.objects.create(
            quote_no="Q-PERMISSION-LIFECYCLE",
            source_type=QuotationSourceType.DOCUMENT_IMPORT,
            project_name="Permission lifecycle",
            currency="USD",
            payment_terms="CIA",
            quote_date="2026-08-01",
            expire_date="2026-09-01",
            issuer_contact_name="someone-else",
            issuer_contact_email="sales@example.com",
            client_company="Client",
            contact_person="Contact",
            email="client@example.com",
        )
        return DocumentAsset.objects.create(
            quotation=quotation,
            doc_type=DocumentType.PDF,
            file_name="permission.pdf",
            mime_type="application/pdf",
            storage_key="quotations/permission.pdf",
            source="feishu",
            feishu_file_token="permission-file",
            feishu_folder_token="permission-folder",
            feishu_folder_path=[
                {"token": "root", "name": "Quotation"},
                {"token": "permission-folder", "name": "Permissions"},
            ],
        )

    def test_admin_assigns_quote_desk_role_with_actor_audit(self):
        response = self.api.post(
            "/api/v1/quotation/memberships",
            {
                "user_id": self.member.id,
                "role": QuotationMembershipRole.USER,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        membership = QuotationMembership.objects.get(user=self.member)
        self.assertEqual(membership.assigned_by, self.admin)
        event = AuditEvent.objects.get(
            event_name="permissions.role_assigned",
        )
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(event.target_id, str(membership.id))
        self.assertEqual(event.risk_level, AuditEvent.RISK_MEDIUM)
        self.assertIsNotNone(event.created_at)

    def test_admin_changes_role_without_creating_duplicate_membership(self):
        membership = QuotationMembership.objects.create(
            user=self.member,
            role=QuotationMembershipRole.USER,
            assigned_by=self.admin,
        )

        response = self.api.patch(
            f"/api/v1/quotation/memberships/{membership.id}",
            {"role": QuotationMembershipRole.ADMIN},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        membership.refresh_from_db()
        self.assertEqual(membership.role, QuotationMembershipRole.ADMIN)
        self.assertEqual(membership.assigned_by, self.admin)
        self.assertEqual(
            QuotationMembership.objects.filter(
                user=self.member,
                is_active=True,
            ).count(),
            1,
        )
        event = AuditEvent.objects.get(
            event_name="permissions.role_changed",
        )
        self.assertEqual(
            event.before_summary["role"],
            QuotationMembershipRole.USER,
        )
        self.assertEqual(
            event.after_summary["role"],
            QuotationMembershipRole.ADMIN,
        )

    def test_duplicate_active_role_is_rejected(self):
        QuotationMembership.objects.create(
            user=self.member,
            role=QuotationMembershipRole.USER,
            assigned_by=self.admin,
        )

        response = self.api.post(
            "/api/v1/quotation/memberships",
            {
                "user_id": self.member.id,
                "role": QuotationMembershipRole.USER,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            QuotationMembership.objects.filter(
                user=self.member,
                is_active=True,
            ).count(),
            1,
        )

    def test_user_without_first_layer_access_cannot_be_managed(self):
        response = self.api.post(
            "/api/v1/quotation/memberships",
            {
                "user_id": self.outsider.id,
                "role": QuotationMembershipRole.USER,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            QuotationMembership.objects.filter(user=self.outsider).exists()
        )

    def test_admin_without_first_layer_access_cannot_manage_permissions(self):
        self.platform_role.users.remove(self.admin)

        membership_response = self.api.get(
            "/api/v1/quotation/memberships"
        )
        permission_response = self.api.get(
            "/api/v1/quotation/view-permissions"
        )

        self.assertEqual(membership_response.status_code, 403)
        self.assertEqual(permission_response.status_code, 403)

    def test_admin_sets_edits_and_lists_grant_expiry(self):
        asset = self._feishu_asset()
        first_expiry = timezone.now() + timedelta(days=1)
        granted = self.api.post(
            "/api/v1/quotation/view-permissions",
            {
                "user_id": self.member.id,
                "target_type": QuotationViewPermissionTarget.DOCUMENT,
                "target_id": asset.id,
                "expires_at": first_expiry.isoformat(),
            },
            format="json",
        )

        self.assertEqual(granted.status_code, 201)
        self.assertEqual(granted.data["status"], "active")
        self.assertIsNotNone(granted.data["expires_at"])

        second_expiry = timezone.now() + timedelta(days=2)
        updated = self.api.patch(
            f"/api/v1/quotation/view-permissions/{granted.data['id']}",
            {"expires_at": second_expiry.isoformat()},
            format="json",
        )

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["status"], "active")
        granted_event = AuditEvent.objects.get(
            event_name="permissions.view_granted",
        )
        self.assertEqual(
            granted_event.target_type,
            "quotation_view_permission",
        )
        self.assertEqual(granted_event.target_id, str(granted.data["id"]))
        self.assertEqual(granted_event.document_id_snapshot, "")
        self.assertEqual(
            granted_event.after_summary["target_id"],
            str(asset.id),
        )
        self.assertEqual(granted_event.risk_level, AuditEvent.RISK_MEDIUM)
        event = AuditEvent.objects.get(
            event_name="permissions.view_expiry_changed",
        )
        self.assertEqual(event.actor, self.admin)
        self.assertNotEqual(
            event.before_summary["expires_at"],
            event.after_summary["expires_at"],
        )

    def test_expired_grant_is_listed_but_does_not_provide_access(self):
        asset = self._feishu_asset()
        permission = QuotationViewPermission.objects.create(
            user=self.member,
            target_type=QuotationViewPermissionTarget.DOCUMENT,
            document=asset,
            granted_by=self.admin,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        response = self.api.get("/api/v1/quotation/view-permissions")

        row = next(
            item
            for item in response.data["permissions"]
            if item["id"] == permission.id
        )
        self.assertEqual(row["status"], "expired")
        self.assertFalse(can_access_quotation(self.member, asset.quotation))

    def test_duplicate_active_grant_is_rejected(self):
        asset = self._feishu_asset()
        payload = {
            "user_id": self.member.id,
            "target_type": QuotationViewPermissionTarget.DOCUMENT,
            "target_id": asset.id,
        }

        first = self.api.post(
            "/api/v1/quotation/view-permissions",
            payload,
            format="json",
        )
        duplicate = self.api.post(
            "/api/v1/quotation/view-permissions",
            payload,
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(
            QuotationViewPermission.objects.filter(
                user=self.member,
                document=asset,
                is_active=True,
            ).count(),
            1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                event_name="permissions.view_granted",
            ).count(),
            1,
        )

    def test_regular_user_receives_403_for_management_endpoints(self):
        asset = self._feishu_asset()
        membership = QuotationMembership.objects.create(
            user=self.member,
            role=QuotationMembershipRole.USER,
            assigned_by=self.admin,
        )
        permission = QuotationViewPermission.objects.create(
            user=self.member,
            target_type=QuotationViewPermissionTarget.DOCUMENT,
            document=asset,
            granted_by=self.admin,
        )
        regular_api = APIClient()
        regular_api.force_authenticate(self.member)

        requests = [
            regular_api.get("/api/v1/quotation/memberships"),
            regular_api.post(
                "/api/v1/quotation/memberships",
                {
                    "user_id": self.member.id,
                    "role": QuotationMembershipRole.USER,
                },
                format="json",
            ),
            regular_api.patch(
                f"/api/v1/quotation/memberships/{membership.id}",
                {"role": QuotationMembershipRole.ADMIN},
                format="json",
            ),
            regular_api.get("/api/v1/quotation/view-permissions"),
            regular_api.post(
                "/api/v1/quotation/view-permissions",
                {
                    "user_id": self.member.id,
                    "target_type": QuotationViewPermissionTarget.DOCUMENT,
                    "target_id": asset.id,
                },
                format="json",
            ),
            regular_api.patch(
                f"/api/v1/quotation/view-permissions/{permission.id}",
                {"expires_at": None},
                format="json",
            ),
            regular_api.delete(
                f"/api/v1/quotation/view-permissions/{permission.id}"
            ),
        ]

        self.assertTrue(
            all(response.status_code == 403 for response in requests)
        )
