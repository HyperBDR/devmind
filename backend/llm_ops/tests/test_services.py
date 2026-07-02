from decimal import Decimal

from django.test import TestCase

from llm_ops.models import (
    ChannelModelPrice,
    ChannelModelPriceHistory,
    ChannelPriceItem,
    LLMModel,
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    ModelSku,
    PriceCollectionSource,
    ProcurementChannel,
    ResaleListing,
    ResaleListingPriceHistory,
    ResalePlatform,
    SourceSkuOffering,
)
from llm_ops.services import (
    calculate_channel_model_cost,
    import_manual_model_prices,
    price_role_for_source,
    record_channel_model_price_history,
    record_resale_listing_price_history,
    resolve_channel_model_currency,
    resolve_channel_model_price,
    resolve_resale_listing_currency,
    sync_channel_price_items,
)


class LLMOpsPricingServiceTests(TestCase):
    def setUp(self):
        self.provider = LLMProvider.objects.create(
            name="OpenAI",
            code="openai",
        )
        self.model = LLMModel.objects.create(
            provider=self.provider,
            name="GPT-4o",
            code="gpt-4o",
            input_price_per_million=Decimal("2.5"),
            output_price_per_million=Decimal("10"),
        )
        self.channel = ProcurementChannel.objects.create(
            name="Direct",
            code="direct",
            currency="USD",
            settlement_ratio=Decimal("0.8"),
        )

    def test_resolves_global_channel_ratio(self):
        prices = resolve_channel_model_price(self.channel, self.model)

        self.assertEqual(prices.input_per_million, Decimal("2.000000"))
        self.assertEqual(prices.output_per_million, Decimal("8.000000"))

    def test_model_override_takes_precedence(self):
        ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
            settlement_ratio=Decimal("0.5"),
            custom_output_price_per_million=Decimal("3.25"),
        )

        prices = resolve_channel_model_price(self.channel, self.model)

        self.assertEqual(prices.input_per_million, Decimal("1.250000"))
        self.assertEqual(prices.output_per_million, Decimal("3.25"))

    def test_calculates_expected_usage_cost(self):
        cost = calculate_channel_model_cost(
            self.channel,
            self.model,
            input_tokens=2_000_000,
            output_tokens=3_000_000,
        )

        self.assertEqual(cost, Decimal("28.000000"))

    def test_official_source_is_cloud_hosted_for_third_party_meta_model(
        self,
    ):
        deepseek = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        deepseek_meta = MetaModel.objects.create(
            name="DeepSeek R1",
            code="deepseek-r1",
            owner_code=deepseek.code,
            owner_name=deepseek.name,
            owner_website=deepseek.website,
        )
        official_source = PriceCollectionSource.objects.create(
            name="OpenAI Official",
            slug="openai-official",
            provider=self.provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
        )

        role = price_role_for_source(
            official_source,
            meta_model=deepseek_meta,
        )

        self.assertEqual(role, LLMModel.PRICE_ROLE_CLOUD_HOSTED)

    def test_records_channel_media_price_history(self):
        self.model.currency = "CNY"
        self.model.image_output_price_per_image = Decimal("0.08")
        self.model.audio_input_price_per_second = Decimal("0.01")
        self.model.audio_output_price_per_second = Decimal("0.02")
        self.model.video_input_price_per_second = Decimal("0.03")
        self.model.video_output_price_per_second = Decimal("0.04")
        self.model.video_resolution_prices = {
            "1080P": {"output": "0.48"},
        }
        self.model.save()
        price = ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
            currency="CNY",
        )

        record_channel_model_price_history(price)

        history = ChannelModelPriceHistory.objects.get()
        self.assertEqual(history.currency, "CNY")
        self.assertEqual(
            history.image_output_price_per_image,
            Decimal("0.064"),
        )
        self.assertEqual(
            history.audio_input_price_per_second,
            Decimal("0.008"),
        )
        self.assertEqual(
            history.audio_output_price_per_second,
            Decimal("0.016"),
        )
        self.assertEqual(
            history.video_input_price_per_second,
            Decimal("0.024"),
        )
        self.assertEqual(
            history.video_output_price_per_second,
            Decimal("0.032"),
        )
        self.assertEqual(
            history.video_resolution_prices,
            {"1080P": {"output": "0.48"}},
        )

    def test_records_resale_media_price_history(self):
        self.model.currency = "CNY"
        self.model.save()
        platform, _ = ResalePlatform.objects.update_or_create(
            code="agione",
            defaults={
                "name": "Agione",
                "currency": "CNY",
            },
        )
        listing = ResaleListing.objects.create(
            platform=platform,
            model=self.model,
            channel=self.channel,
            retail_input_price_per_million=Decimal("1.2"),
            retail_output_price_per_million=Decimal("2.4"),
            retail_image_output_price_per_image=Decimal("0.08"),
            retail_audio_input_price_per_second=Decimal("0.03"),
            retail_audio_output_price_per_second=Decimal("0.04"),
            retail_video_input_price_per_second=Decimal("0.05"),
            retail_video_output_price_per_second=Decimal("0.06"),
        )

        record_resale_listing_price_history(listing)

        history = ResaleListingPriceHistory.objects.get()
        self.assertEqual(history.currency, "CNY")
        self.assertEqual(
            history.retail_image_output_price_per_image,
            Decimal("0.08"),
        )
        self.assertEqual(
            history.retail_audio_input_price_per_second,
            Decimal("0.03"),
        )
        self.assertEqual(
            history.retail_video_output_price_per_second,
            Decimal("0.06"),
        )

    def test_resolves_channel_model_currency_override_first(self):
        self.model.currency = "CNY"
        self.model.save()
        price = ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
            currency="CNY",
        )

        currency = resolve_channel_model_currency(
            self.channel,
            self.model,
            override=price,
        )

        self.assertEqual(currency, "CNY")

    def test_resolves_resale_listing_currency_from_platform(self):
        platform, _ = ResalePlatform.objects.update_or_create(
            code="agione",
            defaults={
                "name": "Agione",
                "currency": "CNY",
            },
        )
        listing = ResaleListing.objects.create(
            platform=platform,
            model=self.model,
            channel=self.channel,
            retail_input_price_per_million=Decimal("1.2"),
            retail_output_price_per_million=Decimal("2.4"),
        )

        self.assertEqual(resolve_resale_listing_currency(listing), "CNY")

    def test_syncs_channel_price_items_from_official_items(self):
        base_item = ModelPriceItem.objects.create(
            provider=self.provider,
            model=self.model,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal("2.5"),
            price_fingerprint="official-input",
            is_current=True,
        )
        price = ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
            settlement_ratio=Decimal("0.8"),
        )

        items = sync_channel_price_items(price)

        self.assertEqual(len(items), 1)
        item = ChannelPriceItem.objects.get()
        self.assertEqual(item.base_price_item, base_item)
        self.assertEqual(item.unit_price, Decimal("2.000000"))
        self.assertEqual(item.comparison_status, "below_official")
        self.assertEqual(item.delta_amount, Decimal("-0.500000"))
        self.assertEqual(item.delta_percent, Decimal("-20.0000"))
        self.assertIsNone(item.source)
        self.assertFalse(PriceCollectionSource.objects.exists())

    def test_sync_uses_selected_procurement_price_source(self):
        official_source = PriceCollectionSource.objects.create(
            name="OpenAI Official",
            slug="openai-official",
            provider=self.provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            currency="USD",
        )
        supplier_source = PriceCollectionSource.objects.create(
            name="Supplier A",
            slug="supplier-a",
            provider=self.provider,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            currency="USD",
        )
        ModelPriceItem.objects.create(
            provider=self.provider,
            model=self.model,
            source=official_source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal("2.5"),
            price_fingerprint="official-input",
            is_current=True,
        )
        supplier_item = ModelPriceItem.objects.create(
            provider=self.provider,
            model=self.model,
            source=supplier_source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal("1.5"),
            price_fingerprint="supplier-input",
            is_current=True,
        )
        price = ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
            price_source=supplier_source,
            settlement_ratio=Decimal("1"),
        )

        items = sync_channel_price_items(price)
        cost = calculate_channel_model_cost(
            self.channel,
            self.model,
            input_tokens=1_000_000,
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].base_price_item, supplier_item)
        self.assertEqual(items[0].unit_price, Decimal("1.500000"))
        self.assertEqual(cost, Decimal("1.500000"))

    def test_sync_falls_back_to_meta_model_price_items(self):
        official_source = PriceCollectionSource.objects.create(
            name="OpenAI Official Meta",
            slug="openai-official-meta",
            provider=self.provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            currency="USD",
        )
        supplier_source = PriceCollectionSource.objects.create(
            name="Supplier Without Items",
            slug="supplier-without-items",
            provider=self.provider,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            currency="USD",
        )
        official_model = LLMModel.objects.create(
            provider=self.provider,
            meta_model=self.model.meta_model,
            source=official_source,
            name="GPT-4o Official",
            code="gpt-4o-official",
        )
        official_item = ModelPriceItem.objects.create(
            provider=self.provider,
            model=official_model,
            source=official_source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal("2.5"),
            price_fingerprint="official-meta-input",
            is_current=True,
        )
        price = ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
            price_source=supplier_source,
            settlement_ratio=Decimal("0.5"),
        )

        items = sync_channel_price_items(price)
        cost = calculate_channel_model_cost(
            self.channel,
            self.model,
            input_tokens=1_000_000,
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].base_price_item, official_item)
        self.assertEqual(items[0].unit_price, Decimal("1.250000"))
        self.assertEqual(cost, Decimal("1.250000"))

    def test_sync_uses_selected_source_offering_price_items(self):
        first_source = PriceCollectionSource.objects.create(
            name="Supplier One",
            slug="supplier-one",
            provider=self.provider,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            currency="USD",
        )
        selected_source = PriceCollectionSource.objects.create(
            name="Supplier Two",
            slug="supplier-two",
            provider=self.provider,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            currency="USD",
        )
        sku = ModelSku.objects.create(
            provider=self.provider,
            meta_model=self.model.meta_model,
            canonical_sku_code="gpt-4o",
            upstream_model_name="gpt-4o",
            display_name="GPT-4o",
        )
        first_offering = SourceSkuOffering.objects.create(
            source=first_source,
            sku=sku,
            provider=self.provider,
            exposed_model_name="gpt-4o",
        )
        selected_offering = SourceSkuOffering.objects.create(
            source=selected_source,
            sku=sku,
            provider=self.provider,
            exposed_model_name="gpt-4o",
        )
        ModelPriceItem.objects.create(
            provider=self.provider,
            sku=sku,
            offering=first_offering,
            meta_model=self.model.meta_model,
            source=first_source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal("9"),
            price_fingerprint="first-source-input",
            is_current=True,
        )
        selected_item = ModelPriceItem.objects.create(
            provider=self.provider,
            sku=sku,
            offering=selected_offering,
            meta_model=self.model.meta_model,
            source=selected_source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal("3"),
            price_fingerprint="selected-source-input",
            is_current=True,
        )
        price = ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
            price_source=selected_source,
            settlement_ratio=Decimal("0.5"),
        )

        items = sync_channel_price_items(price)
        cost = calculate_channel_model_cost(
            self.channel,
            self.model,
            input_tokens=1_000_000,
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].base_price_item, selected_item)
        self.assertEqual(items[0].unit_price, Decimal("1.500000"))
        self.assertEqual(cost, Decimal("1.500000"))

    def test_marks_channel_item_comparison_unknown_for_currency_mismatch(self):
        ModelPriceItem.objects.create(
            provider=self.provider,
            model=self.model,
            dimension=ModelPriceItem.DIMENSION_TEXT_OUTPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal("10"),
            price_fingerprint="official-output",
            is_current=True,
        )
        cny_channel = ProcurementChannel.objects.create(
            name="CNY Channel",
            code="cny-channel",
            currency="CNY",
            settlement_ratio=Decimal("1"),
        )
        price = ChannelModelPrice.objects.create(
            channel=cny_channel,
            model=self.model,
        )

        sync_channel_price_items(price)

        item = ChannelPriceItem.objects.get()
        self.assertEqual(item.currency, "CNY")
        self.assertEqual(item.comparison_status, "unknown")
        self.assertIsNone(item.delta_amount)
        self.assertIsNone(item.delta_percent)

    def test_manual_import_without_promotion_reuses_existing_model(self):
        source = PriceCollectionSource.objects.create(
            provider=self.provider,
            name="Supplier Sheet",
            slug="supplier-sheet",
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            currency="USD",
            updates_model_prices=False,
        )

        import_manual_model_prices(
            source=source,
            provider=self.provider,
            rows=[
                {
                    "model_code": "gpt-4o",
                    "model_name": "GPT-4o",
                    "currency": "USD",
                    "output_price_per_million": Decimal("3.5"),
                },
                {
                    "model_code": "gpt-4o",
                    "model_name": "GPT-4o",
                    "currency": "USD",
                    "output_price_per_million": Decimal("3.5"),
                },
                {
                    "model_code": "gpt-4o",
                    "model_name": "GPT-4o",
                    "currency": "USD",
                    "input_price_per_million": Decimal("1.5"),
                },
            ],
            default_currency="USD",
            updates_model_prices=False,
        )

        self.assertEqual(LLMModel.objects.count(), 1)
        self.model.refresh_from_db()
        self.assertIsNone(self.model.source)
        self.assertEqual(
            self.model.input_price_per_million,
            Decimal("2.5"),
        )
        self.assertGreater(
            ModelPriceItem.objects.filter(source=source).count(),
            1,
        )
        self.assertEqual(
            ModelPriceItem.objects.filter(
                source=source,
                is_current=True,
            ).count(),
            1,
        )
        item = ModelPriceItem.objects.get(source=source, is_current=True)
        self.assertEqual(item.model, self.model)
        self.assertEqual(item.dimension, ModelPriceItem.DIMENSION_TEXT_INPUT)

    def test_manual_import_reports_incremental_refresh_records(self):
        source = PriceCollectionSource.objects.create(
            provider=self.provider,
            name="Supplier Sheet",
            slug="supplier-sheet",
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            currency="USD",
            updates_model_prices=False,
        )

        first_result = import_manual_model_prices(
            source=source,
            provider=self.provider,
            rows=[
                {
                    "model_code": "gpt-4o",
                    "model_name": "GPT-4o",
                    "currency": "USD",
                    "input_price_per_million": Decimal("1.5"),
                }
            ],
            default_currency="USD",
            updates_model_prices=False,
        )
        input_item = ModelPriceItem.objects.get(
            source=source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
        )
        self.model.refresh_from_db()

        self.assertIn(self.model.id, first_result["affected_model_ids"])
        self.assertIn(
            self.model.meta_model_id,
            first_result["affected_meta_model_ids"],
        )
        self.assertIn(input_item.id, first_result["affected_price_item_ids"])
        self.assertEqual(first_result["deactivated_price_item_ids"], [])

        second_result = import_manual_model_prices(
            source=source,
            provider=self.provider,
            rows=[
                {
                    "model_code": "gpt-4o",
                    "model_name": "GPT-4o",
                    "currency": "USD",
                    "output_price_per_million": Decimal("3.5"),
                }
            ],
            default_currency="USD",
            updates_model_prices=False,
        )

        self.assertIn(
            input_item.id,
            second_result["deactivated_price_item_ids"],
        )
        self.assertEqual(
            ModelPriceItem.objects.filter(source=source, is_current=True)
            .values_list("dimension", flat=True)
            .get(),
            ModelPriceItem.DIMENSION_TEXT_OUTPUT,
        )

    def test_manual_import_omits_deactivated_items_from_affected_ids(self):
        source = PriceCollectionSource.objects.create(
            provider=self.provider,
            name="Supplier Sheet",
            slug="supplier-sheet",
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            currency="USD",
            updates_model_prices=False,
        )

        result = import_manual_model_prices(
            source=source,
            provider=self.provider,
            rows=[
                {
                    "model_code": "gpt-4o",
                    "model_name": "GPT-4o",
                    "currency": "USD",
                    "input_price_per_million": Decimal("1.5"),
                },
                {
                    "model_code": "gpt-4o",
                    "model_name": "GPT-4o",
                    "currency": "USD",
                    "output_price_per_million": Decimal("3.5"),
                },
            ],
            default_currency="USD",
            updates_model_prices=False,
        )

        current_item = ModelPriceItem.objects.get(
            source=source,
            is_current=True,
        )
        stale_item = ModelPriceItem.objects.get(
            source=source,
            is_current=False,
        )

        self.assertEqual(
            current_item.dimension,
            ModelPriceItem.DIMENSION_TEXT_OUTPUT,
        )
        self.assertIn(current_item.id, result["affected_price_item_ids"])
        self.assertNotIn(stale_item.id, result["affected_price_item_ids"])
        self.assertIn(stale_item.id, result["deactivated_price_item_ids"])

    def test_manual_import_omits_reactivated_items_from_deactivated_ids(self):
        source = PriceCollectionSource.objects.create(
            provider=self.provider,
            name="Supplier Sheet",
            slug="supplier-sheet",
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            currency="USD",
            updates_model_prices=False,
        )

        import_manual_model_prices(
            source=source,
            provider=self.provider,
            rows=[
                {
                    "model_code": "gpt-4o",
                    "model_name": "GPT-4o",
                    "currency": "USD",
                    "output_price_per_million": Decimal("3.5"),
                },
                {
                    "model_code": "gpt-4o",
                    "model_name": "GPT-4o",
                    "currency": "USD",
                    "input_price_per_million": Decimal("1.5"),
                }
            ],
            default_currency="USD",
            updates_model_prices=False,
        )
        input_item = ModelPriceItem.objects.get(
            source=source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
        )

        result = import_manual_model_prices(
            source=source,
            provider=self.provider,
            rows=[
                {
                    "model_code": "gpt-4o",
                    "model_name": "GPT-4o",
                    "currency": "USD",
                    "output_price_per_million": Decimal("3.5"),
                },
                {
                    "model_code": "gpt-4o",
                    "model_name": "GPT-4o",
                    "currency": "USD",
                    "input_price_per_million": Decimal("1.5"),
                },
            ],
            default_currency="USD",
            updates_model_prices=False,
        )
        input_item.refresh_from_db()
        output_item = ModelPriceItem.objects.get(
            source=source,
            dimension=ModelPriceItem.DIMENSION_TEXT_OUTPUT,
        )

        self.assertTrue(input_item.is_current)
        self.assertFalse(output_item.is_current)
        self.assertIn(input_item.id, result["affected_price_item_ids"])
        self.assertNotIn(input_item.id, result["deactivated_price_item_ids"])
        self.assertIn(output_item.id, result["deactivated_price_item_ids"])

    def test_manual_import_without_source_provider_uses_model_owner(self):
        source = PriceCollectionSource.objects.create(
            name="Agione Sheet",
            slug="agione-sheet",
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            currency="USD",
            updates_model_prices=False,
        )

        import_manual_model_prices(
            source=source,
            provider=None,
            rows=[
                {
                    "model_code": "gpt-4o",
                    "model_name": "GPT-4o",
                    "currency": "USD",
                    "input_price_per_million": Decimal("1.5"),
                }
            ],
            default_currency="USD",
            updates_model_prices=False,
        )

        item = ModelPriceItem.objects.get(source=source)
        self.assertEqual(item.provider, self.provider)
        self.assertEqual(item.model, self.model)

    def test_manual_source_import_never_promotes_model_prices(self):
        aliyun = LLMProvider.objects.create(name="阿里云", code="aliyun")
        deepseek = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        deepseek_meta = MetaModel.objects.create(
            name="DeepSeek R1",
            code="deepseek-r1",
            owner_code=deepseek.code,
            owner_name=deepseek.name,
            owner_website=deepseek.website,
        )
        official_source = PriceCollectionSource.objects.create(
            provider=aliyun,
            name="阿里云官方价格",
            slug="aliyun-official",
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            updates_model_prices=True,
        )
        LLMModel.objects.create(
            provider=aliyun,
            meta_model=deepseek_meta,
            source=official_source,
            name="DeepSeek R1",
            code="deepseek-r1",
            input_price_per_million=Decimal("4"),
            price_role=LLMModel.PRICE_ROLE_SUPPLIER,
        )
        manual_source = PriceCollectionSource.objects.create(
            provider=aliyun,
            name="人工录入价格源",
            slug="manual-sheet",
            source_category=PriceCollectionSource.SOURCE_CATEGORY_MANUAL,
            updates_model_prices=False,
        )

        import_manual_model_prices(
            source=manual_source,
            provider=deepseek,
            rows=[
                {
                    "model_code": "deepseek-r1",
                    "model_name": "DeepSeek R1",
                    "currency": "CNY",
                    "input_price_per_million": Decimal("3.5"),
                }
            ],
            default_currency="CNY",
            updates_model_prices=True,
        )

        manual_source.refresh_from_db()
        self.assertFalse(manual_source.updates_model_prices)
        model = LLMModel.objects.get(
            provider=deepseek,
            code="deepseek-r1",
        )
        self.assertIsNone(model.source)
        self.assertEqual(model.input_price_per_million, Decimal("0"))
        item = ModelPriceItem.objects.get(source=manual_source)
        self.assertEqual(item.provider, deepseek)
        self.assertEqual(item.model, model)
