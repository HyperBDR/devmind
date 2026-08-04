from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from llm_ops.models import (
    LLMModel,
    LLMProvider,
    ModelPriceItem,
    ProcurementChannel,
    ResaleListing,
    ResaleListingPriceRevision,
    ResalePlatform,
)
from llm_ops.services import (
    approve_resale_listing_price_revision,
    create_resale_listing_price_revision,
    sync_resale_listing_flat_revision,
)
from rest_framework.test import APIClient


class ResaleListingPriceRevisionTests(TestCase):
    def setUp(self):
        provider = LLMProvider.objects.create(
            name="OpenAI",
            code="openai-revisions",
        )
        self.model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5-revisions",
        )
        self.channel = ProcurementChannel.objects.create(
            name="Direct Revisions",
            code="direct-revisions",
        )
        self.platform = ResalePlatform.objects.create(
            name="Revision Platform",
            code="revision-platform",
            currency="USD",
        )
        self.listing = ResaleListing.objects.create(
            platform=self.platform,
            model=self.model,
            channel=self.channel,
            currency="USD",
            retail_input_price_per_million=Decimal("1.25"),
            retail_output_price_per_million=Decimal("5.00"),
            retail_cache_input_price_per_million=Decimal("0.50"),
        )

    def _tiered_items(self):
        return [
            {
                "dimension": ModelPriceItem.DIMENSION_TEXT_INPUT,
                "billing_unit": ModelPriceItem.UNIT_PER_1M_TOKENS,
                "tier_type": ModelPriceItem.TIER_USAGE_RANGE,
                "tier_start": Decimal("0"),
                "tier_end": Decimal("1000000"),
                "unit_price": Decimal("1.25"),
                "spec": {"tier_metric": "tokens_per_request"},
            },
            {
                "dimension": ModelPriceItem.DIMENSION_TEXT_INPUT,
                "billing_unit": ModelPriceItem.UNIT_PER_1M_TOKENS,
                "tier_type": ModelPriceItem.TIER_USAGE_RANGE,
                "tier_start": Decimal("1000000"),
                "tier_end": None,
                "unit_price": Decimal("0.95"),
                "spec": {"tier_metric": "tokens_per_request"},
            },
        ]

    def test_creates_one_revision_with_all_tier_items(self):
        revision = create_resale_listing_price_revision(
            listing=self.listing,
            currency="USD",
            status=ResaleListingPriceRevision.STATUS_DRAFT,
            items=self._tiered_items(),
        )

        self.assertEqual(revision.version, 1)
        self.assertEqual(revision.items.count(), 2)
        self.assertEqual(
            list(revision.items.values_list("tier_start", flat=True)),
            [Decimal("0.000000"), Decimal("1000000.000000")],
        )

    def test_revision_creation_rolls_back_when_any_item_fails(self):
        with mock.patch(
            "llm_ops.services.ResaleListingPriceItem.objects.bulk_create",
            side_effect=RuntimeError("item write failed"),
        ):
            with self.assertRaisesMessage(RuntimeError, "item write failed"):
                create_resale_listing_price_revision(
                    listing=self.listing,
                    currency="USD",
                    status=ResaleListingPriceRevision.STATUS_DRAFT,
                    items=self._tiered_items(),
                )

        self.assertFalse(
            ResaleListingPriceRevision.objects.filter(
                listing=self.listing,
            ).exists()
        )

    def test_rejects_revision_without_currency(self):
        with self.assertRaisesMessage(ValueError, "currency is required"):
            create_resale_listing_price_revision(
                listing=self.listing,
                currency="",
                status=ResaleListingPriceRevision.STATUS_DRAFT,
                items=self._tiered_items(),
            )

    def test_rejects_revision_dimension_outside_text_scope(self):
        items = self._tiered_items()
        items[0]["dimension"] = ModelPriceItem.DIMENSION_IMAGE_OUTPUT

        with self.assertRaisesMessage(ValueError, "Unsupported dimension"):
            create_resale_listing_price_revision(
                listing=self.listing,
                currency="USD",
                status=ResaleListingPriceRevision.STATUS_DRAFT,
                items=items,
            )

    def test_submitted_revision_and_items_are_immutable(self):
        revision = create_resale_listing_price_revision(
            listing=self.listing,
            currency="USD",
            status=ResaleListingPriceRevision.STATUS_SUBMITTED,
            items=self._tiered_items(),
        )
        item = revision.items.first()

        revision.currency = "CNY"
        with self.assertRaises(ValidationError):
            revision.save()

        item.unit_price = Decimal("9.99")
        with self.assertRaises(ValidationError):
            item.save()

        with self.assertRaises(ValidationError):
            item.delete()

    def test_submitted_item_cannot_be_moved_to_a_draft_revision(self):
        submitted = create_resale_listing_price_revision(
            listing=self.listing,
            currency="USD",
            status=ResaleListingPriceRevision.STATUS_SUBMITTED,
            items=self._tiered_items(),
        )
        draft = create_resale_listing_price_revision(
            listing=self.listing,
            currency="USD",
            status=ResaleListingPriceRevision.STATUS_DRAFT,
            items=self._tiered_items(),
        )
        item = submitted.items.first()

        item.revision = draft
        with self.assertRaises(ValidationError):
            item.save()

        with self.assertRaises(ValidationError):
            item.delete()
        self.assertEqual(submitted.items.count(), 2)

    def test_changed_submitted_flat_price_creates_new_revision(self):
        first = sync_resale_listing_flat_revision(
            self.listing,
            status=ResaleListingPriceRevision.STATUS_SUBMITTED,
        )
        self.listing.retail_input_price_per_million = Decimal("1.50")
        self.listing.save(
            update_fields=["retail_input_price_per_million", "updated_at"]
        )

        second = sync_resale_listing_flat_revision(
            self.listing,
            status=ResaleListingPriceRevision.STATUS_SUBMITTED,
        )

        self.assertEqual(first.version, 1)
        self.assertEqual(second.version, 2)
        self.assertEqual(first.status, first.STATUS_SUBMITTED)
        self.assertEqual(
            self.listing.pending_price_revision_id,
            second.id,
        )
        self.assertEqual(
            second.items.get(
                dimension=ModelPriceItem.DIMENSION_TEXT_INPUT
            ).unit_price,
            Decimal("1.500000"),
        )

    def test_approval_replaces_current_and_supersedes_previous(self):
        current = sync_resale_listing_flat_revision(
            self.listing,
            status=ResaleListingPriceRevision.STATUS_SUBMITTED,
        )
        approve_resale_listing_price_revision(self.listing)
        self.listing.retail_output_price_per_million = Decimal("6.00")
        self.listing.save(
            update_fields=["retail_output_price_per_million", "updated_at"]
        )
        pending = sync_resale_listing_flat_revision(
            self.listing,
            status=ResaleListingPriceRevision.STATUS_SUBMITTED,
        )

        approved = approve_resale_listing_price_revision(self.listing)

        current.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertEqual(current.status, current.STATUS_SUPERSEDED)
        self.assertEqual(approved.id, pending.id)
        self.assertEqual(approved.status, approved.STATUS_APPROVED)
        self.assertEqual(
            self.listing.current_price_revision_id,
            pending.id,
        )
        self.assertIsNone(self.listing.pending_price_revision_id)


class ResaleListingPriceRevisionAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username="revision-operator",
            password="secret",
            is_staff=True,
        )
        self.client.force_authenticate(self.user)
        provider = LLMProvider.objects.create(
            name="OpenAI API Revisions",
            code="openai-api-revisions",
        )
        self.model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5 API Revisions",
            code="gpt-5-api-revisions",
        )
        self.channel = ProcurementChannel.objects.create(
            name="API Revision Channel",
            code="api-revision-channel",
        )
        self.platform = ResalePlatform.objects.create(
            name="API Revision Platform",
            code="api-revision-platform",
            currency="USD",
        )

    def _submit(self, input_price):
        return self.client.post(
            reverse("resale-listing-bulk-upsert"),
            {
                "items": [
                    {
                        "platform": self.platform.id,
                        "model": self.model.id,
                        "channel": self.channel.id,
                        "retail_input_price_per_million": input_price,
                        "retail_output_price_per_million": "5.00",
                        "retail_cache_input_price_per_million": "0.50",
                    }
                ]
            },
            format="json",
        )

    def _transition(self, listing, action):
        return self.client.post(
            reverse("resale-listing-bulk-transition"),
            {
                "platform": self.platform.id,
                "listings": [listing.id],
                "action": action,
            },
            format="json",
        )

    def test_submissions_and_approval_bind_exact_revisions(self):
        first_response = self._submit("1.25")

        self.assertEqual(first_response.status_code, 200)
        listing = ResaleListing.objects.get(
            platform=self.platform,
            model=self.model,
            channel=self.channel,
        )
        first = listing.pending_price_revision
        self.assertEqual(first.version, 1)
        self.assertEqual(first.status, first.STATUS_SUBMITTED)
        self.assertEqual(first.items.count(), 3)
        self.assertIsNone(listing.current_price_revision_id)

        approval_response = self._transition(listing, "confirm_publish")

        self.assertEqual(approval_response.status_code, 200)
        listing.refresh_from_db()
        first.refresh_from_db()
        self.assertEqual(first.status, first.STATUS_APPROVED)
        self.assertEqual(listing.current_price_revision_id, first.id)
        self.assertIsNone(listing.pending_price_revision_id)

        second_response = self._submit("1.50")

        self.assertEqual(second_response.status_code, 200)
        listing.refresh_from_db()
        second = listing.pending_price_revision
        self.assertEqual(second.version, 2)
        self.assertEqual(second.status, second.STATUS_SUBMITTED)
        self.assertEqual(listing.current_price_revision_id, first.id)
        self.assertEqual(
            listing.workflow_status,
            ResaleListing.WORKFLOW_PENDING_UPDATE,
        )

        third_response = self._submit("1.75")

        self.assertEqual(third_response.status_code, 200)
        listing.refresh_from_db()
        second.refresh_from_db()
        third = listing.pending_price_revision
        self.assertEqual(third.version, 3)
        self.assertEqual(third.status, third.STATUS_SUBMITTED)
        self.assertEqual(second.status, second.STATUS_SUPERSEDED)
        self.assertEqual(listing.current_price_revision_id, first.id)
        self.assertEqual(listing.pending_price_revision_id, third.id)
