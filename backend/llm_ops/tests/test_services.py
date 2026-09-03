from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from llm_ops.models import (
    ChannelModelPrice,
    ChannelModelPriceHistory,
    ChannelOffering,
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
from llm_ops.price_table_validation import usage_range_spec
from llm_ops.services import (
    build_currency_conversion_context,
    calculate_channel_model_cost,
    channel_price_is_stale,
    compute_model_decision,
    import_manual_model_prices,
    match_meta_model_by_alias_or_name,
    price_role_for_source,
    record_channel_model_price_history,
    record_resale_listing_price_history,
    resolve_channel_model_currency,
    resolve_channel_model_price,
    resolve_channel_price_schedule,
    resolve_resale_listing_currency,
    sync_channel_price_items,
    sync_dependent_channel_price_items_for_price_items,
)
from llm_ops.tier_pricing import TieredPriceNotSupportedError


class ModelDecisionTests(SimpleTestCase):
    def test_channel_price_becomes_stale_after_24_hours(self):
        now = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)

        self.assertFalse(
            channel_price_is_stale(now - timedelta(hours=24), now=now)
        )
        self.assertTrue(
            channel_price_is_stale(
                now - timedelta(hours=24, seconds=1),
                now=now,
            )
        )
        self.assertFalse(channel_price_is_stale(None, now=now))

    def test_stale_price_requires_refresh_before_commercial_action(self):
        result = compute_model_decision(
            procurement_row={
                "best_channel": {
                    "channel_id": 1,
                    "input_price_per_million": 2,
                    "output_price_per_million": 8,
                },
                "options": [{"channel_id": 1}],
            },
            current_listing=None,
            platform=None,
            data_event_type="stale",
        )

        self.assertEqual(result["decision_status"], "platform_fee_unresolved")
        self.assertEqual(result["decision_action"], "refresh_prices")
        self.assertEqual(result["decision_priority"], 0)
        self.assertTrue(result["is_data_anomaly"])

    def test_stale_event_does_not_turn_market_reference_into_procurement(self):
        result = compute_model_decision(
            procurement_row={"best_channel": None, "options": []},
            current_listing=None,
            platform=None,
            operation_scope="market_reference",
            data_event_type="stale",
        )

        self.assertEqual(result["decision_status"], "market_reference")
        self.assertEqual(result["decision_action"], "view_market_price")
        self.assertEqual(result["decision_priority"], 9)


class CurrencyConversionContextTests(SimpleTestCase):
    @mock.patch("llm_ops.services._build_exchange_rate_info")
    def test_builds_context_without_remote_exchange_rate_lookup(
        self,
        mock_exchange_rate_info,
    ):
        mock_exchange_rate_info.return_value = {
            "exchange_rate": 7.23,
            "rate_source_label": "ExchangeRate API",
            "rate_source_url": "https://www.exchangerate-api.com/",
            "rate_collected_at": "2026-08-11T00:00:00+00:00",
        }

        context = build_currency_conversion_context("CNY")

        self.assertEqual(context.usd_to_cny_rate, Decimal("7.23"))
        mock_exchange_rate_info.assert_called_once_with(allow_remote=False)


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

    def test_calculates_cached_token_cost(self):
        self.model.cache_input_price_per_million = Decimal("1")
        self.model.save(update_fields=["cache_input_price_per_million"])

        cost = calculate_channel_model_cost(
            self.channel,
            self.model,
            input_tokens=1_000_000,
            cache_input_tokens=2_000_000,
        )

        self.assertEqual(cost, Decimal("3.600000"))

    def test_repeated_meta_model_alias_matches_share_full_table_load(self):
        from llm_ops import services

        getattr(services, "invalidate_meta_model_lookup_cache", lambda: None)()
        meta_model = MetaModel.objects.create(
            name="Alias Family",
            code="alias-family",
            aliases=["vendor/alias-family-2024-08-06"],
        )

        with CaptureQueriesContext(connection) as context:
            first = match_meta_model_by_alias_or_name(
                raw_code="vendor/alias-family-2024-08-06",
                reported_code="alias-family-2024-08-06",
                reported_name="Alias Family",
                canonical_code="alias-family",
                canonical_name="Alias Family",
                seed_aliases=[],
            )
            second = match_meta_model_by_alias_or_name(
                raw_code="vendor/alias-family-2024-08-06",
                reported_code="alias-family-2024-08-06",
                reported_name="Alias Family",
                canonical_code="alias-family",
                canonical_name="Alias Family",
                seed_aliases=[],
            )

        self.assertEqual(first, meta_model)
        self.assertEqual(second, meta_model)
        full_table_queries = [
            query
            for query in context.captured_queries
            if 'FROM "llm_ops_metamodel"' in query["sql"]
            and " WHERE " not in query["sql"]
        ]
        self.assertEqual(len(full_table_queries), 1)

    def test_expired_meta_model_lookup_cache_reloads_table(self):
        from llm_ops import services
        from llm_ops.meta_model_lookup import (
            META_MODEL_LOOKUP_CACHE_TTL_SECONDS,
        )

        getattr(services, "invalidate_meta_model_lookup_cache", lambda: None)()
        MetaModel.objects.create(
            name="Existing Family",
            code="existing-family",
            aliases=["existing-family"],
        )

        with mock.patch(
            "llm_ops.meta_model_lookup.monotonic",
            side_effect=[
                100.0,
                100.0 + META_MODEL_LOOKUP_CACHE_TTL_SECONDS + 0.01,
                100.0 + META_MODEL_LOOKUP_CACHE_TTL_SECONDS + 0.02,
            ],
        ):
            with CaptureQueriesContext(connection) as context:
                missing = match_meta_model_by_alias_or_name(
                    raw_code="new-family",
                    reported_code="new-family",
                    reported_name="New Family",
                    canonical_code="new-family",
                    canonical_name="New Family",
                    seed_aliases=[],
                )
                MetaModel.objects.bulk_create(
                    [
                        MetaModel(
                            name="New Family",
                            code="new-family",
                            aliases=["new-family"],
                        )
                    ]
                )
                found = match_meta_model_by_alias_or_name(
                    raw_code="new-family",
                    reported_code="new-family",
                    reported_name="New Family",
                    canonical_code="new-family",
                    canonical_name="New Family",
                    seed_aliases=[],
                )

        self.assertIsNone(missing)
        self.assertEqual(found.code, "new-family")
        full_table_queries = [
            query
            for query in context.captured_queries
            if 'FROM "llm_ops_metamodel"' in query["sql"]
            and " WHERE " not in query["sql"]
        ]
        self.assertEqual(len(full_table_queries), 2)

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

    def test_sync_dependent_channel_items_after_source_price_change(self):
        supplier_source = PriceCollectionSource.objects.create(
            name="Supplier A",
            slug="supplier-a",
            provider=self.provider,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            currency="USD",
        )
        base_item = ModelPriceItem.objects.create(
            provider=self.provider,
            model=self.model,
            source=supplier_source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal("2.5"),
            price_fingerprint="supplier-input-v1",
            is_current=True,
        )
        price = ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
            price_source=supplier_source,
            settlement_ratio=Decimal("0.8"),
        )
        sync_channel_price_items(price)
        self.assertEqual(
            ChannelPriceItem.objects.get(is_current=True).unit_price,
            Decimal("2.000000"),
        )

        base_item.unit_price = Decimal("3.5")
        base_item.price_fingerprint = "supplier-input-v2"
        base_item.save(update_fields=["unit_price", "price_fingerprint"])
        result = sync_dependent_channel_price_items_for_price_items(
            [base_item],
        )

        self.assertEqual(result["channel_model_prices"], 1)
        self.assertEqual(result["channel_price_items"], 1)
        self.assertEqual(
            ChannelPriceItem.objects.get(is_current=True).unit_price,
            Decimal("2.800000"),
        )
        self.assertEqual(
            ChannelPriceItem.objects.filter(is_current=False).count(),
            1,
        )

    def test_sync_does_not_fallback_when_selected_source_has_no_items(self):
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
        ModelPriceItem.objects.create(
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

        self.assertEqual(items, [])
        self.assertEqual(cost, Decimal("0.000000"))

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

    def test_channel_preserves_conditional_prices_and_uses_safe_default(self):
        source = PriceCollectionSource.objects.create(
            name="Aliyun Official",
            slug="aliyun-conditional-official",
            provider=self.provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            currency="CNY",
        )
        price = ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
            price_source=source,
            currency="CNY",
            settlement_ratio=Decimal("1"),
        )
        source_items = []
        dimensions = (
            ModelPriceItem.DIMENSION_TEXT_INPUT,
            ModelPriceItem.DIMENSION_TEXT_OUTPUT,
            ModelPriceItem.DIMENSION_CACHE_INPUT,
        )
        for code, values in (
            ("peak", ("3", "9", "0.3")),
            ("off_peak", ("1.5", "4.5", "0.15")),
        ):
            for dimension, value in zip(dimensions, values, strict=True):
                source_items.append(
                    ModelPriceItem.objects.create(
                        provider=self.provider,
                        model=self.model,
                        meta_model=self.model.meta_model,
                        source=source,
                        dimension=dimension,
                        billing_unit=(
                            ModelPriceItem.UNIT_PER_1M_TOKENS
                        ),
                        currency="CNY",
                        unit_price=Decimal(value),
                        spec={
                            "access_region": "cn-beijing",
                            "deployment_scope": "china_mainland",
                        },
                        pricing_condition={
                            "type": "provider_schedule",
                            "code": code,
                            "timezone": "Asia/Shanghai",
                        },
                        price_fingerprint=f"{code}-{dimension}",
                        is_current=True,
                    )
                )

        schedule = resolve_channel_price_schedule(
            self.channel,
            self.model,
            override=price,
            source_items=source_items,
        )
        unit_prices = resolve_channel_model_price(
            self.channel,
            self.model,
            override=price,
            source_items=source_items,
        )

        self.assertEqual(len(schedule.tiers), 6)
        self.assertEqual(
            {
                tier.spec["pricing_condition"]["code"]
                for tier in schedule.tiers
            },
            {"peak", "off_peak"},
        )
        self.assertEqual(unit_prices.input_per_million, Decimal("3"))
        self.assertEqual(unit_prices.output_per_million, Decimal("9"))
        self.assertEqual(
            unit_prices.cache_input_per_million,
            Decimal("0.3"),
        )

    def test_sync_does_not_mix_regions_for_selected_source_offering(self):
        source = PriceCollectionSource.objects.create(
            name="Regional supplier",
            slug="regional-supplier",
            provider=self.provider,
        )
        offerings = []
        for region, amount in (("Global", "9"), ("Japan", "3")):
            sku = ModelSku.objects.create(
                provider=self.provider,
                meta_model=self.model.meta_model,
                canonical_sku_code="gpt-4o",
                upstream_model_name="gpt-4o",
                display_name=f"GPT-4o {region}",
                region=region,
            )
            offering = SourceSkuOffering.objects.create(
                source=source,
                sku=sku,
                provider=self.provider,
                exposed_model_name="gpt-4o",
            )
            ModelPriceItem.objects.create(
                provider=self.provider,
                sku=sku,
                offering=offering,
                meta_model=self.model.meta_model,
                source=source,
                dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
                billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
                currency="USD",
                unit_price=Decimal(amount),
                price_fingerprint=f"region-{region}",
                is_current=True,
            )
            offerings.append(offering)
        channel_offering = ChannelOffering.objects.create(
            channel=self.channel,
            meta_model=self.model.meta_model,
            model=self.model,
            source_offering=offerings[1],
            offering_key="japan",
            display_name="Japan",
        )
        price = ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
            offering=channel_offering,
            price_source=source,
            settlement_ratio=Decimal("1"),
        )

        items = sync_channel_price_items(price)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].unit_price, Decimal("3"))

    def test_sync_selects_price_group_matching_model_base_prices(self):
        source = PriceCollectionSource.objects.create(
            name="Aliyun Official",
            slug="aliyun-official",
            provider=self.provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            currency="CNY",
        )
        sku = ModelSku.objects.create(
            provider=self.provider,
            meta_model=self.model.meta_model,
            canonical_sku_code="deepseek-v4-flash",
            upstream_model_name="deepseek-v4-flash",
            display_name="Deepseek V4 Flash",
        )
        offering = SourceSkuOffering.objects.create(
            source=source,
            sku=sku,
            provider=self.provider,
            exposed_model_name="deepseek-v4-flash",
        )
        self.model.input_price_per_million = Decimal("1")
        self.model.output_price_per_million = Decimal("2")
        self.model.currency = "CNY"
        self.model.save(
            update_fields=[
                "input_price_per_million",
                "output_price_per_million",
                "currency",
            ]
        )
        price_specs = [
            (
                "mainland-input",
                ModelPriceItem.DIMENSION_TEXT_INPUT,
                "1",
                "中国内地",
            ),
            (
                "mainland-output",
                ModelPriceItem.DIMENSION_TEXT_OUTPUT,
                "2",
                "中国内地",
            ),
            (
                "intl-input",
                ModelPriceItem.DIMENSION_TEXT_INPUT,
                "1.499",
                "国际",
            ),
            (
                "intl-output",
                ModelPriceItem.DIMENSION_TEXT_OUTPUT,
                "2.998",
                "国际",
            ),
        ]
        for fingerprint, dimension, unit_price, region in price_specs:
            ModelPriceItem.objects.create(
                provider=self.provider,
                sku=sku,
                offering=offering,
                meta_model=self.model.meta_model,
                source=source,
                dimension=dimension,
                billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
                currency="CNY",
                unit_price=Decimal(unit_price),
                spec={"deployment_scope": region},
                price_fingerprint=fingerprint,
                is_current=True,
            )
        cny_channel = ProcurementChannel.objects.create(
            name="CNY Direct",
            code="cny-direct",
            currency="CNY",
            settlement_ratio=Decimal("0.85"),
        )
        price = ChannelModelPrice.objects.create(
            channel=cny_channel,
            model=self.model,
            price_source=source,
        )

        items = sync_channel_price_items(price)
        unit_prices = resolve_channel_model_price(
            cny_channel,
            self.model,
            override=price,
        )

        self.assertEqual(len(items), 2)
        self.assertEqual(unit_prices.input_per_million, Decimal("0.850000"))
        self.assertEqual(unit_prices.output_per_million, Decimal("1.700000"))
        self.assertEqual(
            {item.base_price_item.unit_price for item in items},
            {Decimal("1.000000"), Decimal("2.000000")},
        )

    def test_channel_schedule_preserves_usage_range_prices(self):
        source = PriceCollectionSource.objects.create(
            name="Aliyun Tiered Official",
            slug="aliyun-tiered-official",
            provider=self.provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            currency="CNY",
        )
        self.model.currency = "CNY"
        self.model.save(update_fields=["currency"])
        self.channel.currency = "CNY"
        self.channel.save(update_fields=["currency"])
        price_specs = [
            (
                "range-input-low",
                ModelPriceItem.DIMENSION_TEXT_INPUT,
                "0.2",
                "0",
                "128000",
            ),
            (
                "range-input-high",
                ModelPriceItem.DIMENSION_TEXT_INPUT,
                "1.2",
                "128000",
                "256000",
            ),
            (
                "range-output-low",
                ModelPriceItem.DIMENSION_TEXT_OUTPUT,
                "2",
                "0",
                "128000",
            ),
            (
                "range-output-high",
                ModelPriceItem.DIMENSION_TEXT_OUTPUT,
                "12",
                "128000",
                "256000",
            ),
        ]
        for fingerprint, dimension, unit_price, start, end in price_specs:
            ModelPriceItem.objects.create(
                provider=self.provider,
                model=self.model,
                meta_model=self.model.meta_model,
                source=source,
                dimension=dimension,
                billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
                currency="CNY",
                unit_price=Decimal(unit_price),
                tier_type=ModelPriceItem.TIER_USAGE_RANGE,
                tier_start=Decimal(start),
                tier_end=Decimal(end),
                spec=usage_range_spec(),
                price_fingerprint=fingerprint,
                is_current=True,
            )
        price = ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
            price_source=source,
        )

        synced_items = sync_channel_price_items(price)

        self.assertEqual(len(synced_items), len(price_specs))
        self.assertEqual(
            [
                (
                    item.dimension,
                    item.tier_type,
                    item.tier_start,
                    item.tier_end,
                    item.unit_price,
                    item.base_price_item_id,
                )
                for item in sorted(
                    synced_items,
                    key=lambda item: (item.dimension, item.tier_start),
                )
            ],
            [
                (
                    ModelPriceItem.DIMENSION_TEXT_INPUT,
                    ModelPriceItem.TIER_USAGE_RANGE,
                    Decimal("0"),
                    Decimal("128000"),
                    Decimal("0.160000"),
                    ModelPriceItem.objects.get(
                        price_fingerprint="range-input-low"
                    ).id,
                ),
                (
                    ModelPriceItem.DIMENSION_TEXT_INPUT,
                    ModelPriceItem.TIER_USAGE_RANGE,
                    Decimal("128000"),
                    Decimal("256000"),
                    Decimal("0.960000"),
                    ModelPriceItem.objects.get(
                        price_fingerprint="range-input-high"
                    ).id,
                ),
                (
                    ModelPriceItem.DIMENSION_TEXT_OUTPUT,
                    ModelPriceItem.TIER_USAGE_RANGE,
                    Decimal("0"),
                    Decimal("128000"),
                    Decimal("1.600000"),
                    ModelPriceItem.objects.get(
                        price_fingerprint="range-output-low"
                    ).id,
                ),
                (
                    ModelPriceItem.DIMENSION_TEXT_OUTPUT,
                    ModelPriceItem.TIER_USAGE_RANGE,
                    Decimal("128000"),
                    Decimal("256000"),
                    Decimal("9.600000"),
                    ModelPriceItem.objects.get(
                        price_fingerprint="range-output-high"
                    ).id,
                ),
            ],
        )

        schedule = resolve_channel_price_schedule(
            self.channel,
            self.model,
            override=price,
        )

        input_tiers = schedule.for_dimension(
            ModelPriceItem.DIMENSION_TEXT_INPUT
        )
        output_tiers = schedule.for_dimension(
            ModelPriceItem.DIMENSION_TEXT_OUTPUT
        )
        self.assertEqual(len(schedule.tiers), 4)
        self.assertEqual(
            [tier.unit_price for tier in input_tiers],
            [Decimal("0.160000"), Decimal("0.960000")],
        )
        self.assertEqual(
            [tier.tier_start for tier in output_tiers],
            [Decimal("0"), Decimal("128000")],
        )
        self.assertEqual(output_tiers[-1].tier_end, Decimal("256000"))
        self.assertEqual(output_tiers[-1].currency, "CNY")
        self.assertEqual(
            output_tiers[-1].spec,
            usage_range_spec(),
        )
        self.assertEqual(
            output_tiers[-1].billing_unit,
            ModelPriceItem.UNIT_PER_1M_TOKENS,
        )
        self.assertIsNone(record_channel_model_price_history(price))

    def test_legacy_unit_price_resolution_rejects_tiered_prices(self):
        source = PriceCollectionSource.objects.create(
            name="Tiered Supplier",
            slug="tiered-supplier",
            provider=self.provider,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            currency="USD",
        )
        ModelPriceItem.objects.create(
            provider=self.provider,
            model=self.model,
            source=source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal("1"),
            tier_type=ModelPriceItem.TIER_USAGE_RANGE,
            tier_start=Decimal("0"),
            tier_end=None,
            price_fingerprint="tiered-input",
        )
        price = ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
            price_source=source,
        )

        with self.assertRaises(TieredPriceNotSupportedError):
            resolve_channel_model_price(
                self.channel,
                self.model,
                override=price,
            )

    def test_channel_schedule_preserves_video_resolution_precedence(self):
        source = PriceCollectionSource.objects.create(
            name="Video Source",
            slug="video-source",
            provider=self.provider,
            currency="USD",
        )
        ModelPriceItem.objects.create(
            provider=self.provider,
            model=self.model,
            source=source,
            dimension=ModelPriceItem.DIMENSION_VIDEO_OUTPUT,
            billing_unit=ModelPriceItem.UNIT_PER_SECOND,
            currency="USD",
            unit_price=Decimal("1"),
            price_fingerprint="video-output",
        )
        self.model.video_resolution_prices = {
            "1080P": {"output": "4"},
        }
        self.model.save(update_fields=["video_resolution_prices"])
        price = ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
            price_source=source,
            settlement_ratio=Decimal("0.5"),
        )

        schedule = resolve_channel_price_schedule(
            self.channel,
            self.model,
            override=price,
            video_resolution="1080P",
        )
        output_tier = schedule.for_dimension(
            ModelPriceItem.DIMENSION_VIDEO_OUTPUT
        )[0]
        self.assertEqual(output_tier.unit_price, Decimal("2"))

        price.custom_video_output_price_per_second = Decimal("3")
        price.custom_video_resolution_prices = {
            "1080P": {"output": "6"},
        }
        price.save()
        schedule = resolve_channel_price_schedule(
            self.channel,
            self.model,
            override=price,
            video_resolution="1080P",
        )
        output_tier = schedule.for_dimension(
            ModelPriceItem.DIMENSION_VIDEO_OUTPUT
        )[0]
        self.assertEqual(output_tier.unit_price, Decimal("6"))

    def test_channel_cost_hits_exact_boundary_and_includes_cached_tokens(self):
        source = PriceCollectionSource.objects.create(
            name="Tiered Supplier",
            slug="tiered-cost-supplier",
            provider=self.provider,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            currency="USD",
        )
        tiers = (
            (ModelPriceItem.DIMENSION_TEXT_INPUT, "1", "0", "1000"),
            (ModelPriceItem.DIMENSION_TEXT_INPUT, "2", "1000", None),
            (ModelPriceItem.DIMENSION_TEXT_OUTPUT, "4", "0", None),
            (ModelPriceItem.DIMENSION_CACHE_INPUT, "0.5", "0", "500"),
            (ModelPriceItem.DIMENSION_CACHE_INPUT, "1", "500", None),
        )
        for index, (dimension, unit_price, start, end) in enumerate(tiers):
            ModelPriceItem.objects.create(
                provider=self.provider,
                model=self.model,
                source=source,
                dimension=dimension,
                billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
                currency="USD",
                unit_price=Decimal(unit_price),
                tier_type=ModelPriceItem.TIER_USAGE_RANGE,
                tier_start=Decimal(start),
                tier_end=Decimal(end) if end is not None else None,
                price_fingerprint=f"tiered-cost-{index}",
            )
        ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
            price_source=source,
            settlement_ratio=Decimal("1"),
        )

        cost = calculate_channel_model_cost(
            self.channel,
            self.model,
            input_tokens=1000,
            output_tokens=2000,
            cache_input_tokens=500,
        )

        self.assertEqual(cost, Decimal("0.010500"))

    def test_channel_price_sync_is_atomic(self):
        for index, dimension in enumerate(
            (
                ModelPriceItem.DIMENSION_TEXT_INPUT,
                ModelPriceItem.DIMENSION_TEXT_OUTPUT,
            )
        ):
            ModelPriceItem.objects.create(
                provider=self.provider,
                model=self.model,
                dimension=dimension,
                billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
                currency="USD",
                unit_price=Decimal(index + 1),
                price_fingerprint=f"atomic-{index}",
            )
        price = ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
        )
        original = sync_channel_price_items(price)
        original_ids = [item.id for item in original]

        with mock.patch.object(
            ChannelPriceItem.objects,
            "update_or_create",
            side_effect=RuntimeError("simulated write failure"),
        ):
            with self.assertRaises(RuntimeError):
                sync_channel_price_items(price)

        self.assertEqual(
            list(
                ChannelPriceItem.objects.filter(is_current=True)
                .order_by("id")
                .values_list("id", flat=True)
            ),
            original_ids,
        )

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

    def test_manual_import_persists_and_resyncs_usage_range_items(self):
        source = PriceCollectionSource.objects.create(
            provider=self.provider,
            name="Supplier Tier Sheet",
            slug="supplier-tier-sheet",
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            currency="USD",
            updates_model_prices=False,
        )
        price = ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
            price_source=source,
            settlement_ratio=Decimal("0.8"),
        )
        tier_spec = usage_range_spec()
        rows = []
        for dimension, first, second in (
            ("text_input", "1", "2"),
            ("text_output", "3", "4"),
            ("cache_input", "0.5", "1"),
        ):
            rows.extend(
                [
                    {
                        "dimension": dimension,
                        "billing_unit": "per_1m_tokens",
                        "unit_price": Decimal(first),
                        "tier_type": "usage_range",
                        "tier_start": Decimal("0"),
                        "tier_end": Decimal("128000"),
                        "spec": tier_spec,
                    },
                    {
                        "dimension": dimension,
                        "billing_unit": "per_1m_tokens",
                        "unit_price": Decimal(second),
                        "tier_type": "usage_range",
                        "tier_start": Decimal("128000"),
                        "tier_end": None,
                        "spec": tier_spec,
                    },
                ]
            )

        result = import_manual_model_prices(
            source=source,
            provider=self.provider,
            rows=[
                {
                    "model_code": "gpt-4o",
                    "model_name": "GPT-4o",
                    "currency": "USD",
                    "price_items": rows,
                }
            ],
            default_currency="USD",
            updates_model_prices=False,
        )

        source_items = ModelPriceItem.objects.filter(
            source=source,
            is_current=True,
        ).order_by("dimension", "tier_start")
        channel_items = ChannelPriceItem.objects.filter(
            channel=price.channel,
            model=price.model,
            is_current=True,
        ).order_by("dimension", "tier_start")
        self.assertEqual(source_items.count(), 6)
        self.assertEqual(channel_items.count(), 6)
        self.assertEqual(
            list(source_items.values_list("tier_start", "tier_end"))[:2],
            [
                (Decimal("0"), Decimal("128000")),
                (Decimal("128000"), None),
            ],
        )
        self.assertEqual(
            result["channel_price_sync"]["channel_model_prices"],
            1,
        )

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

    def test_manual_import_resyncs_dependent_channel_prices(self):
        source = PriceCollectionSource.objects.create(
            provider=self.provider,
            name="Supplier Sheet",
            slug="supplier-sheet-resync",
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
                    "input_price_per_million": Decimal("1.5"),
                }
            ],
            default_currency="USD",
            updates_model_prices=False,
        )
        price = ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.model,
            price_source=source,
            settlement_ratio=Decimal("0.8"),
        )
        sync_channel_price_items(price)
        self.assertEqual(
            ChannelPriceItem.objects.get(is_current=True).unit_price,
            Decimal("1.200000"),
        )

        result = import_manual_model_prices(
            source=source,
            provider=self.provider,
            rows=[
                {
                    "model_code": "gpt-4o",
                    "model_name": "GPT-4o",
                    "currency": "USD",
                    "input_price_per_million": Decimal("2.5"),
                }
            ],
            default_currency="USD",
            updates_model_prices=False,
        )

        self.assertEqual(
            result["channel_price_sync"]["channel_model_prices"],
            1,
        )
        self.assertEqual(
            ChannelPriceItem.objects.get(is_current=True).unit_price,
            Decimal("2.000000"),
        )

    def test_manual_import_keeps_current_rows_when_write_fails(self):
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
                    "input_price_per_million": Decimal("1.5"),
                }
            ],
            default_currency="USD",
            updates_model_prices=False,
        )
        current_item = ModelPriceItem.objects.get(
            source=source,
            model=self.model,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
        )

        with mock.patch.object(
            ModelPriceItem.objects,
            "update_or_create",
            side_effect=RuntimeError("write failed"),
        ):
            with self.assertRaisesMessage(RuntimeError, "write failed"):
                import_manual_model_prices(
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

        current_item.refresh_from_db()
        self.assertTrue(current_item.is_current)
        self.assertIsNone(current_item.effective_to)

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
