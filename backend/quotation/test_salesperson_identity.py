from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role
from quotation.access import (
    can_access_quotation,
    filter_accessible_quotations,
)
from quotation.models import (
    DocumentAsset,
    Quotation,
    QuotationMembership,
    QuotationMembershipRole,
)
from quotation.services.quotation_queries import filter_quotation_salesperson


class SalespersonIdentityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="Evelyn.chee", email="evelyn@example.com",
        )
        role = Role.objects.create(
            name="Sales identity test",
            visible_features=["quotation_management"],
        )
        self.user.platform_roles.add(role)
        self.membership = QuotationMembership.objects.create(
            user=self.user, role=QuotationMembershipRole.USER,
        )
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def quote(self, name="Evelyn Chee", **fields):
        values = {
            "quote_no": f"IDENTITY-{Quotation.objects.count()}",
            "source_type": "document_import",
            "issuer_contact_name": name,
            "created_by_email": "importer@example.com",
            "quote_date": "2026-09-21",
            "currency": "USD",
        }
        values.update(fields)
        return Quotation.objects.create(**values)

    def visible_ids(self, user=None):
        return set(filter_accessible_quotations(
            user or self.user, Quotation.objects.all(),
        ).values_list("id", flat=True))

    def test_full_name_formats_match_in_list_and_detail(self):
        for name in ("Evelyn Chee", " evelyn CHEE ", "EVELYN.CHEE"):
            with self.subTest(name=name):
                quote = self.quote(name)
                self.assertIn(quote.pk, self.visible_ids())
                self.assertTrue(can_access_quotation(self.user, quote))

    def test_other_people_and_partial_names_are_not_owned(self):
        for name in ("Leon Du", "Evelyn", "Chee", "Evelyn Chee Other"):
            with self.subTest(name=name):
                quote = self.quote(name)
                self.assertNotIn(quote.pk, self.visible_ids())
                self.assertFalse(can_access_quotation(self.user, quote))

    def test_other_dotted_accounts_use_the_same_rule(self):
        user = User.objects.create_user("leon.du", email="leon@example.com")
        quote = self.quote("Leon Du")
        self.assertIn(quote.pk, self.visible_ids(user))
        self.assertNotIn(quote.pk, self.visible_ids())
        self.assertTrue(can_access_quotation(user, quote))

    def test_colliding_accounts_disable_automatic_ownership(self):
        quote = self.quote()
        exact = self.quote("Evelyn.chee")
        other = User.objects.create_user("Evelyn Chee")
        self.assertNotIn(quote.pk, self.visible_ids())
        self.assertFalse(can_access_quotation(self.user, quote))
        self.assertIn(exact.pk, self.visible_ids())
        self.assertIn(quote.pk, self.visible_ids(other))
        self.assertNotIn(exact.pk, self.visible_ids(other))

    def test_inactive_accounts_also_reserve_their_identity(self):
        User.objects.create_user("evelyn chee", is_active=False)
        quote = self.quote()
        self.assertNotIn(quote.pk, self.visible_ids())
        self.assertFalse(can_access_quotation(self.user, quote))

    def test_self_edited_names_do_not_grant_access(self):
        self.user.first_name = "Leon"
        self.user.last_name = "Du"
        self.user.save(update_fields=["first_name", "last_name"])
        quote = self.quote("Leon Du")
        self.assertNotIn(quote.pk, self.visible_ids())
        self.assertFalse(can_access_quotation(self.user, quote))

    def test_archived_quotes_stay_hidden(self):
        quote = self.quote(archived_at=timezone.now())
        self.assertNotIn(quote.pk, self.visible_ids())
        self.assertFalse(can_access_quotation(self.user, quote))

    def test_admin_still_sees_all_non_archived_quotes(self):
        own = self.quote()
        other = self.quote("Leon Du")
        self.membership.role = QuotationMembershipRole.ADMIN
        self.membership.save(update_fields=["role"])
        self.assertEqual(self.visible_ids(), {own.pk, other.pk})

    def test_empty_sales_owner_uses_full_folder_identity(self):
        quote = self.quote("")
        DocumentAsset.objects.create(
            quotation=quote, doc_type="pdf", source="feishu",
            file_name="identity.pdf", storage_key="identity.pdf",
            feishu_folder_path=[{"name": "Evelyn Chee"}],
        )
        self.assertIn(quote.pk, self.visible_ids())
        self.assertTrue(can_access_quotation(self.user, quote))

    def test_api_pagination_dates_and_salesperson_are_consistent(self):
        for _ in range(12):
            self.quote()
        self.quote("Leon Du")
        self.quote(quote_date="2025-09-21")
        response = self.api.get("/api/v1/quotation/quotations", {
            "salesperson": " evelyn.chee ", "created_from": "2026-09-01",
            "created_to": "2026-09-30", "page": 2, "page_size": 10,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 12)
        self.assertEqual(len(response.data["items"]), 2)
        self.assertEqual(response.data["total_pages"], 2)

    def test_web_dashboard_list_and_detail_share_visibility(self):
        quote = self.quote()
        other = self.quote("Leon Du")
        listing = self.api.get("/api/v1/quotation/quotations")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["total"], 1)
        detail = self.api.get(f"/api/v1/quotation/quotations/{quote.pk}")
        self.assertEqual(detail.status_code, 200)
        denied = self.api.get(f"/api/v1/quotation/quotations/{other.pk}")
        self.assertEqual(denied.status_code, 403)
        dashboard = self.api.get("/api/v1/quotation/dashboard/overview", {
            "currency": "USD", "date_from": "2026-09",
            "date_to": "2026-09",
        })
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.data["summary"]["month_quote_count"], 1)
        self.assertEqual(len(dashboard.data["recent"]["items"]), 1)

    def test_structured_salesperson_filter_never_matches_partial_names(self):
        self.quote()
        self.assertEqual(filter_quotation_salesperson(
            Quotation.objects.all(), " evelyn.chee ",
        ).count(), 1)
        self.assertEqual(filter_quotation_salesperson(
            Quotation.objects.all(), "Evelyn",
        ).count(), 0)
