from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from llm_ops.models import (
    AuditLog,
    ChannelModelPrice,
    LLMModel,
    LLMProvider,
    ModelPriceItem,
    PriceCollectionSource,
    ProcurementChannel,
    ResaleListing,
    ResaleListingPriceRevision,
    ResalePlatform,
)


class ResalePriceRevisionAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username="tier-price-operator",
            password="secret",
            is_staff=True,
        )
        self.client.force_authenticate(self.user)
        self.provider = LLMProvider.objects.create(
            name="OpenAI Tier API",
            code="openai-tier-api",
        )
        self.model = LLMModel.objects.create(
            provider=self.provider,
            name="GPT Tier API",
            code="gpt-tier-api",
            currency="USD",
        )
        self.channel = ProcurementChannel.objects.create(
            name="Tier API Channel",
            code="tier-api-channel",
            currency="USD",
            settlement_ratio=Decimal("1"),
        )
        self.source = PriceCollectionSource.objects.create(
            name="Tier API Official",
            slug="tier-api-official",
            provider=self.provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            currency="USD",
        )
        self.channel_price = ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
            price_source=self.source,
            is_listed=True,
        )
        self.cost_items = []
        for dimension, low_price, high_price in (
            (ModelPriceItem.DIMENSION_TEXT_INPUT, "1", "0.8"),
            (ModelPriceItem.DIMENSION_TEXT_OUTPUT, "2", "1.6"),
        ):
            for price, start, end in (
                (low_price, "0", "100"),
                (high_price, "100", None),
            ):
                self.cost_items.append(
                    ModelPriceItem.objects.create(
                        provider=self.provider,
                        model=self.model,
                        meta_model=self.model.meta_model,
                        source=self.source,
                        dimension=dimension,
                        billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
                        currency="USD",
                        unit_price=Decimal(price),
                        tier_type=ModelPriceItem.TIER_USAGE_RANGE,
                        tier_start=Decimal(start),
                        tier_end=(Decimal(end) if end is not None else None),
                        price_fingerprint=f"{dimension}-{start}",
                        is_current=True,
                    )
                )
        self.platform = ResalePlatform.objects.create(
            name="Tier API Platform",
            code="tier-api-platform",
            currency="USD",
            fee_rate=Decimal("0"),
            service_fee_rate=Decimal("0"),
            tax_rate=Decimal("0"),
            settlement_rate=Decimal("1"),
            yield_warning=Decimal("0.2"),
            auto_approve_max_margin_rate=Decimal("200"),
        )
        self.listing = ResaleListing.objects.create(
            platform=self.platform,
            model=self.model,
            channel=self.channel,
            currency="USD",
            retail_input_price_per_million=Decimal("2"),
            retail_output_price_per_million=Decimal("4"),
        )

    def retail_items(self, *, input_high="1.6"):
        rows = []
        for dimension, low_price, high_price in (
            (
                ModelPriceItem.DIMENSION_TEXT_INPUT,
                "2",
                input_high,
            ),
            (ModelPriceItem.DIMENSION_TEXT_OUTPUT, "4", "3.2"),
        ):
            for price, start, end in (
                (low_price, "0", "100"),
                (high_price, "100", None),
            ):
                rows.append(
                    {
                        "dimension": dimension,
                        "billing_unit": (ModelPriceItem.UNIT_PER_1M_TOKENS),
                        "currency": "USD",
                        "unit_price": price,
                        "tier_type": ModelPriceItem.TIER_USAGE_RANGE,
                        "tier_start": start,
                        "tier_end": end,
                        "spec": {},
                    }
                )
        return rows

    def save_draft(self, **overrides):
        payload = {
            "currency": "USD",
            "items": self.retail_items(),
        }
        payload.update(overrides)
        return self.client.put(
            reverse(
                "resale-listing-price-draft",
                args=[self.listing.id],
            ),
            payload,
            format="json",
        )

    def flat_items(self):
        return [
            {
                "dimension": ModelPriceItem.DIMENSION_TEXT_INPUT,
                "billing_unit": ModelPriceItem.UNIT_PER_1M_TOKENS,
                "currency": "USD",
                "unit_price": "2",
                "tier_type": ModelPriceItem.TIER_FLAT,
                "tier_start": None,
                "tier_end": None,
                "spec": {},
            },
            {
                "dimension": ModelPriceItem.DIMENSION_TEXT_OUTPUT,
                "billing_unit": ModelPriceItem.UNIT_PER_1M_TOKENS,
                "currency": "USD",
                "unit_price": "4",
                "tier_type": ModelPriceItem.TIER_FLAT,
                "tier_start": None,
                "tier_end": None,
                "spec": {},
            },
        ]

    def mixed_items(self):
        tiered_input = [
            item
            for item in self.retail_items()
            if item["dimension"] == ModelPriceItem.DIMENSION_TEXT_INPUT
        ]
        flat_output = [
            item
            for item in self.flat_items()
            if item["dimension"] == ModelPriceItem.DIMENSION_TEXT_OUTPUT
        ]
        return tiered_input + flat_output

    def submit_revision(self, revision_id):
        return self.client.post(
            reverse(
                "resale-listing-submit-price-revision",
                args=[self.listing.id],
            ),
            {"revision_id": revision_id},
            format="json",
        )

    def test_price_draft_requires_authentication(self):
        client = APIClient()

        response = client.put(
            reverse(
                "resale-listing-price-draft",
                args=[self.listing.id],
            ),
            {"currency": "USD", "items": self.retail_items()},
            format="json",
        )

        self.assertIn(response.status_code, {401, 403})

    def test_price_draft_is_atomic_and_rejects_stale_revision(self):
        created = self.save_draft()
        self.assertEqual(created.status_code, 200, created.data)

        stale = self.save_draft(
            expected_revision_id=created.data["id"] + 1000,
        )

        self.assertEqual(stale.status_code, 409)
        self.assertEqual(
            stale.data["code"],
            "resale_price.revision_conflict",
        )
        self.assertEqual(self.listing.price_revisions.count(), 1)

    def test_price_draft_returns_stable_tier_validation_code(self):
        items = self.retail_items()
        items[1]["tier_start"] = "101"

        response = self.save_draft(items=items)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "price_table_gap")

    def test_listing_defaults_to_flat_pricing_format(self):
        listing = ResaleListing.objects.get(pk=self.listing.pk)

        self.assertEqual(
            listing.pricing_format,
            ResaleListing.PRICING_FORMAT_FLAT,
        )

    def test_saving_tiered_draft_sets_usage_range_format(self):
        response = self.save_draft()
        self.assertEqual(response.status_code, 200, response.data)

        listing = ResaleListing.objects.get(pk=self.listing.pk)
        self.assertEqual(
            listing.pricing_format,
            ResaleListing.PRICING_FORMAT_USAGE_RANGE,
        )

    def test_saving_flat_draft_sets_flat_format(self):
        response = self.save_draft(items=self.flat_items())
        self.assertEqual(response.status_code, 200, response.data)

        listing = ResaleListing.objects.get(pk=self.listing.pk)
        self.assertEqual(
            listing.pricing_format,
            ResaleListing.PRICING_FORMAT_FLAT,
        )

    def test_saving_mixed_draft_sets_mixed_format(self):
        response = self.save_draft(items=self.mixed_items())
        self.assertEqual(response.status_code, 200, response.data)

        listing = ResaleListing.objects.get(pk=self.listing.pk)
        self.assertEqual(
            listing.pricing_format,
            ResaleListing.PRICING_FORMAT_MIXED,
        )

    def test_preview_returns_cost_fee_and_interval_profitability(self):
        draft = self.save_draft()

        response = self.client.post(
            reverse(
                "resale-listing-price-preview",
                args=[self.listing.id],
            ),
            {"revision_id": draft.data["id"]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["cost_schedule"]), 4)
        self.assertEqual(len(response.data["retail_schedule"]), 4)
        self.assertEqual(len(response.data["profitability"]["intervals"]), 4)
        self.assertIn("fee_rate", response.data["fee_config"])
        self.assertIn("minimum_gross_margin", response.data["profitability"])
        self.assertIn(
            "minimum_gross_margin_interval",
            response.data["profitability"],
        )
        self.assertIn(
            "platform_fee",
            response.data["profitability"]["intervals"][0],
        )
        self.assertTrue(response.data["approval"]["eligible"])

    def test_submit_snapshots_auto_approval_and_publish_revision(self):
        draft = self.save_draft()

        submitted = self.submit_revision(draft.data["id"])

        self.assertEqual(submitted.status_code, 200, submitted.data)
        revision = ResaleListingPriceRevision.objects.get(pk=draft.data["id"])
        self.assertEqual(
            revision.status,
            ResaleListingPriceRevision.STATUS_APPROVED,
        )
        self.assertTrue(revision.decision_snapshot)
        self.assertTrue(revision.decision_fingerprint)
        self.assertEqual(revision.submitted_by, self.user)
        self.listing.refresh_from_db()
        self.assertEqual(
            self.listing.workflow_status,
            ResaleListing.WORKFLOW_PENDING_PUBLISH,
        )

        published = self.client.post(
            reverse("resale-listing-bulk-transition"),
            {
                "platform": self.platform.id,
                "listings": [self.listing.id],
                "action": "confirm_publish",
            },
            format="json",
        )

        self.assertEqual(published.status_code, 200, published.data)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.current_price_revision, revision)
        self.assertEqual(self.listing.published_price_revision, revision)
        self.assertIsNone(self.listing.pending_price_revision)
        audit = AuditLog.objects.filter(
            target_id=str(self.listing.id),
            metadata__workflow_action="confirm_publish",
        ).latest("created_at")
        self.assertEqual(audit.metadata["price_revision_id"], revision.id)

    def test_edit_after_approval_creates_unapproved_new_revision(self):
        draft = self.save_draft()
        submitted = self.submit_revision(draft.data["id"])
        self.assertEqual(submitted.status_code, 200, submitted.data)
        approved = ResaleListingPriceRevision.objects.get(pk=draft.data["id"])
        decision_fingerprint = approved.decision_fingerprint
        self.listing.workflow_status = ResaleListing.WORKFLOW_UPDATE_DRAFT
        self.listing.save(update_fields=["workflow_status"])

        replacement = self.save_draft(
            items=self.retail_items(input_high="1.7"),
        )

        self.assertEqual(replacement.status_code, 200, replacement.data)
        self.assertNotEqual(replacement.data["id"], approved.id)
        self.assertEqual(replacement.data["status"], "draft")
        approved.refresh_from_db()
        self.assertEqual(approved.decision_fingerprint, decision_fingerprint)
        self.assertEqual(approved.status, "approved")

    def test_submit_rejects_stale_cost_with_stable_code(self):
        ModelPriceItem.objects.filter(
            id__in=[item.id for item in self.cost_items]
        ).update(effective_from=timezone.now() - timedelta(days=31))
        draft = self.save_draft()

        response = self.submit_revision(draft.data["id"])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "resale_price.cost_stale")

    def test_submit_rejects_lowest_tier_below_server_margin_policy(self):
        draft = self.save_draft(
            items=self.retail_items(input_high="0.81"),
        )

        response = self.submit_revision(draft.data["id"])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["code"],
            "resale_price.minimum_margin_below_warning",
        )

    def test_manual_approval_is_bound_to_submitted_revision(self):
        self.platform.auto_approve_max_margin_rate = Decimal("0")
        self.platform.save(update_fields=["auto_approve_max_margin_rate"])
        draft = self.save_draft()

        submitted = self.submit_revision(draft.data["id"])

        self.assertEqual(submitted.status_code, 200, submitted.data)
        revision = ResaleListingPriceRevision.objects.get(pk=draft.data["id"])
        self.assertEqual(revision.status, "submitted")
        self.assertIsNone(revision.approved_at)

        confirmed = self.client.post(
            reverse("resale-listing-bulk-transition"),
            {
                "platform": self.platform.id,
                "listings": [self.listing.id],
                "action": "confirm_publish",
            },
            format="json",
        )

        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        revision.refresh_from_db()
        self.assertEqual(revision.status, "approved")
        self.assertEqual(revision.approved_by, self.user)
        self.assertIsNotNone(revision.approved_at)

    def test_revision_history_reconstructs_decision_snapshot(self):
        draft = self.save_draft()
        submitted = self.submit_revision(draft.data["id"])
        self.assertEqual(submitted.status_code, 200, submitted.data)

        response = self.client.get(
            reverse(
                "resale-listing-price-revisions",
                args=[self.listing.id],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["pending_revision_id"], draft.data["id"]
        )
        snapshot = response.data["revisions"][0]["decision_snapshot"]
        self.assertIn("cost_schedule", snapshot)
        self.assertIn("retail_schedule", snapshot)
        self.assertIn("exchange_rate", snapshot)
        self.assertIn("fee_config", snapshot)
        self.assertIn("profitability", snapshot)
