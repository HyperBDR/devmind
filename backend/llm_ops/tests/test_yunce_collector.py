from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from llm_ops.collection_services import (
    slugify_provider,
    sync_yunce_text_model_prices,
)
from llm_ops.collectors.yunce import (
    CollectedModelPricing,
    CollectedPricingCatalog,
    NormalizedPriceRow,
    normalize_price_rows,
)
from llm_ops.models import (
    CollectedModelPriceHistory,
    CollectedModelPriceSnapshot,
    LLMModel,
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    PriceCollectionRun,
    PriceCollectionSource,
)


class YuncePriceNormalizerTests(TestCase):
    def test_normalizes_text_tiered_pricing_with_zero_range(self):
        rows = normalize_price_rows(
            {
                "type": "Text",
                "mode": "normal",
                "price_info": {
                    "unit": 1000000,
                    "tiered_pricing": True,
                    "pricing_detail": [
                        {
                            "input_start": 0,
                            "input_end": 1000000,
                            "output_start": 0,
                            "output_end": 1000000,
                            "input_price": {"non_cache": 2.5},
                            "output_price": {"non_thinking": 10},
                        }
                    ],
                },
            }
        )

        self.assertEqual(rows[0].kind, "text_token")
        self.assertEqual(rows[0].values["input_token_range"], "0-1000000")
        self.assertEqual(rows[0].values["output_token_range"], "0-1000000")
        self.assertEqual(rows[0].values["input_price"], 2.5)
        self.assertEqual(rows[0].values["output_price"], 10)

    def test_normalizes_image_count_pricing(self):
        rows = normalize_price_rows(
            {
                "type": "Image",
                "price_info": {
                    "pricing_detail_by_count": [
                        {"image_size": "1024x1024", "unit_price": 0.04}
                    ]
                },
            }
        )

        self.assertEqual(rows[0].kind, "image_size")
        self.assertEqual(rows[0].values["image_size"], "1024x1024")
        self.assertEqual(rows[0].values["unit_price"], 0.04)

    def test_normalizes_video_resolution_pricing(self):
        rows = normalize_price_rows(
            {
                "type": "Video",
                "price_info": {
                    "video_price": [
                        {"resolution": "1080p", "unit_price": 0.08}
                    ]
                },
            }
        )

        self.assertEqual(rows[0].kind, "video_resolution_output")
        self.assertEqual(rows[0].values["resolution"], "1080p")
        self.assertEqual(rows[0].values["price"], 0.08)


class YunceCollectionSyncTests(TestCase):
    def test_slugify_provider_uses_ascii_slug(self):
        self.assertTrue(
            slugify_provider("阿里云 百炼").startswith("provider-")
        )
        self.assertEqual(slugify_provider("Azure OpenAI"), "azure-openai")

    @patch("llm_ops.collection_services.collect_yunce_pricing_catalog")
    def test_sync_model_prices_upserts_models_and_snapshots(
        self,
        mock_collect,
    ):
        mock_collect.return_value = CollectedPricingCatalog(
            source_url="https://llm.guohe-sh.com/",
            total_models=3,
            models=[
                CollectedModelPricing(
                    model_source="OpenAI",
                    model_type="文本模型",
                    source_model_type="Text",
                    name="GPT-4o",
                    model_id="gpt-4o",
                    platform_id=1,
                    mode="normal",
                    provider="OpenAI",
                    billing_type="按量计费",
                    billing_unit="USD",
                    currency="USD",
                    unit=1000000,
                    billing_mode="",
                    price_rows=[
                        NormalizedPriceRow(
                            kind="text_token",
                            values={
                                "input_price": 2.5,
                                "output_price": 10,
                            },
                            raw={},
                        )
                    ],
                    raw_price_info={},
                    raw_detail={},
                ),
                CollectedModelPricing(
                    model_source="OpenAI",
                    model_type="图片模型",
                    source_model_type="Image",
                    name="GPT Image",
                    model_id="gpt-image",
                    platform_id=2,
                    mode="normal",
                    provider="OpenAI",
                    billing_type="按量计费",
                    billing_unit="USD",
                    currency="USD",
                    unit=1000000,
                    billing_mode="",
                    price_rows=[
                        NormalizedPriceRow(
                            kind="image_token",
                            values={
                                "input_price": 5,
                                "image_output_price": 30,
                            },
                            raw={},
                        )
                    ],
                    raw_price_info={},
                    raw_detail={},
                ),
                CollectedModelPricing(
                    model_source="Google云",
                    model_type="视频模型",
                    source_model_type="Video",
                    name="Veo",
                    model_id="veo",
                    platform_id=3,
                    mode="normal",
                    provider="Google",
                    billing_type="按量计费",
                    billing_unit="USD",
                    currency="USD",
                    unit=None,
                    billing_mode="",
                    price_rows=[
                        NormalizedPriceRow(
                            kind="video_resolution_output",
                            values={
                                "resolution": "1080p",
                                "price": 0.08,
                                "no_audio_price": 0.04,
                            },
                            raw={},
                        )
                    ],
                    raw_price_info={},
                    raw_detail={},
                ),
            ],
        )

        source = PriceCollectionSource.objects.create(
            name="Official Yunce",
            slug="official-yunce",
            source_type=PriceCollectionSource.SOURCE_TYPE_YUNCE,
            updates_model_prices=True,
        )
        result = sync_yunce_text_model_prices(
            username="user",
            password="secret",
            source=source,
        )

        self.assertEqual(result["models"], 3)
        self.assertEqual(result["created"], 3)
        provider = LLMProvider.objects.get(code="openai")
        model = LLMModel.objects.get(provider=provider, code="gpt-4o")
        self.assertEqual(model.input_price_per_million, Decimal("2.5"))
        self.assertEqual(model.output_price_per_million, Decimal("10"))
        self.assertEqual(model.source, source)
        image_model = LLMModel.objects.get(provider=provider, code="gpt-image")
        self.assertEqual(image_model.input_price_per_million, Decimal("5"))
        self.assertEqual(image_model.output_price_per_million, Decimal("30"))
        video_model = LLMModel.objects.get(code="veo")
        self.assertEqual(
            video_model.video_output_price_per_second,
            Decimal("0.08"),
        )
        self.assertEqual(
            video_model.video_resolution_prices["1080p"]["output"],
            "0.08",
        )
        self.assertEqual(PriceCollectionRun.objects.count(), 1)
        self.assertEqual(CollectedModelPriceSnapshot.objects.count(), 3)
        self.assertEqual(CollectedModelPriceHistory.objects.count(), 3)
        self.assertEqual(
            CollectedModelPriceHistory.objects.filter(is_current=True).count(),
            3,
        )

    @patch("llm_ops.collection_services.collect_yunce_pricing_catalog")
    def test_sync_model_prices_can_collect_without_promoting_prices(
        self,
        mock_collect,
    ):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        source = PriceCollectionSource.objects.create(
            provider=provider,
            name="OpenAI Yunce Snapshot",
            slug="openai-yunce-snapshot",
            source_type=PriceCollectionSource.SOURCE_TYPE_YUNCE,
            updates_model_prices=False,
        )
        mock_collect.return_value = CollectedPricingCatalog(
            source_url="https://llm.guohe-sh.com/",
            total_models=1,
            models=[
                CollectedModelPricing(
                    model_source="OpenAI",
                    model_type="文本模型",
                    source_model_type="Text",
                    name="GPT Snapshot",
                    model_id="gpt-snapshot",
                    platform_id=18,
                    mode="normal",
                    provider="OpenAI",
                    billing_type="按量计费",
                    billing_unit="USD",
                    currency="USD",
                    unit=1000000,
                    billing_mode="",
                    price_rows=[
                        NormalizedPriceRow(
                            kind="text_token",
                            values={
                                "input_price": 2.5,
                                "output_price": 10,
                            },
                            raw={},
                        )
                    ],
                    raw_price_info={},
                    raw_detail={},
                )
            ],
        )

        sync_yunce_text_model_prices(
            username="user",
            password="secret",
            source=source,
        )

        model = LLMModel.objects.get(code="gpt-snapshot")
        self.assertEqual(model.provider, provider)
        self.assertIsNone(model.source)
        self.assertEqual(model.input_price_per_million, Decimal("0"))
        self.assertEqual(model.output_price_per_million, Decimal("0"))
        self.assertEqual(CollectedModelPriceSnapshot.objects.count(), 1)
        self.assertEqual(CollectedModelPriceHistory.objects.count(), 1)

    @patch("llm_ops.collection_services.collect_yunce_pricing_catalog")
    def test_sync_model_prices_reuses_existing_base_model(self, mock_collect):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        base_model = LLMModel.objects.create(
            provider=provider,
            name="GPT-4o",
            code="gpt-4o",
        )
        source = PriceCollectionSource.objects.create(
            provider=provider,
            name="OpenAI Yunce Snapshot",
            slug="openai-yunce-base-model",
            source_type=PriceCollectionSource.SOURCE_TYPE_YUNCE,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            updates_model_prices=False,
        )
        mock_collect.return_value = CollectedPricingCatalog(
            source_url="https://llm.guohe-sh.com/",
            total_models=1,
            models=[
                CollectedModelPricing(
                    model_source="OpenAI",
                    model_type="文本模型",
                    source_model_type="Text",
                    name="GPT-4o",
                    model_id="gpt-4o",
                    platform_id=99,
                    mode="normal",
                    provider="OpenAI",
                    billing_type="按量计费",
                    billing_unit="USD",
                    currency="USD",
                    unit=1000000,
                    billing_mode="",
                    price_rows=[
                        NormalizedPriceRow(
                            kind="text_token",
                            values={
                                "input_price": 2.5,
                                "output_price": 10,
                            },
                            raw={},
                        )
                    ],
                    raw_price_info={},
                    raw_detail={},
                )
            ],
        )

        sync_yunce_text_model_prices(
            username="user",
            password="secret",
            source=source,
        )

        self.assertEqual(LLMModel.objects.count(), 1)
        snapshot = CollectedModelPriceSnapshot.objects.get(
            source_platform_id="99",
        )
        history = CollectedModelPriceHistory.objects.get(
            source_platform_id="99",
        )
        items = list(ModelPriceItem.objects.filter(source=source))
        self.assertEqual(snapshot.model, base_model)
        self.assertEqual(history.model, base_model)
        self.assertEqual(len(items), 2)
        self.assertTrue(all(item.model == base_model for item in items))

    @patch("llm_ops.collection_services.collect_yunce_pricing_catalog")
    def test_sync_model_prices_uses_raw_model_code_for_meta_binding(
        self,
        mock_collect,
    ):
        provider = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        source = PriceCollectionSource.objects.create(
            provider=provider,
            name="DeepSeek Yunce Snapshot",
            slug="deepseek-yunce-raw-code",
            source_type=PriceCollectionSource.SOURCE_TYPE_YUNCE,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            updates_model_prices=False,
        )
        mock_collect.return_value = CollectedPricingCatalog(
            source_url="https://llm.guohe-sh.com/",
            total_models=1,
            models=[
                CollectedModelPricing(
                    model_source="DeepSeek",
                    model_type="文本模型",
                    source_model_type="Text",
                    name="DeepSeek R1 0528",
                    model_id="",
                    platform_id=109,
                    mode="normal",
                    provider="DeepSeek",
                    billing_type="按量计费",
                    billing_unit="CNY",
                    currency="CNY",
                    unit=1000000,
                    billing_mode="",
                    price_rows=[
                        NormalizedPriceRow(
                            kind="text_token",
                            values={
                                "input_price": 4,
                                "output_price": 16,
                            },
                            raw={},
                        )
                    ],
                    raw_price_info={},
                    raw_detail={
                        "model_info": {
                            "model_id": "deepseek-r1-250528",
                        }
                    },
                )
            ],
        )

        sync_yunce_text_model_prices(
            username="user",
            password="secret",
            source=source,
        )

        model = LLMModel.objects.get()
        snapshot = CollectedModelPriceSnapshot.objects.get(
            source_platform_id="109",
        )
        history = CollectedModelPriceHistory.objects.get(
            source_platform_id="109",
        )
        items = list(ModelPriceItem.objects.filter(source=source))

        self.assertEqual(model.code, "deepseek-r1-250528")
        self.assertEqual(model.meta_model.code, "deepseek-r1")
        self.assertEqual(
            MetaModel.objects.filter(code="deepseek-r1").count(),
            1,
        )
        self.assertEqual(snapshot.source_model_id, "deepseek-r1-250528")
        self.assertEqual(snapshot.meta_model_id, model.meta_model_id)
        self.assertEqual(history.meta_model_id, model.meta_model_id)
        self.assertEqual(len(items), 2)
        self.assertTrue(
            all(item.meta_model_id == model.meta_model_id for item in items)
        )

    @patch("llm_ops.collection_services.collect_yunce_pricing_catalog")
    def test_sync_model_prices_uses_source_provider(self, mock_collect):
        provider = LLMProvider.objects.create(
            name="Anthropic",
            code="anthropic",
        )
        source = PriceCollectionSource.objects.create(
            provider=provider,
            name="Anthropic Yunce",
            slug="anthropic-yunce",
            source_type=PriceCollectionSource.SOURCE_TYPE_YUNCE,
        )
        mock_collect.return_value = CollectedPricingCatalog(
            source_url="https://llm.guohe-sh.com/",
            total_models=1,
            models=[
                CollectedModelPricing(
                    model_source="Some Aggregator Name",
                    model_type="文本模型",
                    source_model_type="Text",
                    name="Claude Sonnet",
                    model_id="claude-sonnet",
                    platform_id=8,
                    mode="normal",
                    provider="Anthropic",
                    billing_type="按量计费",
                    billing_unit="USD",
                    currency="USD",
                    unit=1000000,
                    billing_mode="",
                    price_rows=[
                        NormalizedPriceRow(
                            kind="text_token",
                            values={
                                "input_price": 3,
                                "output_price": 15,
                            },
                            raw={},
                        )
                    ],
                    raw_price_info={},
                    raw_detail={},
                )
            ],
        )

        sync_yunce_text_model_prices(
            username="user",
            password="secret",
            source=source,
        )

        model = LLMModel.objects.get(code="claude-sonnet")
        snapshot = CollectedModelPriceSnapshot.objects.get(
            source_platform_id="8",
        )
        self.assertEqual(model.provider, provider)
        self.assertEqual(snapshot.provider, provider)

    @patch("llm_ops.collection_services.collect_yunce_pricing_catalog")
    def test_sync_model_prices_skips_other_provider_models(
        self,
        mock_collect,
    ):
        provider = LLMProvider.objects.create(
            name="OpenAI",
            code="openai",
        )
        source = PriceCollectionSource.objects.create(
            provider=provider,
            name="OpenAI Yunce",
            slug="openai-yunce",
            source_type=PriceCollectionSource.SOURCE_TYPE_YUNCE,
        )
        mock_collect.return_value = CollectedPricingCatalog(
            source_url="https://llm.guohe-sh.com/",
            total_models=2,
            models=[
                CollectedModelPricing(
                    model_source="OpenAI",
                    model_type="文本模型",
                    source_model_type="Text",
                    name="GPT-4o",
                    model_id="gpt-4o",
                    platform_id=1,
                    mode="normal",
                    provider="OpenAI",
                    billing_type="按量计费",
                    billing_unit="USD",
                    currency="USD",
                    unit=1000000,
                    billing_mode="",
                    price_rows=[
                        NormalizedPriceRow(
                            kind="text_token",
                            values={
                                "input_price": 2.5,
                                "output_price": 10,
                            },
                            raw={},
                        )
                    ],
                    raw_price_info={},
                    raw_detail={},
                ),
                CollectedModelPricing(
                    model_source="Anthropic",
                    model_type="文本模型",
                    source_model_type="Text",
                    name="Claude Sonnet",
                    model_id="claude-sonnet",
                    platform_id=2,
                    mode="normal",
                    provider="Anthropic",
                    billing_type="按量计费",
                    billing_unit="USD",
                    currency="USD",
                    unit=1000000,
                    billing_mode="",
                    price_rows=[
                        NormalizedPriceRow(
                            kind="text_token",
                            values={
                                "input_price": 3,
                                "output_price": 15,
                            },
                            raw={},
                        )
                    ],
                    raw_price_info={},
                    raw_detail={},
                ),
            ],
        )

        result = sync_yunce_text_model_prices(
            username="user",
            password="secret",
            source=source,
        )

        self.assertEqual(result["models"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertTrue(LLMModel.objects.filter(code="gpt-4o").exists())
        self.assertFalse(
            LLMModel.objects.filter(code="claude-sonnet").exists()
        )
        run = PriceCollectionRun.objects.get()
        self.assertEqual(run.skipped_count, 1)
        self.assertEqual(run.metadata["skipped_provider_names"], ["Anthropic"])

    @patch("llm_ops.collection_services.collect_yunce_pricing_catalog")
    def test_sync_model_prices_converts_token_unit_to_million(
        self,
        mock_collect,
    ):
        mock_collect.return_value = CollectedPricingCatalog(
            source_url="https://llm.guohe-sh.com/",
            total_models=1,
            models=[
                CollectedModelPricing(
                    model_source="OpenAI",
                    model_type="文本模型",
                    source_model_type="Text",
                    name="GPT Unit",
                    model_id="gpt-unit",
                    platform_id=1,
                    mode="normal",
                    provider="OpenAI",
                    billing_type="按量计费",
                    billing_unit="USD",
                    currency="USD",
                    unit=1000,
                    billing_mode="",
                    price_rows=[
                        NormalizedPriceRow(
                            kind="text_token",
                            values={
                                "input_price": "0.002",
                                "output_price": "0.01",
                                "Cache Hits": "0.001",
                            },
                            raw={},
                        )
                    ],
                    raw_price_info={},
                    raw_detail={},
                )
            ],
        )

        source = PriceCollectionSource.objects.create(
            name="Official Yunce",
            slug="official-unit-yunce",
            source_type=PriceCollectionSource.SOURCE_TYPE_YUNCE,
            updates_model_prices=True,
        )
        sync_yunce_text_model_prices(
            username="user",
            password="secret",
            source=source,
        )

        model = LLMModel.objects.get(code="gpt-unit")
        self.assertEqual(model.input_price_per_million, Decimal("2.000000"))
        self.assertEqual(model.output_price_per_million, Decimal("10.000000"))
        self.assertEqual(
            model.cache_input_price_per_million,
            Decimal("1.000000"),
        )

    @patch("llm_ops.collection_services.collect_yunce_pricing_catalog")
    def test_sync_model_prices_rejects_disabled_source(self, mock_collect):
        source = PriceCollectionSource.objects.create(
            name="Disabled Yunce",
            slug="disabled-yunce",
            source_type=PriceCollectionSource.SOURCE_TYPE_YUNCE,
            is_enabled=False,
        )

        with self.assertRaisesMessage(
            ValueError,
            "Price collection source is disabled.",
        ):
            sync_yunce_text_model_prices(
                username="user",
                password="secret",
                source=source,
            )

        mock_collect.assert_not_called()
        self.assertEqual(PriceCollectionRun.objects.count(), 0)

    @patch("llm_ops.collection_services.upsert_collected_snapshot")
    @patch("llm_ops.collection_services.collect_yunce_pricing_catalog")
    def test_sync_model_prices_rolls_back_model_writes_on_failure(
        self,
        mock_collect,
        mock_snapshot,
    ):
        mock_collect.return_value = CollectedPricingCatalog(
            source_url="https://llm.guohe-sh.com/",
            total_models=1,
            models=[
                CollectedModelPricing(
                    model_source="OpenAI",
                    model_type="文本模型",
                    source_model_type="Text",
                    name="GPT Fails",
                    model_id="gpt-fails",
                    platform_id=1,
                    mode="normal",
                    provider="OpenAI",
                    billing_type="按量计费",
                    billing_unit="USD",
                    currency="USD",
                    unit=1000000,
                    billing_mode="",
                    price_rows=[
                        NormalizedPriceRow(
                            kind="text_token",
                            values={
                                "input_price": 2.5,
                                "output_price": 10,
                            },
                            raw={},
                        )
                    ],
                    raw_price_info={},
                    raw_detail={},
                )
            ],
        )
        mock_snapshot.side_effect = RuntimeError("snapshot failed")

        with self.assertRaisesMessage(RuntimeError, "snapshot failed"):
            sync_yunce_text_model_prices(
                username="user",
                password="secret",
            )

        self.assertFalse(LLMModel.objects.filter(code="gpt-fails").exists())
        run = PriceCollectionRun.objects.get()
        self.assertEqual(run.status, PriceCollectionRun.STATUS_FAILED)

    @patch("llm_ops.collection_services.collect_yunce_pricing_catalog")
    def test_sync_model_prices_only_records_changed_history(
        self,
        mock_collect,
    ):
        mock_collect.return_value = CollectedPricingCatalog(
            source_url="https://llm.guohe-sh.com/",
            total_models=1,
            models=[
                CollectedModelPricing(
                    model_source="OpenAI",
                    model_type="文本模型",
                    source_model_type="Text",
                    name="GPT-4o",
                    model_id="gpt-4o",
                    platform_id=1,
                    mode="normal",
                    provider="OpenAI",
                    billing_type="按量计费",
                    billing_unit="USD",
                    currency="USD",
                    unit=1000000,
                    billing_mode="",
                    price_rows=[
                        NormalizedPriceRow(
                            kind="text_token",
                            values={
                                "input_price": 2.5,
                                "output_price": 10,
                            },
                            raw={},
                        )
                    ],
                    raw_price_info={},
                    raw_detail={},
                )
            ],
        )

        first = sync_yunce_text_model_prices(
            username="user",
            password="secret",
        )
        second = sync_yunce_text_model_prices(
            username="user",
            password="secret",
        )

        self.assertEqual(first["changed"], 1)
        self.assertEqual(first["unchanged"], 0)
        self.assertEqual(second["changed"], 0)
        self.assertEqual(second["unchanged"], 1)
        self.assertEqual(CollectedModelPriceHistory.objects.count(), 1)

        model = mock_collect.return_value.models[0]
        changed_row = NormalizedPriceRow(
            kind="text_token",
            values={
                "input_price": 3,
                "output_price": 12,
            },
            raw={},
        )
        mock_collect.return_value = CollectedPricingCatalog(
            source_url="https://llm.guohe-sh.com/",
            total_models=1,
            models=[
                CollectedModelPricing(
                    model_source=model.model_source,
                    model_type=model.model_type,
                    source_model_type=model.source_model_type,
                    name=model.name,
                    model_id=model.model_id,
                    platform_id=model.platform_id,
                    mode=model.mode,
                    provider=model.provider,
                    billing_type=model.billing_type,
                    billing_unit=model.billing_unit,
                    currency=model.currency,
                    unit=model.unit,
                    billing_mode=model.billing_mode,
                    price_rows=[changed_row],
                    raw_price_info=model.raw_price_info,
                    raw_detail=model.raw_detail,
                )
            ],
        )

        third = sync_yunce_text_model_prices(
            username="user",
            password="secret",
        )

        self.assertEqual(third["changed"], 1)
        self.assertEqual(CollectedModelPriceHistory.objects.count(), 2)
        self.assertEqual(
            CollectedModelPriceHistory.objects.filter(is_current=True).count(),
            1,
        )
        self.assertEqual(
            CollectedModelPriceHistory.objects.filter(
                is_current=False,
            ).count(),
            1,
        )
