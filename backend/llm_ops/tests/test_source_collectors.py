from unittest import mock

from django.test import TestCase

from llm_ops.collectors.official import OFFICIAL_PROVIDER_CONFIGS
from llm_ops.models import LLMProvider, PriceCollectionSource
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
                "https://api-docs.deepseek.com/quick_start/pricing"
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
