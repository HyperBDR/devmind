from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from llm_ops.collection_services import (
    ensure_official_source,
    sync_configured_official_model_prices,
    sync_official_provider_model_prices,
)
from llm_ops.models import (
    CollectedModelPriceSnapshot,
    LLMModel,
    LLMProvider,
    ModelPriceItem,
    PriceCollectionRun,
    PriceCollectionSource,
)
from llm_ops.seed_data import seed_initial_price_sheet


class MockPricingResponse:
    """Small requests response double for official pricing pages."""

    def __init__(
        self,
        text,
        status_code=200,
        content_type="text/html; charset=utf-8",
    ):
        self.text = text
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class OfficialCollectionSyncTests(TestCase):
    def setUp(self):
        seed_initial_price_sheet()

    def test_sync_openai_official_prices_updates_usd_models(self):
        provider = LLMProvider.objects.get(code="openai")

        stats = sync_official_provider_model_prices(
            provider=provider,
            verify_source=False,
        )

        model = LLMModel.objects.get(
            provider=provider,
            source__slug="openai-official",
            code="gpt-4o-mini",
        )
        self.assertEqual(model.currency, "USD")
        self.assertEqual(model.input_price_per_million, Decimal("0.150000"))
        self.assertEqual(model.output_price_per_million, Decimal("0.600000"))
        self.assertGreaterEqual(stats["models"], 13)
        self.assertGreater(stats["skipped"], 0)

        snapshot = CollectedModelPriceSnapshot.objects.get(
            source__slug="openai-official",
            source_platform_id="gpt-4o-mini",
        )
        self.assertEqual(snapshot.currency, "USD")
        self.assertEqual(snapshot.raw_price_info["unit"], 1000000)

        price_item = ModelPriceItem.objects.get(
            model=model,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            is_current=True,
        )
        self.assertEqual(price_item.billing_unit, "per_1m_tokens")
        self.assertEqual(price_item.unit_price, Decimal("0.150000"))

    @patch("llm_ops.collectors.official.requests.get")
    def test_sync_official_prices_reads_configured_source_content(
        self,
        mock_get,
    ):
        provider = LLMProvider.objects.get(code="openai")
        mock_get.return_value = MockPricingResponse(
            """
            <table>
              <tr>
                <td>gpt-4o-mini</td>
                <td>Input $0.11 / 1M tokens</td>
                <td>Output $0.44 / 1M tokens</td>
              </tr>
            </table>
            """,
        )

        stats = sync_official_provider_model_prices(provider=provider)

        model = LLMModel.objects.get(
            provider=provider,
            source__slug="openai-official",
            code="gpt-4o-mini",
        )
        self.assertEqual(model.input_price_per_million, Decimal("0.110000"))
        self.assertEqual(model.output_price_per_million, Decimal("0.440000"))
        self.assertEqual(stats["models"], 1)
        self.assertGreater(stats["skipped"], 0)
        mock_get.assert_called_once()

    @patch("llm_ops.collectors.official.requests.get")
    def test_sync_official_prices_falls_back_when_source_has_no_prices(
        self,
        mock_get,
    ):
        provider = LLMProvider.objects.get(code="openai")
        mock_get.return_value = MockPricingResponse(
            "<html><body>No matching model pricing here.</body></html>",
        )

        stats = sync_official_provider_model_prices(provider=provider)

        run = PriceCollectionRun.objects.latest("id")
        self.assertEqual(run.status, PriceCollectionRun.STATUS_SUCCEEDED)
        self.assertGreater(stats["models"], 0)
        snapshot = CollectedModelPriceSnapshot.objects.get(
            source__slug="openai-official",
            source_platform_id="gpt-4o-mini",
        )
        self.assertIn(
            "source_parse_warning",
            snapshot.raw_detail["official_source_fetch"],
        )

    @patch("llm_ops.collectors.official.requests.get")
    def test_sync_official_prices_reads_models_dev_json(self, mock_get):
        provider = LLMProvider.objects.get(code="openai")
        source = PriceCollectionSource.objects.get(slug="openai-official")
        source.endpoint_url = "https://models.dev/api.json"
        source.save(update_fields=["endpoint_url"])
        mock_get.return_value = MockPricingResponse(
            """
            {
              "openai": {
                "id": "openai",
                "name": "OpenAI",
                "models": {
                  "gpt-4o-mini": {
                    "id": "gpt-4o-mini",
                    "name": "GPT-4o mini",
                    "family": "gpt-4o-mini",
                    "modalities": {
                      "input": ["text", "image"],
                      "output": ["text"]
                    },
                    "cost": {
                      "input": 0.12,
                      "output": 0.48,
                      "cache_read": 0.06
                    }
                  }
                }
              }
            }
            """,
            content_type="application/json",
        )

        stats = sync_official_provider_model_prices(provider=provider)

        model = LLMModel.objects.get(
            provider=provider,
            source__slug="openai-official",
            code="gpt-4o-mini",
        )
        source.refresh_from_db()
        self.assertEqual(model.currency, "USD")
        self.assertEqual(source.currency, "USD")
        self.assertEqual(model.input_price_per_million, Decimal("0.120000"))
        self.assertEqual(model.output_price_per_million, Decimal("0.480000"))
        self.assertEqual(stats["models"], 1)
        snapshot = CollectedModelPriceSnapshot.objects.get(
            source=source,
            source_platform_id="gpt-4o-mini",
        )
        self.assertEqual(
            snapshot.raw_detail["official_source_fetch"][
                "models_dev_provider_key"
            ],
            "openai",
        )
        self.assertNotIn("json", snapshot.raw_detail["official_source_fetch"])

    @patch("llm_ops.collectors.official.requests.get")
    def test_sync_models_dev_source_maps_aliyun_to_usd_source(
        self,
        mock_get,
    ):
        provider = LLMProvider.objects.get(code="aliyun")
        source = PriceCollectionSource.objects.get(slug="aliyun-official")
        source.endpoint_url = "https://models.dev/api.json"
        source.save(update_fields=["endpoint_url"])
        mock_get.return_value = MockPricingResponse(
            """
            {
              "alibaba-cn": {
                "id": "alibaba-cn",
                "name": "Alibaba (China)",
                "models": {
                  "qwen-plus": {
                    "id": "qwen-plus",
                    "name": "Qwen Plus",
                    "family": "qwen-plus",
                    "modalities": {
                      "input": ["text"],
                      "output": ["text"]
                    },
                    "cost": {
                      "input": 0.115,
                      "output": 0.287
                    }
                  }
                }
              }
            }
            """,
            content_type="application/json",
        )

        sync_official_provider_model_prices(provider=provider)

        source.refresh_from_db()
        model = LLMModel.objects.get(
            provider=provider,
            source__slug="aliyun-official",
            code="qwen-plus",
        )
        self.assertEqual(source.currency, "USD")
        self.assertEqual(model.currency, "USD")
        self.assertEqual(model.input_price_per_million, Decimal("0.115000"))
        self.assertEqual(model.output_price_per_million, Decimal("0.287000"))

    def test_sync_aliyun_official_prices_keeps_cny_currency(self):
        provider = LLMProvider.objects.get(code="aliyun")

        stats = sync_official_provider_model_prices(
            provider=provider,
            verify_source=False,
        )

        model = LLMModel.objects.get(
            provider=provider,
            source__slug="aliyun-official",
            code="qwen-plus",
        )
        deepseek = LLMModel.objects.get(
            provider=provider,
            source__slug="aliyun-official",
            code="deepseek-r1",
        )
        qwen3 = LLMModel.objects.get(
            provider=provider,
            source__slug="aliyun-official",
            code="qwen3-235b-a22b-instruct-2507",
        )
        self.assertEqual(model.currency, "CNY")
        self.assertEqual(model.input_price_per_million, Decimal("0.800000"))
        self.assertEqual(model.output_price_per_million, Decimal("2.000000"))
        self.assertEqual(deepseek.input_price_per_million, Decimal("4.000000"))
        self.assertEqual(
            deepseek.output_price_per_million,
            Decimal("16.000000"),
        )
        self.assertEqual(qwen3.input_price_per_million, Decimal("2.000000"))
        self.assertEqual(qwen3.output_price_per_million, Decimal("8.000000"))
        self.assertEqual(stats["models"], 19)

        source = PriceCollectionSource.objects.get(slug="aliyun-official")
        self.assertEqual(source.currency, "CNY")
        self.assertEqual(source.source_category, "official_provider")
        self.assertTrue(source.updates_model_prices)

    def test_sync_volcengine_official_prices_keeps_cny_currency(self):
        provider = LLMProvider.objects.get(code="volcengine")

        stats = sync_official_provider_model_prices(
            provider=provider,
            verify_source=False,
        )

        model = LLMModel.objects.get(
            provider=provider,
            source__slug="volcengine-official",
            code="deepseek-r1-250528",
        )
        self.assertEqual(stats["models"], 1)
        self.assertEqual(stats["skipped"], 11)
        self.assertEqual(model.currency, "CNY")
        self.assertEqual(model.name, "DeepSeek R1 250528")
        self.assertEqual(model.input_price_per_million, Decimal("4.000000"))
        self.assertEqual(model.output_price_per_million, Decimal("16.000000"))

    def test_sync_aliyun_wanx_prices_uses_image_and_video_units(self):
        provider = LLMProvider.objects.get(code="aliyun-wanx")

        stats = sync_official_provider_model_prices(
            provider=provider,
            verify_source=False,
        )

        image_model = LLMModel.objects.get(
            provider=provider,
            source__slug="aliyun-wanx-official",
            code="qwen-image",
        )
        video_model = LLMModel.objects.get(
            provider=provider,
            source__slug="aliyun-wanx-official",
            code="wan2.5-t2v-preview",
        )
        self.assertEqual(stats["models"], 12)
        self.assertEqual(image_model.currency, "CNY")
        self.assertEqual(
            image_model.image_output_price_per_image,
            Decimal("0.080000"),
        )
        self.assertEqual(video_model.currency, "CNY")
        self.assertEqual(
            video_model.video_output_price_per_second,
            Decimal("0.120000"),
        )
        self.assertEqual(
            video_model.video_resolution_prices["1080P"]["output"],
            "0.48",
        )
        image_item = ModelPriceItem.objects.get(
            model=image_model,
            dimension=ModelPriceItem.DIMENSION_IMAGE_OUTPUT,
            billing_unit=ModelPriceItem.UNIT_PER_IMAGE,
            is_current=True,
        )
        video_item = ModelPriceItem.objects.get(
            model=video_model,
            dimension=ModelPriceItem.DIMENSION_VIDEO_OUTPUT,
            spec__resolution="1080P",
            spec__audio="included",
            is_current=True,
        )
        self.assertEqual(image_item.unit_price, Decimal("0.080000"))
        self.assertEqual(video_item.unit_price, Decimal("0.480000"))

    def test_sync_anthropic_matches_dated_model_aliases(self):
        provider = LLMProvider.objects.get(code="anthropic")

        sync_official_provider_model_prices(
            provider=provider,
            verify_source=False,
        )

        model = LLMModel.objects.get(
            provider=provider,
            source__slug="anthropic-official",
            code="claude-sonnet-4-6-20260218",
        )
        sonnet_45 = LLMModel.objects.get(
            provider=provider,
            source__slug="anthropic-official",
            code="claude-sonnet-4-5-20250929",
        )
        sonnet_4 = LLMModel.objects.get(
            provider=provider,
            source__slug="anthropic-official",
            code="claude-sonnet-4-20250514",
        )
        self.assertEqual(model.currency, "USD")
        self.assertEqual(model.input_price_per_million, Decimal("3.000000"))
        self.assertEqual(model.output_price_per_million, Decimal("15.000000"))
        self.assertEqual(model.name, "Claude Sonnet 4.6")
        self.assertEqual(sonnet_45.name, "Claude Sonnet 4.5")
        self.assertEqual(sonnet_4.name, "Claude Sonnet 4")

    @patch("llm_ops.collection_services.collect_official_pricing_catalog")
    def test_sync_official_prices_uses_configured_source_url(
        self,
        mock_collect,
    ):
        provider = LLMProvider.objects.get(code="openai")
        source = PriceCollectionSource.objects.get(slug="openai-official")
        source.endpoint_url = "https://example.com/pricing"
        source.save(update_fields=["endpoint_url"])
        mock_collect.return_value.total_models = 0
        mock_collect.return_value.models = []
        mock_collect.return_value.source_url = source.endpoint_url

        sync_official_provider_model_prices(
            provider=provider,
            source=source,
            verify_source=True,
        )

        mock_collect.assert_called_once()
        self.assertEqual(
            mock_collect.call_args.kwargs["source_url"],
            "https://example.com/pricing",
        )

    def test_ensure_official_source_preserves_runtime_configuration(self):
        provider = LLMProvider.objects.get(code="openai")
        source = PriceCollectionSource.objects.get(slug="openai-official")
        source.endpoint_url = "https://example.com/custom-pricing"
        source.is_enabled = False
        source.save(update_fields=["endpoint_url", "is_enabled"])

        ensured = ensure_official_source(provider=provider)

        self.assertEqual(ensured.endpoint_url, source.endpoint_url)
        self.assertFalse(ensured.is_enabled)

    def test_sync_configured_provider_prices_records_skipped_models(self):
        results = sync_configured_official_model_prices(
            provider_codes=["google"],
            verify_source=False,
        )

        self.assertIn("google", results)
        run = PriceCollectionRun.objects.get(source__slug="google-official")
        self.assertEqual(run.status, PriceCollectionRun.STATUS_SUCCEEDED)
        self.assertEqual(run.metadata["currency"], "USD")
        self.assertEqual(run.skipped_count, 0)
        model = LLMModel.objects.get(
            provider__code="google",
            source__slug="google-official",
            code="gemini-3-pro-preview",
        )
        self.assertEqual(model.name, "Gemini 3 Pro Preview")
        self.assertEqual(model.input_price_per_million, Decimal("2.000000"))
        self.assertEqual(model.output_price_per_million, Decimal("12.000000"))
