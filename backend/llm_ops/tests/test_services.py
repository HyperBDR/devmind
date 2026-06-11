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
    PriceCollectionSource,
    ProcurementChannel,
    ResaleListing,
    ResaleListingPriceHistory,
    ResalePlatform,
)
from llm_ops.seed_data import seed_initial_price_sheet
from llm_ops.services import (
    calculate_channel_model_cost,
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
        self.assertEqual(item.source.source_category, "supplier")
        self.assertEqual(item.source.channel, self.channel)

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


class LLMOpsPriceSheetSeedTests(TestCase):
    def test_seed_initial_price_sheet_imports_models_and_discounts(self):
        stats = seed_initial_price_sheet()

        self.assertEqual(stats["providers"], 7)
        self.assertEqual(stats["models"], 113)
        openai = LLMProvider.objects.get(code="openai")
        model = LLMModel.objects.get(provider=openai, code="gpt-5.4-pro")
        price = ChannelModelPrice.objects.get(model=model)
        self.assertEqual(price.channel.code, "real-resource-platform")
        self.assertEqual(price.settlement_ratio, Decimal("0.55"))
        self.assertEqual(model.source.provider, openai)
        self.assertEqual(model.currency, "USD")
        aliyun = LLMProvider.objects.get(code="aliyun")
        qwen = LLMModel.objects.get(provider=aliyun, code="qwen-plus")
        self.assertEqual(qwen.currency, "CNY")
        self.assertEqual(qwen.source.currency, "CNY")
        qwen_meta = MetaModel.objects.get(code="qwen-plus")
        self.assertEqual(qwen_meta.name, "Qwen Plus")
        self.assertEqual(qwen_meta.family, "Qwen")
        self.assertEqual(qwen_meta.context_window, 131072)
        self.assertIn("通义千问 Plus", qwen_meta.aliases)
        self.assertIn("tool_calling", qwen_meta.capabilities["features"])
        gpt_meta = MetaModel.objects.get(code="gpt-4o-mini")
        self.assertEqual(gpt_meta.name, "GPT-4o mini")
        self.assertEqual(gpt_meta.family, "GPT-4o")
        self.assertEqual(gpt_meta.context_window, 128000)
        self.assertIn("vision", gpt_meta.capabilities["features"])
        self.assertEqual(
            ChannelModelPrice.objects.get(
                channel__code="real-resource-platform",
                model=qwen,
            ).currency,
            "CNY",
        )
        source = qwen.source
        self.assertEqual(source.source_category, "supplier")
        self.assertEqual(source.channel.code, "real-resource-platform")
        yunce_source = PriceCollectionSource.objects.get(
            slug="yunce-aliyun-qwen-plus",
        )
        yunce_price = ChannelModelPrice.objects.get(
            channel__code="yunce-supplier-platform",
            model=qwen,
        )
        self.assertEqual(yunce_source.channel.code, "yunce-supplier-platform")
        self.assertEqual(yunce_source.source_type, "yunce")
        self.assertEqual(yunce_price.price_source, yunce_source)
        self.assertEqual(
            ModelPriceItem.objects.filter(
                model=qwen,
                source=yunce_source,
                is_current=True,
            ).count(),
            2,
        )
        deepseek_v3_sources = LLMModel.objects.filter(
            code="deepseek-v3",
        ).values_list("source__name", flat=True)
        self.assertEqual(len(deepseek_v3_sources), 3)
        self.assertIn("阿里云 表格价格目录", deepseek_v3_sources)
        self.assertIn("火山 表格价格目录", deepseek_v3_sources)
        self.assertIn("硅基流动 表格价格目录", deepseek_v3_sources)

    def test_seed_initial_price_sheet_is_idempotent(self):
        seed_initial_price_sheet()
        stats = seed_initial_price_sheet()

        self.assertEqual(stats["providers"], 0)
        self.assertEqual(stats["models"], 0)
        self.assertEqual(stats["channel_model_prices"], 0)
        self.assertEqual(stats["yunce_supplier_sources"], 0)
        self.assertEqual(stats["yunce_supplier_prices"], 0)
        self.assertEqual(stats["yunce_supplier_price_items"], 0)
        self.assertEqual(LLMModel.objects.count(), 113)
