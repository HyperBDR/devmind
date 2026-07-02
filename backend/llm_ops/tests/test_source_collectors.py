from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase

from llm_ops.collection_services import (
    sync_model_price_items,
    upsert_collected_snapshot,
    upsert_collected_offering,
)
from llm_ops.collectors import CollectedModelPricing, NormalizedPriceRow
from llm_ops.collectors.official import OFFICIAL_PROVIDER_CONFIGS
from llm_ops.models import (
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    ModelSku,
    PriceCollectionRun,
    PriceCollectionSource,
    SourceSkuOffering,
)
from llm_ops.source_collectors import (
    collect_price_source,
    get_price_source_collector,
    source_supports_code_collection,
)
from llm_ops.source_collectors.official import (
    SUPPORTED_OFFICIAL_PROVIDER_CODES,
)


class PriceSourceCollectorRegistryTests(TestCase):
    def test_all_official_configs_have_registered_collectors(self):
        self.assertEqual(
            set(OFFICIAL_PROVIDER_CONFIGS),
            set(SUPPORTED_OFFICIAL_PROVIDER_CODES),
        )

    def test_official_provider_source_dispatches_to_provider_collector(self):
        provider = LLMProvider.objects.create(name="阿里云", code="aliyun")
        source = PriceCollectionSource.objects.create(
            name="Aliyun Official",
            slug="aliyun-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://help.aliyun.com/zh/model-studio/model-pricing"
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        collector = get_price_source_collector(source)
        self.assertIsNotNone(collector)
        self.assertEqual(collector.collector_id, "official_provider:aliyun")
        self.assertEqual(
            collector.__class__.__name__,
            "AliyunOfficialPriceSourceCollector",
        )
        self.assertTrue(source_supports_code_collection(source))

        with mock.patch(
            "llm_ops.source_collectors.official."
            "sync_official_provider_model_prices"
        ) as mock_sync:
            mock_sync.return_value = {"models": 1}
            result = collect_price_source(
                source,
                verify_source=False,
            )

        mock_sync.assert_called_once_with(
            provider=provider,
            source=source,
            verify_source=False,
        )
        self.assertEqual(result, {"models": 1})

    def test_generic_official_provider_source_dispatches_to_collector(self):
        provider = LLMProvider.objects.create(name="DeepSeek", code="deepseek")
        source = PriceCollectionSource.objects.create(
            name="DeepSeek Official",
            slug="deepseek-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://api-docs.deepseek.com/zh-cn/quick_start/pricing"
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        collector = get_price_source_collector(source)

        self.assertIsNotNone(collector)
        self.assertEqual(collector.collector_id, "official_provider:deepseek")
        self.assertTrue(source_supports_code_collection(source))

    def test_baidu_official_provider_source_dispatches_to_collector(self):
        provider = LLMProvider.objects.create(name="百度", code="baidu")
        source = PriceCollectionSource.objects.create(
            name="Baidu Official",
            slug="baidu-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://cloud.baidu.com/doc/qianfan/s/wmh4sv6ya",
            is_enabled=True,
            updates_model_prices=True,
        )

        collector = get_price_source_collector(source)

        self.assertIsNotNone(collector)
        self.assertEqual(collector.collector_id, "official_provider:baidu")
        self.assertTrue(source_supports_code_collection(source))

    def test_model_level_official_source_is_not_supported(self):
        provider = LLMProvider.objects.create(name="阿里云", code="aliyun")
        source = PriceCollectionSource.objects.create(
            name="Aliyun Qwen Plus Official",
            slug="aliyun-qwen-plus-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://help.aliyun.com/zh/model-studio/model-pricing"
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        collector = get_price_source_collector(source)

        self.assertIsNone(collector)
        self.assertFalse(source_supports_code_collection(source))

    def test_supplier_source_does_not_support_code_collection(self):
        provider = LLMProvider.objects.create(name="DeepSeek", code="deepseek")
        source = PriceCollectionSource.objects.create(
            name="SiliconFlow Sheet",
            slug="siliconflow-sheet",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            endpoint_url="https://example.com/pricing",
            is_enabled=True,
            updates_model_prices=True,
        )

        self.assertIsNone(get_price_source_collector(source))
        self.assertFalse(source_supports_code_collection(source))
        with self.assertRaisesMessage(
            ValueError,
            "This source does not support code collection.",
        ):
            collect_price_source(source)

    def test_siliconflow_supplier_source_dispatches_to_collector(self):
        source = PriceCollectionSource.objects.create(
            name="SiliconFlow Pricing",
            slug="siliconflow-pricing",
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            endpoint_url="https://siliconflow.cn/pricing",
            currency="CNY",
            is_enabled=True,
            updates_model_prices=True,
        )

        collector = get_price_source_collector(source)

        self.assertIsNotNone(collector)
        self.assertEqual(collector.collector_id, "supplier:siliconflow")
        self.assertTrue(source_supports_code_collection(source))

        with mock.patch(
            "llm_ops.source_collectors.siliconflow."
            "sync_vendor_price_source_catalog"
        ) as mock_sync:
            mock_sync.return_value = {"models": 2}
            result = collect_price_source(source, verify_source=False)

        mock_sync.assert_called_once_with(
            provider_code="siliconflow",
            source=source,
            verify_source=False,
        )
        self.assertEqual(result, {"models": 2})

    def test_unknown_official_provider_does_not_match_collector(self):
        provider = LLMProvider.objects.create(
            name="Unknown AI",
            code="unknown-ai",
        )
        source = PriceCollectionSource.objects.create(
            name="Unknown Official",
            slug="unknown-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://example.com/pricing",
            is_enabled=True,
            updates_model_prices=True,
        )

        self.assertIsNone(get_price_source_collector(source))
        self.assertFalse(source_supports_code_collection(source))


class PriceCollectionSkuPersistenceTests(TestCase):
    def setUp(self):
        self.provider = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        self.source = PriceCollectionSource.objects.create(
            name="DeepSeek Official",
            slug="deepseek-official",
            provider=self.provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://api-docs.deepseek.com/zh-cn/quick_start/pricing"
            ),
            currency="CNY",
            is_enabled=True,
            updates_model_prices=True,
        )
        self.meta_model = MetaModel.objects.create(
            code="deepseek-v4-flash",
            name="DeepSeek V4 Flash",
            owner_code="deepseek",
            owner_name="DeepSeek",
        )

    def test_collected_price_creates_candidate_sku_and_offering(self):
        item = self.collected_item(exposed_model_name="deepseek-chat")

        offering, _ = upsert_collected_offering(
            item,
            source=self.source,
            source_url=self.source.endpoint_url,
            meta_model=self.meta_model,
        )
        price_items = sync_model_price_items(
            item,
            source=self.source,
            offering=offering,
            source_url=self.source.endpoint_url,
        )

        sku = offering.sku
        persisted_offering = SourceSkuOffering.objects.get(
            source=self.source,
            sku=sku,
            exposed_model_name="deepseek-chat",
        )
        input_item = ModelPriceItem.objects.get(
            source=self.source,
            offering=offering,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
        )

        self.assertEqual(len(price_items), 2)
        self.assertEqual(sku.routing_status, ModelSku.ROUTING_CANDIDATE)
        self.assertFalse(sku.is_routable)
        self.assertEqual(sku.variant_type, ModelSku.VARIANT_OFFICIAL)
        self.assertEqual(sku.upstream_model_name, "deepseek-v4-flash")
        self.assertEqual(persisted_offering.pricing_method, "collected")
        self.assertEqual(input_item.sku, sku)
        self.assertEqual(input_item.offering, offering)
        self.assertEqual(input_item.model.sku, sku)
        self.assertEqual(input_item.unit_price, Decimal("1.000000"))

    def test_collected_price_does_not_overwrite_locked_sku(self):
        item = self.collected_item()
        offering, _ = upsert_collected_offering(
            item,
            source=self.source,
            source_url=self.source.endpoint_url,
            meta_model=self.meta_model,
        )
        locked_meta = MetaModel.objects.create(
            code="operator-locked-deepseek-v4-flash",
            name="Operator Locked DeepSeek V4 Flash",
            owner_code="deepseek",
            owner_name="DeepSeek",
        )
        sku = offering.sku
        sku.meta_model = locked_meta
        sku.routing_status = ModelSku.ROUTING_LOCKED
        sku.is_routable = True
        sku.save()

        upsert_collected_offering(
            item,
            source=self.source,
            source_url=self.source.endpoint_url,
            meta_model=self.meta_model,
        )

        sku.refresh_from_db()
        self.assertEqual(sku.meta_model, locked_meta)
        self.assertEqual(sku.routing_status, ModelSku.ROUTING_LOCKED)
        self.assertTrue(sku.is_routable)

    def test_same_source_and_sku_can_keep_distinct_exposed_names(self):
        first = self.collected_item(exposed_model_name="deepseek-chat")
        second = self.collected_item(exposed_model_name="deepseek-chat-fast")

        offering, _ = upsert_collected_offering(
            first,
            source=self.source,
            source_url=self.source.endpoint_url,
            meta_model=self.meta_model,
        )
        sync_model_price_items(
            first,
            source=self.source,
            offering=offering,
            source_url=self.source.endpoint_url,
        )
        second_offering, _ = upsert_collected_offering(
            second,
            source=self.source,
            source_url=self.source.endpoint_url,
            meta_model=self.meta_model,
        )
        sync_model_price_items(
            second,
            source=self.source,
            offering=second_offering,
            source_url=self.source.endpoint_url,
        )

        offerings = SourceSkuOffering.objects.filter(
            source=self.source,
            sku=offering.sku,
        )
        current_inputs = ModelPriceItem.objects.filter(
            source=self.source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            is_current=True,
        )

        self.assertEqual(offerings.count(), 2)
        self.assertEqual(current_inputs.count(), 2)

    def test_snapshots_are_scoped_by_offering(self):
        first = self.collected_item(exposed_model_name="deepseek-chat")
        second = self.collected_item(exposed_model_name="deepseek-chat-fast")
        run = PriceCollectionRun.objects.create(source=self.source)

        first_offering, _ = upsert_collected_offering(
            first,
            source=self.source,
            source_url=self.source.endpoint_url,
            meta_model=self.meta_model,
        )
        second_offering, _ = upsert_collected_offering(
            second,
            source=self.source,
            source_url=self.source.endpoint_url,
            meta_model=self.meta_model,
        )

        first_snapshot, _ = upsert_collected_snapshot(
            first,
            source=self.source,
            run=run,
            offering=first_offering,
        )
        second_snapshot, _ = upsert_collected_snapshot(
            second,
            source=self.source,
            run=run,
            offering=second_offering,
        )

        self.assertNotEqual(first_snapshot.id, second_snapshot.id)
        self.assertEqual(first_snapshot.offering, first_offering)
        self.assertEqual(second_snapshot.offering, second_offering)

    def test_source_sku_offering_rejects_upstream_cycle(self):
        item = self.collected_item()
        offering, _ = upsert_collected_offering(
            item,
            source=self.source,
            source_url=self.source.endpoint_url,
            meta_model=self.meta_model,
        )
        sync_model_price_items(
            item,
            source=self.source,
            offering=offering,
            source_url=self.source.endpoint_url,
        )
        offering = SourceSkuOffering.objects.get(
            source=self.source,
            sku=offering.sku,
        )
        offering.upstream_offering = offering

        with self.assertRaises(ValidationError):
            offering.save()

    def collected_item(
        self,
        *,
        exposed_model_name: str = "deepseek-v4-flash",
    ) -> CollectedModelPricing:
        return CollectedModelPricing(
            model_source="DeepSeek",
            model_type="文本模型",
            source_model_type="Text",
            name="DeepSeek V4 Flash",
            model_id="deepseek-v4-flash",
            platform_id="deepseek-v4-flash",
            mode="official",
            provider="DeepSeek",
            billing_type="按量计费",
            billing_unit="CNY",
            currency="CNY",
            unit=1000000,
            billing_mode="pay_as_you_go",
            price_rows=[
                NormalizedPriceRow(
                    kind="text_token",
                    values={
                        "input_price": "1",
                        "output_price": "2",
                        "currency": "CNY",
                    },
                    raw={"currency": "CNY"},
                )
            ],
            raw_price_info={},
            raw_detail={
                "model_id": "deepseek-v4-flash",
                "exposed_model_name": exposed_model_name,
            },
        )
