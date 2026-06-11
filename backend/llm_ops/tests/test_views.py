from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from llm_ops.models import (
    ChannelModelPrice,
    ChannelModelPriceHistory,
    ChannelPriceItem,
    CollectedModelPriceSnapshot,
    LLMModel,
    LLMProvider,
    ModelPriceItem,
    PriceCollectionRun,
    PriceCollectionSource,
    ProcurementChannel,
    ResaleListing,
    ResaleListingExclusion,
    ResaleListingPriceHistory,
    ResalePlatform,
)


class LLMOpsViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username="ops",
            password="secret",
            is_staff=True,
        )
        self.client.force_authenticate(self.user)

    @patch("llm_ops.views.sync_yunce_model_prices")
    def test_yunce_collection_endpoint_returns_sync_stats(self, mock_sync):
        mock_sync.return_value = {
            "models": 3,
            "created": 2,
            "updated": 1,
            "skipped": 0,
        }

        response = self.client.post(
            reverse("llm-ops-yunce-collect"),
            {
                "username": "user",
                "password": "secret",
                "base_url": "https://llm.guohe-sh.com/admin/api",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["models"], 3)
        mock_sync.assert_called_once_with(
            username="user",
            password="secret",
            base_url="https://llm.guohe-sh.com/admin/api",
        )

    @patch("llm_ops.views.sync_yunce_model_prices")
    def test_yunce_collection_endpoint_accepts_source_id(self, mock_sync):
        source = PriceCollectionSource.objects.create(
            name="Yunce Production",
            slug="yunce-production",
            source_type=PriceCollectionSource.SOURCE_TYPE_YUNCE,
            endpoint_url="https://example.com/admin/api",
        )
        mock_sync.return_value = {
            "models": 1,
            "created": 1,
            "updated": 0,
            "skipped": 0,
        }

        response = self.client.post(
            reverse("llm-ops-yunce-collect"),
            {
                "source_id": source.id,
                "username": "user",
                "password": "secret",
                "base_url": "https://example.com/admin/api",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        mock_sync.assert_called_once_with(
            username="user",
            password="secret",
            source=source,
            base_url="https://example.com/admin/api",
        )

    def test_collection_source_can_be_deleted(self):
        source = PriceCollectionSource.objects.create(
            name="Manual Source",
            slug="manual-source",
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_MANUAL,
        )

        response = self.client.delete(
            reverse("collection-source-detail", args=[source.id]),
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            PriceCollectionSource.objects.filter(id=source.id).exists()
        )

    def test_model_price_item_can_be_updated(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        source = PriceCollectionSource.objects.create(
            name="Manual Source",
            slug="manual-source",
            provider=provider,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_MANUAL,
            currency="USD",
        )
        model = LLMModel.objects.create(
            provider=provider,
            source=source,
            name="GPT-4o mini",
            code="gpt-4o-mini",
        )
        item = ModelPriceItem.objects.create(
            provider=provider,
            model=model,
            source=source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price="0.150000",
            price_fingerprint="manual-input",
            spec={},
        )

        response = self.client.patch(
            reverse("model-price-item-detail", args=[item.id]),
            {
                "unit_price": "0.120000",
                "currency": "CNY",
                "spec": {"note": "manual correction"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(str(item.unit_price), "0.120000")
        self.assertEqual(item.currency, "CNY")
        self.assertEqual(item.spec["note"], "manual correction")

    def test_model_price_item_can_be_deleted(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-4o mini",
            code="gpt-4o-mini",
        )
        item = ModelPriceItem.objects.create(
            provider=provider,
            model=model,
            dimension=ModelPriceItem.DIMENSION_TEXT_OUTPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price="0.600000",
            price_fingerprint="manual-output",
        )

        response = self.client.delete(
            reverse("model-price-item-detail", args=[item.id]),
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(ModelPriceItem.objects.filter(id=item.id).exists())

    @patch("llm_ops.views.sync_official_provider_model_prices")
    def test_collection_source_collects_official_provider(self, mock_sync):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        source = PriceCollectionSource.objects.create(
            name="OpenAI Official",
            slug="openai-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://openai.com/api/pricing/",
            is_enabled=True,
            updates_model_prices=True,
        )
        mock_sync.return_value = {
            "models": 2,
            "created": 0,
            "updated": 2,
            "skipped": 0,
            "changed": 1,
            "unchanged": 1,
        }

        response = self.client.post(
            reverse("collection-source-collect", args=[source.id]),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["models"], 2)
        mock_sync.assert_called_once_with(
            provider=provider,
            source=source,
            verify_source=True,
        )

    @patch("llm_ops.views.sync_official_provider_model_prices")
    def test_collection_source_collect_rejects_disabled_source(
        self,
        mock_sync,
    ):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        source = PriceCollectionSource.objects.create(
            name="OpenAI Official",
            slug="openai-official-disabled",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            is_enabled=False,
            updates_model_prices=True,
        )

        response = self.client.post(
            reverse("collection-source-collect", args=[source.id]),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "Price collection source is disabled.",
        )
        mock_sync.assert_not_called()

    def test_collected_price_snapshot_list_returns_normalized_rows(self):
        source = PriceCollectionSource.objects.create(
            name="Yunce",
            slug="yunce",
            source_type=PriceCollectionSource.SOURCE_TYPE_YUNCE,
        )
        run = PriceCollectionRun.objects.create(
            source=source,
            status=PriceCollectionRun.STATUS_SUCCEEDED,
            collected_count=1,
        )
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-4o",
            code="gpt-4o",
        )
        CollectedModelPriceSnapshot.objects.create(
            source=source,
            run=run,
            provider=provider,
            model=model,
            source_platform_id="1",
            source_model_id="gpt-4o",
            source_model_name="GPT-4o",
            source_model_type="Text",
            source_provider_name="OpenAI",
            currency="USD",
            normalized_price_rows=[
                {
                    "kind": "text_token",
                    "values": {
                        "input_price": 2.5,
                        "output_price": 10,
                    },
                    "raw": {},
                }
            ],
        )

        response = self.client.get(
            reverse("collected-price-snapshot-list"),
            {"source_model_type": "Text"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["results"][0]["source_model_name"],
            "GPT-4o",
        )
        self.assertEqual(
            response.data["results"][0]["normalized_price_rows"][0]["kind"],
            "text_token",
        )

    def test_summary_only_uses_configured_channel_models(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Real Resource",
            code="real-resource",
        )

        response = self.client.get(reverse("llm-ops-summary"))

        self.assertEqual(response.status_code, 200)
        row = response.data["procurement"][0]
        self.assertIsNone(row["best_channel"])
        self.assertEqual(row["options"], [])

        ChannelModelPrice.objects.create(channel=channel, model=model)

        response = self.client.get(reverse("llm-ops-summary"))

        row = response.data["procurement"][0]
        self.assertEqual(row["best_channel"]["channel_name"], "Real Resource")
        self.assertEqual(row["best_channel"]["original_currency"], "USD")

    def test_channel_model_price_bulk_upsert_updates_existing_rows(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Real Resource",
            code="real-resource",
        )
        source = PriceCollectionSource.objects.create(
            name="Supplier A",
            slug="supplier-a",
            provider=provider,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
        )
        ChannelModelPrice.objects.create(
            channel=channel,
            model=model,
            settlement_ratio="0.9",
        )

        response = self.client.post(
            reverse("channel-model-price-bulk-upsert"),
            {
                "items": [
                    {
                        "channel": channel.id,
                        "model": model.id,
                        "price_source": source.id,
                        "is_listed": True,
                        "settlement_ratio": "0.55",
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ChannelModelPrice.objects.count(), 1)
        self.assertEqual(
            str(ChannelModelPrice.objects.get().settlement_ratio),
            "0.5500",
        )
        self.assertEqual(ChannelModelPrice.objects.get().price_source, source)
        self.assertEqual(ChannelModelPriceHistory.objects.count(), 1)
        history = ChannelModelPriceHistory.objects.get()
        self.assertEqual(history.price_source, source)
        self.assertEqual(
            history.input_price_per_million,
            model.input_price_per_million,
        )

    def test_channel_model_price_bulk_upsert_syncs_price_items(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Real Resource",
            code="real-resource",
        )
        ModelPriceItem.objects.create(
            provider=provider,
            model=model,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price="2.5",
            price_fingerprint="official-input",
        )

        response = self.client.post(
            reverse("channel-model-price-bulk-upsert"),
            {
                "items": [
                    {
                        "channel": channel.id,
                        "model": model.id,
                        "is_listed": True,
                        "settlement_ratio": "0.5",
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        item = ChannelPriceItem.objects.get()
        self.assertEqual(str(item.unit_price), "1.250000")
        self.assertEqual(item.comparison_status, "below_official")

    def test_channel_model_price_sync_price_items_action(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Real Resource",
            code="real-resource",
            settlement_ratio="0.5",
        )
        ChannelModelPrice.objects.create(
            channel=channel,
            model=model,
            is_listed=True,
        )
        ModelPriceItem.objects.create(
            provider=provider,
            model=model,
            dimension=ModelPriceItem.DIMENSION_TEXT_OUTPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price="10",
            price_fingerprint="official-output",
        )

        response = self.client.post(
            reverse("channel-model-price-sync-price-items"),
            {"channel": channel.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["models"], 1)
        self.assertEqual(response.data["price_items"], 1)
        self.assertEqual(ChannelPriceItem.objects.count(), 1)

    def test_channel_model_price_rejects_negative_custom_price(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Real Resource",
            code="real-resource",
        )

        response = self.client.post(
            reverse("channel-model-price-list"),
            {
                "channel": channel.id,
                "model": model.id,
                "custom_input_price_per_million": "-1",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_resale_listing_bulk_replace_deactivates_previous_listings(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        old_channel = ProcurementChannel.objects.create(
            name="Old Channel",
            code="old-channel",
        )
        best_channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        ResaleListing.objects.create(
            platform=platform,
            model=model,
            channel=old_channel,
            retail_input_price_per_million="2.0",
            retail_output_price_per_million="4.0",
        )

        response = self.client.post(
            reverse("resale-listing-bulk-replace"),
            {
                "items": [
                    {
                        "platform": platform.id,
                        "model": model.id,
                        "channel": best_channel.id,
                        "display_name": "GPT-5",
                        "retail_input_price_per_million": "1.2",
                        "retail_output_price_per_million": "2.4",
                        "is_active": True,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        old_listing = ResaleListing.objects.get(channel=old_channel)
        new_listing = ResaleListing.objects.get(channel=best_channel)
        self.assertFalse(old_listing.is_active)
        self.assertTrue(new_listing.is_active)
        self.assertEqual(ResaleListingPriceHistory.objects.count(), 2)

    def test_resale_listing_bulk_upsert_keeps_previous_listings_active(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        old_channel = ProcurementChannel.objects.create(
            name="Old Channel",
            code="old-channel",
        )
        best_channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        ResaleListing.objects.create(
            platform=platform,
            model=model,
            channel=old_channel,
            retail_input_price_per_million="2.0",
            retail_output_price_per_million="4.0",
        )

        response = self.client.post(
            reverse("resale-listing-bulk-upsert"),
            {
                "items": [
                    {
                        "platform": platform.id,
                        "model": model.id,
                        "channel": best_channel.id,
                        "display_name": "GPT-5",
                        "retail_input_price_per_million": "1.2",
                        "retail_output_price_per_million": "2.4",
                        "is_active": True,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        old_listing = ResaleListing.objects.get(channel=old_channel)
        new_listing = ResaleListing.objects.get(channel=best_channel)
        self.assertTrue(old_listing.is_active)
        self.assertTrue(new_listing.is_active)
        self.assertEqual(ResaleListingPriceHistory.objects.count(), 1)

    def test_resale_listing_bulk_upsert_allows_channel_after_auto_listing(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        ResaleListing.objects.create(
            platform=platform,
            model=model,
            channel=None,
            retail_input_price_per_million="2.0",
            retail_output_price_per_million="4.0",
            is_active=False,
        )

        response = self.client.post(
            reverse("resale-listing-bulk-upsert"),
            {
                "items": [
                    {
                        "platform": platform.id,
                        "model": model.id,
                        "channel": channel.id,
                        "display_name": "GPT-5",
                        "retail_input_price_per_million": "1.2",
                        "retail_output_price_per_million": "2.4",
                        "is_active": True,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ResaleListing.objects.get(
                platform=platform,
                model=model,
                channel=channel,
            ).is_active
        )

    def test_resale_listing_bulk_upsert_restores_removed_model(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        ResaleListingExclusion.objects.create(
            platform=platform,
            model=model,
            reason="Hidden",
        )

        response = self.client.post(
            reverse("resale-listing-bulk-upsert"),
            {
                "items": [
                    {
                        "platform": platform.id,
                        "model": model.id,
                        "channel": channel.id,
                        "display_name": "GPT-5",
                        "retail_input_price_per_million": "1.2",
                        "retail_output_price_per_million": "2.4",
                        "is_active": True,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            ResaleListingExclusion.objects.filter(
                platform=platform,
                model=model,
            ).exists()
        )

    def test_resale_listing_bulk_replace_allows_channel_after_auto_listing(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        ResaleListing.objects.create(
            platform=platform,
            model=model,
            channel=None,
            retail_input_price_per_million="2.0",
            retail_output_price_per_million="4.0",
            is_active=False,
        )

        response = self.client.post(
            reverse("resale-listing-bulk-replace"),
            {
                "items": [
                    {
                        "platform": platform.id,
                        "model": model.id,
                        "channel": channel.id,
                        "display_name": "GPT-5",
                        "retail_input_price_per_million": "1.2",
                        "retail_output_price_per_million": "2.4",
                        "is_active": True,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ResaleListing.objects.get(
                platform=platform,
                model=model,
                channel=channel,
            ).is_active
        )

    def test_resale_listing_exclusion_bulk_upsert_and_restore(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )

        remove_response = self.client.post(
            reverse("resale-listing-exclusion-bulk-upsert"),
            {
                "platform": platform.id,
                "models": [model.id],
                "reason": "Not needed now",
            },
            format="json",
        )

        self.assertEqual(remove_response.status_code, 200)
        self.assertTrue(
            ResaleListingExclusion.objects.filter(
                platform=platform,
                model=model,
                reason="Not needed now",
            ).exists()
        )

        restore_response = self.client.post(
            reverse("resale-listing-exclusion-bulk-restore"),
            {
                "platform": platform.id,
                "models": [model.id],
            },
            format="json",
        )

        self.assertEqual(restore_response.status_code, 200)
        self.assertFalse(
            ResaleListingExclusion.objects.filter(
                platform=platform,
                model=model,
            ).exists()
        )

    def test_resale_listing_bulk_offline_deactivates_selected_models(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        selected_model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        untouched_model = LLMModel.objects.create(
            provider=provider,
            name="GPT-4o",
            code="gpt-4o",
        )
        channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        other_platform = ResalePlatform.objects.create(
            name="Agione Backup",
            code="agione-backup",
        )
        selected_listing = ResaleListing.objects.create(
            platform=platform,
            model=selected_model,
            channel=channel,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )
        untouched_listing = ResaleListing.objects.create(
            platform=platform,
            model=untouched_model,
            channel=channel,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )
        other_platform_listing = ResaleListing.objects.create(
            platform=other_platform,
            model=selected_model,
            channel=channel,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )

        response = self.client.post(
            reverse("resale-listing-bulk-offline"),
            {
                "platform": platform.id,
                "models": [selected_model.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        selected_listing.refresh_from_db()
        untouched_listing.refresh_from_db()
        other_platform_listing.refresh_from_db()
        self.assertFalse(selected_listing.is_active)
        self.assertTrue(untouched_listing.is_active)
        self.assertTrue(other_platform_listing.is_active)
        self.assertEqual(ResaleListingPriceHistory.objects.count(), 1)

    def test_summary_returns_agione_diagnostics(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        ChannelModelPrice.objects.create(
            channel=channel,
            model=model,
            is_listed=True,
        )
        ResaleListing.objects.create(
            platform=platform,
            model=model,
            channel=channel,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )

        response = self.client.get(reverse("llm-ops-summary"))

        self.assertEqual(response.status_code, 200)
        diagnostic = response.data["agione"]["diagnostics"][0]
        self.assertEqual(diagnostic["status"], "low_coverage")
        self.assertTrue(diagnostic["is_agione_listed"])
        self.assertTrue(diagnostic["has_lowest_listing"])
        self.assertEqual(
            response.data["point_conversion"]["points_per_currency_unit"],
            100.0,
        )

    def test_summary_uses_selected_resale_platform(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        default_platform, _ = ResalePlatform.objects.update_or_create(
            code="agione",
            defaults={"name": "Agione Default"},
        )
        selected_platform = ResalePlatform.objects.create(
            name="Agione Europe",
            code="agione-eu",
            points_per_currency_unit="50",
        )
        ChannelModelPrice.objects.create(
            channel=channel,
            model=model,
            is_listed=True,
        )
        ResaleListing.objects.create(
            platform=default_platform,
            model=model,
            channel=channel,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )

        response = self.client.get(
            reverse("llm-ops-summary"),
            {"resale_platform": selected_platform.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["agione"]["platform_id"],
            selected_platform.id,
        )
        self.assertEqual(
            response.data["point_conversion"]["points_per_currency_unit"],
            50.0,
        )
        diagnostic = response.data["agione"]["diagnostics"][0]
        self.assertFalse(diagnostic["is_agione_listed"])
        self.assertEqual(diagnostic["status"], "unlisted")

    def test_summary_converts_cross_currency_channel_options(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
            currency="USD",
            input_price_per_million="1",
            output_price_per_million="1",
        )
        usd_channel = ProcurementChannel.objects.create(
            name="USD Channel",
            code="usd-channel",
            currency="USD",
        )
        cny_channel = ProcurementChannel.objects.create(
            name="CNY Channel",
            code="cny-channel",
            currency="CNY",
        )
        ChannelModelPrice.objects.create(
            channel=usd_channel,
            model=model,
            is_listed=True,
        )
        ChannelModelPrice.objects.create(
            channel=cny_channel,
            model=model,
            is_listed=True,
        )

        response = self.client.get(
            reverse("llm-ops-summary"),
            {"display_currency": "CNY"},
        )

        self.assertEqual(response.status_code, 200)
        row = response.data["procurement"][0]
        self.assertEqual(row["best_channel"]["currency"], "CNY")
        self.assertFalse(row["requires_currency_conversion"])
        self.assertEqual(row["best_channel"]["original_currency"], "CNY")
        usd_option = next(
            item
            for item in row["options"]
            if item["original_currency"] == "USD"
        )
        expected_usd_price = round(
            response.data["currency"]["usd_to_cny_rate"],
            4,
        )
        self.assertEqual(
            usd_option["input_price_per_million"],
            expected_usd_price,
        )
        diagnostic = response.data["agione"]["diagnostics"][0]
        self.assertEqual(diagnostic["status"], "unlisted")
        self.assertEqual(response.data["currency"]["display_currency"], "CNY")

    def test_summary_ignores_agione_listing_for_unlisted_channel_model(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Hidden Channel",
            code="hidden-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        ChannelModelPrice.objects.create(
            channel=channel,
            model=model,
            is_listed=False,
        )
        ResaleListing.objects.create(
            platform=platform,
            model=model,
            channel=channel,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )

        response = self.client.get(reverse("llm-ops-summary"))

        self.assertEqual(response.status_code, 200)
        diagnostic = response.data["agione"]["diagnostics"][0]
        self.assertEqual(diagnostic["status"], "missing_channel")
        self.assertFalse(diagnostic["is_agione_listed"])
        self.assertEqual(response.data["listings"], [])
