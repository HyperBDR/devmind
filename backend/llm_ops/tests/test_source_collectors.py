from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase

from llm_ops.collection_services import (
    sync_vendor_price_source_catalog,
    sync_model_price_items,
    upsert_collected_snapshot,
    upsert_collected_offering,
)
from llm_ops.collectors import CollectedModelPricing, NormalizedPriceRow
from llm_ops.global_config import price_sync_source_queryset
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


class PriceSourceCollectorRegistryTests(TestCase):
    def test_auto_source_dispatches_to_registered_provider_parser(self):
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
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        collector = get_price_source_collector(source)
        self.assertIsNotNone(collector)
        self.assertEqual(collector.collector_id, "auto_price_source")
        self.assertEqual(
            collector.__class__.__name__,
            "AutoPriceSourceCollector",
        )
        self.assertTrue(source_supports_code_collection(source))

        with mock.patch(
            "llm_ops.collection_services.sync_vendor_price_source_catalog"
        ) as mock_sync:
            mock_sync.return_value = {"models": 1}
            result = collect_price_source(
                source,
                verify_source=False,
            )

        mock_sync.assert_called_once_with(
            provider_code="aliyun",
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
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        collector = get_price_source_collector(source)

        self.assertIsNotNone(collector)
        self.assertEqual(collector.collector_id, "auto_price_source")
        self.assertTrue(source_supports_code_collection(source))

    def test_azure_openai_source_dispatches_to_official_collector(self):
        provider = LLMProvider.objects.create(
            name="Azure OpenAI",
            code="azure-openai",
        )
        source = PriceCollectionSource.objects.create(
            name="Azure OpenAI Official",
            slug="azure-openai-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://azure.microsoft.com/en-us/pricing/details/"
                "azure-openai/#pricing"
            ),
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        collector = get_price_source_collector(source)

        self.assertIsNotNone(collector)
        self.assertEqual(collector.collector_id, "auto_price_source")
        self.assertTrue(source_supports_code_collection(source))

    def test_anthropic_source_dispatches_to_official_collector(self):
        provider = LLMProvider.objects.create(
            name="Anthropic",
            code="anthropic",
        )
        source = PriceCollectionSource.objects.create(
            name="Anthropic Official",
            slug="anthropic-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://docs.anthropic.com/en/docs/about-claude/pricing"
            ),
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        collector = get_price_source_collector(source)

        self.assertIsNotNone(collector)
        self.assertEqual(collector.collector_id, "auto_price_source")
        self.assertTrue(source_supports_code_collection(source))

    def test_baidu_source_dispatches_to_official_collector(self):
        provider = LLMProvider.objects.create(
            name="百度千帆",
            code="baidu",
        )
        source = PriceCollectionSource.objects.create(
            name="Baidu Qianfan Official",
            slug="baidu-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://cloud.baidu.com/doc/qianfan/s/wmh4sv6ya",
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        collector = get_price_source_collector(source)

        self.assertIsNotNone(collector)
        self.assertEqual(collector.collector_id, "auto_price_source")
        self.assertTrue(source_supports_code_collection(source))

    def test_google_source_dispatches_to_official_collector(self):
        provider = LLMProvider.objects.create(name="Google", code="google")
        source = PriceCollectionSource.objects.create(
            name="Google Gemini Official",
            slug="google-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://cloud.google.com/gemini-enterprise-agent-platform/"
                "generative-ai/pricing?hl=en"
            ),
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        collector = get_price_source_collector(source)

        self.assertIsNotNone(collector)
        self.assertEqual(collector.collector_id, "auto_price_source")
        self.assertTrue(source_supports_code_collection(source))

    def test_minimax_source_dispatches_to_official_collector(self):
        provider = LLMProvider.objects.create(
            name="MiniMax",
            code="minimax",
        )
        source = PriceCollectionSource.objects.create(
            name="MiniMax Official",
            slug="minimax-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://platform.minimaxi.com/subscribe/"
                "token-plan?tab=api-enterprise"
            ),
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        collector = get_price_source_collector(source)

        self.assertIsNotNone(collector)
        self.assertEqual(collector.collector_id, "auto_price_source")
        self.assertTrue(source_supports_code_collection(source))

    def test_volcengine_source_dispatches_to_official_collector(self):
        provider = LLMProvider.objects.create(
            name="火山方舟",
            code="volcengine",
        )
        source = PriceCollectionSource.objects.create(
            name="VolcEngine Official",
            slug="volcengine-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://www.volcengine.com/docs/82379/1544106?lang=zh"
            ),
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        collector = get_price_source_collector(source)

        self.assertIsNotNone(collector)
        self.assertEqual(collector.collector_id, "auto_price_source")
        self.assertTrue(source_supports_code_collection(source))

    def test_zhipu_source_dispatches_to_official_collector(self):
        provider = LLMProvider.objects.create(
            name="智谱",
            code="zhipu",
        )
        source = PriceCollectionSource.objects.create(
            name="Zhipu Official",
            slug="zhipu-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://bigmodel.cn/pricing",
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        collector = get_price_source_collector(source)

        self.assertIsNotNone(collector)
        self.assertEqual(collector.collector_id, "auto_price_source")
        self.assertTrue(source_supports_code_collection(source))

    def test_auto_source_without_registered_parser_is_not_supported(self):
        provider = LLMProvider.objects.create(
            name="Unknown AI",
            code="unknown-ai",
        )
        source = PriceCollectionSource.objects.create(
            name="Unknown Official",
            slug="unknown-ai-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://example.com/pricing",
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        collector = get_price_source_collector(source)

        self.assertIsNone(collector)
        self.assertFalse(source_supports_code_collection(source))

    def test_auto_collection_ignores_source_category(self):
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
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        collector = get_price_source_collector(source)

        self.assertIsNotNone(collector)
        self.assertTrue(source_supports_code_collection(source))

    def test_non_auto_source_does_not_support_code_collection(self):
        provider = LLMProvider.objects.create(name="DeepSeek", code="deepseek")
        source = PriceCollectionSource.objects.create(
            name="SiliconFlow Sheet",
            slug="siliconflow-sheet",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            endpoint_url="https://example.com/pricing",
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_MANUAL_ENTRY
            ),
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
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        collector = get_price_source_collector(source)

        self.assertIsNotNone(collector)
        self.assertEqual(collector.collector_id, "auto_price_source")
        self.assertTrue(source_supports_code_collection(source))

        with mock.patch(
            "llm_ops.collection_services.sync_vendor_price_source_catalog"
        ) as mock_sync:
            mock_sync.return_value = {"models": 2}
            result = collect_price_source(source, verify_source=False)

        mock_sync.assert_called_once_with(
            provider_code="siliconflow",
            source=source,
            verify_source=False,
        )
        self.assertEqual(result, {"models": 2})

    def test_price_sync_queryset_includes_code_backed_supplier_source(self):
        aliyun = LLMProvider.objects.create(name="阿里云", code="aliyun")
        aliyun_source = PriceCollectionSource.objects.create(
            name="Aliyun Official",
            slug="aliyun-official",
            provider=aliyun,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://help.aliyun.com/zh/model-studio/model-pricing"
            ),
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )
        siliconflow_source = PriceCollectionSource.objects.create(
            name="SiliconFlow Pricing",
            slug="siliconflow-pricing",
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            endpoint_url="https://siliconflow.cn/pricing",
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )
        unsupported_source = PriceCollectionSource.objects.create(
            name="Supplier Sheet",
            slug="supplier-sheet",
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            endpoint_url="https://example.com/pricing",
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        source_ids = set(
            price_sync_source_queryset().values_list("id", flat=True)
        )

        self.assertIn(aliyun_source.id, source_ids)
        self.assertIn(siliconflow_source.id, source_ids)
        self.assertNotIn(unsupported_source.id, source_ids)

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
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        self.assertIsNone(get_price_source_collector(source))
        self.assertFalse(source_supports_code_collection(source))

    def test_source_sync_fails_when_catalog_is_empty(self):
        provider = LLMProvider.objects.create(
            name="MiniMax",
            code="minimax",
        )
        source = PriceCollectionSource.objects.create(
            name="MiniMax Official",
            slug="minimax-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://platform.minimaxi.com/subscribe/"
                "token-plan?tab=api-enterprise"
            ),
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        with mock.patch(
            "llm_ops.collection_services.collect_vendor_price_catalog"
        ) as mock_collect:
            mock_collect.return_value = {
                "schema_version": "llm_ops.model_price_catalog.v1",
                "source_type": "provider_adapter",
                "source_url": source.endpoint_url,
                "total_models": 0,
                "provider": {
                    "code": "minimax",
                    "name": "MiniMax",
                    "currency": "CNY",
                },
                "models": [],
                "notes": "",
                "raw_payload": {
                    "collector": "llm_ops.price_collectors.minimax",
                },
            }
            with self.assertRaisesMessage(
                ValueError,
                "returned no models",
            ):
                sync_vendor_price_source_catalog(
                    provider_code="minimax",
                    source=source,
                    verify_source=True,
                )

        run = PriceCollectionRun.objects.get(source=source)
        self.assertEqual(run.status, PriceCollectionRun.STATUS_FAILED)
        self.assertIn("returned no models", run.error_message)

    def test_source_sync_preserves_collector_value_errors(self):
        provider = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
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
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )

        with mock.patch(
            "llm_ops.collection_services.collect_vendor_price_catalog"
        ) as mock_collect:
            mock_collect.side_effect = ValueError("bad parser payload")
            with self.assertRaisesMessage(ValueError, "bad parser payload"):
                sync_vendor_price_source_catalog(
                    provider_code="deepseek",
                    source=source,
                    verify_source=True,
                )

        run = PriceCollectionRun.objects.get(source=source)
        self.assertEqual(run.status, PriceCollectionRun.STATUS_FAILED)
        self.assertEqual(run.error_message, "bad parser payload")


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
