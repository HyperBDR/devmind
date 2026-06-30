from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from llm_ops.collection_services import (
    ensure_official_source,
    official_model_source_slug as build_official_model_source_slug,
    sync_configured_official_model_prices,
    sync_meta_models_from_models_dev,
    sync_official_provider_model_prices,
)
from llm_ops.collectors.official import (
    OFFICIAL_PROVIDER_CONFIGS,
    collect_official_pricing_catalog,
)
from llm_ops.models import (
    CollectedModelPriceSnapshot,
    LLMModel,
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    PriceCollectionRun,
    PriceCollectionSource,
)
from llm_ops.seed_data import seed_initial_price_sheet
from llm_ops.skill_runner import MODEL_PRICE_CATALOG_SCHEMA_VERSION


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

    def official_model_source_slug(self, provider_code, model_code):
        return build_official_model_source_slug(provider_code, model_code)

    def test_sync_openai_official_prices_updates_usd_models(self):
        provider = LLMProvider.objects.get(code="openai")

        stats = sync_official_provider_model_prices(
            provider=provider,
            verify_source=False,
        )

        model = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "openai",
                "gpt-4o-mini",
            ),
            code="gpt-4o-mini",
        )
        self.assertEqual(model.currency, "USD")
        self.assertEqual(model.input_price_per_million, Decimal("0.150000"))
        self.assertEqual(model.output_price_per_million, Decimal("0.600000"))
        self.assertGreaterEqual(stats["models"], 13)
        self.assertGreater(stats["skipped"], 0)

        snapshot = CollectedModelPriceSnapshot.objects.get(
            source__slug=self.official_model_source_slug(
                "openai",
                "gpt-4o-mini",
            ),
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

    def test_sync_openai_official_prices_uses_one_source_per_model(self):
        provider = LLMProvider.objects.get(code="openai")

        sync_official_provider_model_prices(
            provider=provider,
            verify_source=False,
        )

        mini = LLMModel.objects.get(
            provider=provider,
            code="gpt-4o-mini",
            source__slug=self.official_model_source_slug(
                "openai",
                "gpt-4o-mini",
            ),
        )
        gpt4o = LLMModel.objects.get(
            provider=provider,
            code="gpt-4o",
            source__slug=self.official_model_source_slug(
                "openai",
                "gpt-4o",
            ),
        )
        self.assertNotEqual(mini.source_id, gpt4o.source_id)
        self.assertTrue(
            CollectedModelPriceSnapshot.objects.filter(
                source=mini.source,
                source_platform_id="gpt-4o-mini",
            ).exists()
        )
        self.assertTrue(
            ModelPriceItem.objects.filter(
                source=mini.source,
                model=mini,
                is_current=True,
            ).exists()
        )

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
            source__slug=self.official_model_source_slug(
                "openai",
                "gpt-4o-mini",
            ),
            code="gpt-4o-mini",
        )
        self.assertEqual(model.input_price_per_million, Decimal("0.110000"))
        self.assertEqual(model.output_price_per_million, Decimal("0.440000"))
        self.assertGreaterEqual(stats["models"], 1)
        self.assertGreaterEqual(stats["skipped"], 0)
        mock_get.assert_called_once()

    @patch("llm_ops.collectors.official.requests.get")
    def test_sync_anthropic_source_reads_cache_hits_column(self, mock_get):
        provider = LLMProvider.objects.get(code="anthropic")
        mock_get.return_value = MockPricingResponse(
            """
            <table>
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Base Input Tokens</th>
                  <th>5m Cache Writes</th>
                  <th>1h Cache Writes</th>
                  <th>Cache Hits &amp; Refreshes</th>
                  <th>Output Tokens</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Claude Sonnet 4.6</td>
                  <td>$3 / MTok</td>
                  <td>$3.75 / MTok</td>
                  <td>$6 / MTok</td>
                  <td>$0.30 / MTok</td>
                  <td>$15 / MTok</td>
                </tr>
              </tbody>
            </table>
            """,
        )

        catalog = collect_official_pricing_catalog(
            provider_code=provider.code,
            model_codes={"claude-sonnet-4-6-20260218"},
            source_url=(
                "https://docs.anthropic.com/en/docs/about-claude/pricing"
            ),
        )

        self.assertEqual(catalog.total_models, 1)
        row = catalog.models[0].price_rows[0]
        self.assertEqual(row.values["input_price"], "3")
        self.assertEqual(row.values["output_price"], "15")
        self.assertEqual(row.values["cache_input_price"], "0.30")

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
            source__slug=self.official_model_source_slug(
                "openai",
                "gpt-4o-mini",
            ),
            source_platform_id="gpt-4o-mini",
        )
        self.assertIn(
            "source_parse_warning",
            snapshot.raw_detail["official_source_fetch"],
        )

    @patch("llm_ops.collectors.official.requests.get")
    def test_sync_official_prices_falls_back_for_partially_parsed_source(
        self,
        mock_get,
    ):
        provider = LLMProvider.objects.get(code="aliyun")
        mock_get.return_value = MockPricingResponse(
            """
            <table>
              <tr>
                <td>qwen-plus</td>
                <td>输入价格 ￥0.88</td>
                <td>输出价格 ￥2.20</td>
              </tr>
            </table>
            """,
        )

        stats = sync_official_provider_model_prices(provider=provider)

        qwen_plus = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "aliyun",
                "qwen-plus",
            ),
            code="qwen-plus",
        )
        qwen_turbo = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "aliyun",
                "qwen-turbo",
            ),
            code="qwen-turbo",
        )
        run = PriceCollectionRun.objects.get(source__slug="aliyun-official")
        self.assertGreater(stats["models"], 1)
        self.assertEqual(
            qwen_plus.input_price_per_million,
            Decimal("0.880000"),
        )
        self.assertEqual(
            qwen_turbo.input_price_per_million,
            Decimal("0.300000"),
        )
        self.assertIn(
            "qwen-turbo",
            run.metadata["source_parse_fallback_model_ids"],
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
            source__slug=self.official_model_source_slug(
                "openai",
                "gpt-4o-mini",
            ),
            code="gpt-4o-mini",
        )
        source.refresh_from_db()
        self.assertEqual(model.currency, "USD")
        self.assertEqual(source.currency, "USD")
        self.assertEqual(model.input_price_per_million, Decimal("0.120000"))
        self.assertEqual(model.output_price_per_million, Decimal("0.480000"))
        self.assertEqual(
            model.cache_input_price_per_million,
            Decimal("0.060000"),
        )
        cache_item = ModelPriceItem.objects.get(
            model=model,
            dimension=ModelPriceItem.DIMENSION_CACHE_INPUT,
            is_current=True,
        )
        self.assertEqual(cache_item.unit_price, Decimal("0.060000"))
        self.assertEqual(stats["models"], 1)
        snapshot = CollectedModelPriceSnapshot.objects.get(
            source__slug=self.official_model_source_slug(
                "openai",
                "gpt-4o-mini",
            ),
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
            source__slug=self.official_model_source_slug(
                "aliyun",
                "qwen-plus",
            ),
            code="qwen-plus",
        )
        self.assertEqual(source.currency, "USD")
        self.assertEqual(model.currency, "USD")
        self.assertEqual(model.input_price_per_million, Decimal("0.115000"))
        self.assertEqual(model.output_price_per_million, Decimal("0.287000"))

    @patch("llm_ops.collectors.official.requests.get")
    def test_sync_meta_models_from_models_dev_is_idempotent(self, mock_get):
        mock_get.return_value = MockPricingResponse(
            """
            {
              "openai": {
                "id": "openai",
                "name": "OpenAI",
                "models": {
                  "openai/gpt-real-test": {
                    "id": "openai/gpt-real-test",
                    "name": "GPT Real Test",
                    "family": "gpt-mini",
                    "reasoning": false,
                    "tool_call": true,
                    "structured_output": true,
                    "release_date": "2024-07-18",
                    "last_updated": "2024-07-18",
                    "modalities": {
                      "input": ["text", "image"],
                      "output": ["text"]
                    },
                    "limit": {"context": 128000, "output": 16384}
                  }
                }
              },
              "supplier": {
                "id": "supplier",
                "name": "Supplier",
                "models": {
                  "openai/gpt-real-test": {
                    "id": "openai/gpt-real-test",
                    "name": "GPT Real Test"
                  },
                  "meta-llama/llama-3.3-70b-instruct-fp8-fast": {
                    "id": "meta-llama/llama-3.3-70b-instruct-fp8-fast",
                    "name": "Supplier Llama Variant"
                  }
                }
              }
            }
            """,
            content_type="application/json",
        )

        stats = sync_meta_models_from_models_dev()
        second_stats = sync_meta_models_from_models_dev()

        meta = MetaModel.objects.get(code="gpt-real-test")
        self.assertEqual(stats["models"], 1)
        self.assertEqual(second_stats["created"], 0)
        self.assertEqual(
            MetaModel.objects.filter(code="gpt-real-test").count(),
            1,
        )
        self.assertFalse(
            MetaModel.objects.filter(code__startswith="llama-3.3").exists(),
        )
        self.assertEqual(meta.vendor.code, "openai")
        self.assertEqual(meta.family, "gpt-mini")
        self.assertEqual(meta.modality, MetaModel.MODALITY_MULTIMODAL)
        self.assertEqual(meta.context_window, 128000)
        self.assertIn("tool_calling", meta.capabilities["features"])
        self.assertEqual(
            meta.metadata["models_dev"]["source_url"],
            "https://models.dev/api.json",
        )

    @patch("llm_ops.collectors.official.requests.get")
    def test_sync_meta_models_from_models_dev_preserves_manual_data(
        self,
        mock_get,
    ):
        openai = LLMProvider.objects.get(code="openai")
        MetaModel.objects.update_or_create(
            code="gpt-4o-mini",
            defaults={
                "name": "Manual GPT",
                "vendor": openai,
                "family": "Manual Family",
                "aliases": ["manual-alias"],
                "context_window": 256000,
            },
        )
        mock_get.return_value = MockPricingResponse(
            """
            {
              "openai": {
                "models": {
                  "openai/gpt-4o-mini": {
                    "id": "openai/gpt-4o-mini",
                    "name": "GPT-4o Mini",
                    "family": "gpt-mini",
                    "modalities": {
                      "input": ["text"],
                      "output": ["text"]
                    },
                    "limit": {"context": 128000, "output": 16384}
                  }
                }
              }
            }
            """,
            content_type="application/json",
        )

        sync_meta_models_from_models_dev()

        meta = MetaModel.objects.get(code="gpt-4o-mini")
        self.assertEqual(meta.name, "Manual GPT")
        self.assertEqual(meta.family, "Manual Family")
        self.assertEqual(meta.context_window, 256000)
        self.assertIn("manual-alias", meta.aliases)
        self.assertIn("openai/gpt-4o-mini", meta.aliases)

    @patch("llm_ops.collectors.official.requests.get")
    def test_sync_meta_models_from_models_dev_cleans_stale_online_rows(
        self,
        mock_get,
    ):
        stale = MetaModel.objects.create(
            code="supplier-only-noise",
            name="Supplier Only Noise",
            metadata={
                "models_dev": {
                    "id": "supplier/supplier-only-noise",
                },
            },
        )
        linked = MetaModel.objects.create(
            code="linked-online-model",
            name="Linked Online Model",
            vendor=LLMProvider.objects.get(code="openai"),
            metadata={
                "models_dev": {
                    "id": "supplier/linked-online-model",
                },
            },
        )
        LLMModel.objects.create(
            provider=LLMProvider.objects.get(code="openai"),
            meta_model=linked,
            name="Linked Online Model",
            code="linked-online-model",
        )
        mock_get.return_value = MockPricingResponse(
            """
            {
              "openai": {
                "models": {
                  "openai/gpt-clean-test": {
                    "id": "openai/gpt-clean-test",
                    "name": "GPT Clean Test"
                  }
                }
              },
              "openrouter": {
                "models": {
                  "openai/gpt-router-noise": {
                    "id": "openai/gpt-router-noise",
                    "name": "GPT Router Noise"
                  }
                }
              }
            }
            """,
            content_type="application/json",
        )

        stats = sync_meta_models_from_models_dev()

        self.assertEqual(stats["deleted"], 1)
        self.assertFalse(MetaModel.objects.filter(id=stale.id).exists())
        self.assertTrue(MetaModel.objects.filter(id=linked.id).exists())
        self.assertFalse(
            MetaModel.objects.filter(code="gpt-router-noise").exists(),
        )
        self.assertTrue(
            MetaModel.objects.filter(code="gpt-clean-test").exists(),
        )

    def test_sync_aliyun_official_prices_keeps_cny_currency(self):
        provider = LLMProvider.objects.get(code="aliyun")

        stats = sync_official_provider_model_prices(
            provider=provider,
            verify_source=False,
        )

        model = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "aliyun",
                "qwen-plus",
            ),
            code="qwen-plus",
        )
        deepseek = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "aliyun",
                "deepseek-r1",
            ),
            code="deepseek-r1",
        )
        deepseek_v3_1 = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "aliyun",
                "deepseek-v3.1",
            ),
            code="deepseek-v3.1",
        )
        deepseek_v3_2 = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "aliyun",
                "deepseek-v3.2",
            ),
            code="deepseek-v3.2",
        )
        deepseek_v4_pro = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "aliyun",
                "deepseek-v4-pro",
            ),
            code="deepseek-v4-pro",
        )
        deepseek_v4_flash = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "aliyun",
                "deepseek-v4-flash",
            ),
            code="deepseek-v4-flash",
        )
        deepseek_distill_qwen_32b = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "aliyun",
                "deepseek-r1-distill-qwen-32b",
            ),
            code="deepseek-r1-distill-qwen-32b",
        )
        qwen3 = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "aliyun",
                "qwen3-235b-a22b-instruct-2507",
            ),
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
        self.assertEqual(
            deepseek_v3_1.input_price_per_million,
            Decimal("4.000000"),
        )
        self.assertEqual(
            deepseek_v3_1.output_price_per_million,
            Decimal("12.000000"),
        )
        self.assertEqual(
            deepseek_v3_2.input_price_per_million,
            Decimal("2.000000"),
        )
        self.assertEqual(
            deepseek_v3_2.output_price_per_million,
            Decimal("3.000000"),
        )
        self.assertEqual(
            deepseek_v4_pro.input_price_per_million,
            Decimal("12.000000"),
        )
        self.assertEqual(
            deepseek_v4_pro.output_price_per_million,
            Decimal("24.000000"),
        )
        self.assertEqual(
            deepseek_v4_flash.input_price_per_million,
            Decimal("1.000000"),
        )
        self.assertEqual(
            deepseek_v4_flash.output_price_per_million,
            Decimal("2.000000"),
        )
        self.assertEqual(
            deepseek_distill_qwen_32b.input_price_per_million,
            Decimal("2.000000"),
        )
        self.assertEqual(
            deepseek_distill_qwen_32b.output_price_per_million,
            Decimal("6.000000"),
        )
        self.assertEqual(qwen3.input_price_per_million, Decimal("2.000000"))
        self.assertEqual(qwen3.output_price_per_million, Decimal("8.000000"))
        self.assertGreaterEqual(stats["models"], 22)

        source = PriceCollectionSource.objects.get(slug="aliyun-official")
        self.assertEqual(source.currency, "CNY")
        self.assertEqual(source.source_category, "official_provider")
        self.assertTrue(source.updates_model_prices)

    @patch("llm_ops.collectors.official.requests.get")
    def test_sync_aliyun_official_prices_reads_deepseek_v4_rows(
        self,
        mock_get,
    ):
        provider = LLMProvider.objects.get(code="aliyun")
        mock_get.return_value = MockPricingResponse(
            """
            <table>
              <tr>
                <td>deepseek-v4-pro</td>
                <td>中国内地</td>
                <td>12 元</td>
                <td>24 元</td>
              </tr>
              <tr>
                <td>deepseek-v4-flash</td>
                <td>中国内地</td>
                <td>1 元</td>
                <td>2 元</td>
              </tr>
              <tr>
                <td>deepseek-v3.2</td>
                <td>中国内地</td>
                <td>2 元</td>
                <td>3 元</td>
              </tr>
              <tr>
                <td>deepseek-v3.1</td>
                <td>中国内地</td>
                <td>4 元</td>
                <td>12 元</td>
              </tr>
            </table>
            """,
        )

        stats = sync_official_provider_model_prices(provider=provider)

        pro = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "aliyun",
                "deepseek-v4-pro",
            ),
            code="deepseek-v4-pro",
        )
        flash = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "aliyun",
                "deepseek-v4-flash",
            ),
            code="deepseek-v4-flash",
        )
        self.assertEqual(pro.input_price_per_million, Decimal("12.000000"))
        self.assertEqual(pro.output_price_per_million, Decimal("24.000000"))
        self.assertEqual(flash.input_price_per_million, Decimal("1.000000"))
        self.assertEqual(flash.output_price_per_million, Decimal("2.000000"))
        v3_2 = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "aliyun",
                "deepseek-v3.2",
            ),
            code="deepseek-v3.2",
        )
        v3_1 = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "aliyun",
                "deepseek-v3.1",
            ),
            code="deepseek-v3.1",
        )
        self.assertEqual(v3_2.input_price_per_million, Decimal("2.000000"))
        self.assertEqual(v3_2.output_price_per_million, Decimal("3.000000"))
        self.assertEqual(v3_1.input_price_per_million, Decimal("4.000000"))
        self.assertEqual(v3_1.output_price_per_million, Decimal("12.000000"))
        self.assertNotIn("deepseek-v4-pro", stats["skipped_model_codes"])
        self.assertNotIn("deepseek-v4-flash", stats["skipped_model_codes"])

    def test_sync_aliyun_official_prices_backfills_configured_models(self):
        provider = LLMProvider.objects.get(code="aliyun")
        LLMModel.objects.filter(provider=provider).delete()
        LLMModel.objects.create(
            provider=provider,
            name="Qwen Plus",
            code="qwen-plus",
            modality=LLMModel.MODALITY_TEXT,
            currency="CNY",
        )

        stats = sync_official_provider_model_prices(
            provider=provider,
            verify_source=False,
        )

        self.assertGreater(stats["models"], 1)
        for model_code in ("qwen-turbo", "qwq-32b", "text-embedding-v4"):
            self.assertTrue(
                LLMModel.objects.filter(
                    provider=provider,
                    source__slug=self.official_model_source_slug(
                        "aliyun",
                        model_code,
                    ),
                    code=model_code,
                ).exists(),
            )
            self.assertNotIn(model_code, stats["skipped_model_codes"])

    @patch("requests.get")
    def test_sync_aliyun_official_prices_collects_unconfigured_page_rows(
        self,
        mock_get,
    ):
        provider = LLMProvider.objects.get(code="aliyun")
        mock_get.return_value = MockPricingResponse(
            """
            <table>
              <tr>
                <th>模型 ID（Model ID）</th>
                <th>服务部署范围</th>
                <th>输入单价（每百万 Token）</th>
                <th>输出单价（每百万 Token）</th>
                <th>免费额度</th>
              </tr>
              <tr>
                <td>
                  <p>qwen-new-2026</p>
                  <blockquote>上下文缓存享有折扣</blockquote>
                </td>
                <td>中国内地</td>
                <td>3.5 元</td>
                <td>7 元</td>
                <td>-</td>
              </tr>
            </table>
            """,
        )

        stats = sync_official_provider_model_prices(provider=provider)

        model = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "aliyun",
                "qwen-new-2026",
            ),
            code="qwen-new-2026",
        )
        self.assertEqual(stats["models"], 1)
        self.assertEqual(model.input_price_per_million, Decimal("3.500000"))
        self.assertEqual(model.output_price_per_million, Decimal("7.000000"))
        self.assertTrue(
            ModelPriceItem.objects.filter(
                model=model,
                source=model.source,
                is_current=True,
            ).exists(),
        )

    def test_aliyun_official_config_uses_pricing_page(self):
        self.assertEqual(
            OFFICIAL_PROVIDER_CONFIGS["aliyun"].source_url,
            "https://help.aliyun.com/zh/model-studio/model-pricing",
        )
        self.assertEqual(
            OFFICIAL_PROVIDER_CONFIGS["aliyun-wanx"].source_url,
            "https://help.aliyun.com/zh/model-studio/model-pricing",
        )

    def test_ensure_official_source_updates_aliyun_legacy_url(self):
        provider = LLMProvider.objects.get(code="aliyun")
        source = PriceCollectionSource.objects.get(slug="aliyun-official")
        source.endpoint_url = "https://help.aliyun.com/zh/model-studio/models"
        source.save(update_fields=["endpoint_url"])

        ensured = ensure_official_source(provider=provider)

        self.assertEqual(
            ensured.endpoint_url,
            "https://help.aliyun.com/zh/model-studio/model-pricing",
        )

    def test_sync_volcengine_official_prices_keeps_cny_currency(self):
        provider = LLMProvider.objects.get(code="volcengine")

        stats = sync_official_provider_model_prices(
            provider=provider,
            verify_source=False,
        )

        model = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "volcengine",
                "deepseek-r1-250528",
            ),
            code="deepseek-r1-250528",
        )
        self.assertGreaterEqual(stats["models"], 1)
        self.assertGreaterEqual(stats["skipped"], 0)
        self.assertEqual(model.currency, "CNY")
        self.assertEqual(model.meta_model.code, "deepseek-r1")
        self.assertIn("deepseek-r1-250528", model.meta_model.aliases)
        # LLMModel keeps the supplier SKU display name; MetaModel is
        # normalized to the family-level identity above.
        self.assertEqual(model.name, "DeepSeek R1 0528")
        self.assertEqual(model.input_price_per_million, Decimal("4.000000"))
        self.assertEqual(model.output_price_per_million, Decimal("16.000000"))

    def test_sync_deepseek_official_prices_includes_cache_hit(self):
        provider = LLMProvider.objects.get(code="deepseek")

        stats = sync_official_provider_model_prices(
            provider=provider,
            verify_source=False,
        )

        source = PriceCollectionSource.objects.get(
            slug=self.official_model_source_slug("deepseek", "deepseek-v3"),
        )
        input_item = ModelPriceItem.objects.get(
            source=source,
            model__code="deepseek-v3",
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
        )
        cache_item = ModelPriceItem.objects.get(
            source=source,
            model__code="deepseek-v3",
            dimension=ModelPriceItem.DIMENSION_CACHE_INPUT,
        )
        output_item = ModelPriceItem.objects.get(
            source=source,
            model__code="deepseek-v3",
            dimension=ModelPriceItem.DIMENSION_TEXT_OUTPUT,
        )
        self.assertGreaterEqual(stats["models"], 5)
        self.assertEqual(source.currency, "USD")
        self.assertEqual(input_item.unit_price, Decimal("0.280000"))
        self.assertEqual(cache_item.unit_price, Decimal("0.028000"))
        self.assertEqual(output_item.unit_price, Decimal("0.420000"))

    def test_sync_aliyun_wanx_prices_uses_image_and_video_units(self):
        provider = LLMProvider.objects.get(code="aliyun-wanx")

        stats = sync_official_provider_model_prices(
            provider=provider,
            verify_source=False,
        )

        image_model = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "aliyun-wanx",
                "qwen-image",
            ),
            code="qwen-image",
        )
        video_model = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "aliyun-wanx",
                "wan2.5-t2v-preview",
            ),
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
            source__slug=self.official_model_source_slug(
                "anthropic",
                "claude-sonnet-4-6-20260218",
            ),
            code="claude-sonnet-4-6-20260218",
        )
        sonnet_45 = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "anthropic",
                "claude-sonnet-4-5-20250929",
            ),
            code="claude-sonnet-4-5-20250929",
        )
        sonnet_4 = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "anthropic",
                "claude-sonnet-4-20250514",
            ),
            code="claude-sonnet-4-20250514",
        )
        haiku_45 = LLMModel.objects.get(
            provider=provider,
            source__slug=self.official_model_source_slug(
                "anthropic",
                "claude-haiku-4-5-20251001",
            ),
            code="claude-haiku-4-5-20251001",
        )
        self.assertEqual(model.currency, "USD")
        self.assertEqual(model.input_price_per_million, Decimal("3.000000"))
        self.assertEqual(model.output_price_per_million, Decimal("15.000000"))
        self.assertEqual(model.name, "Claude Sonnet 4.6")
        self.assertEqual(sonnet_45.name, "Claude Sonnet 4.5")
        self.assertEqual(sonnet_4.name, "Claude Sonnet 4")
        cache_item = ModelPriceItem.objects.get(
            model=haiku_45,
            dimension=ModelPriceItem.DIMENSION_CACHE_INPUT,
            is_current=True,
        )
        self.assertEqual(cache_item.unit_price, Decimal("0.100000"))

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
            provider_codes=["aliyun"],
            verify_source=False,
        )

        self.assertIn("aliyun", results)
        run = PriceCollectionRun.objects.get(source__slug="aliyun-official")
        self.assertEqual(run.status, PriceCollectionRun.STATUS_SUCCEEDED)
        self.assertEqual(run.metadata["currency"], "CNY")
        self.assertGreaterEqual(run.skipped_count, 0)
        model = LLMModel.objects.get(
            provider__code="aliyun",
            source__slug=self.official_model_source_slug(
                "aliyun",
                "qwen-plus",
            ),
            code="qwen-plus",
        )
        self.assertEqual(model.name, "Qwen Plus")
        self.assertEqual(model.input_price_per_million, Decimal("0.800000"))
        self.assertEqual(model.output_price_per_million, Decimal("2.000000"))

    def test_sync_official_prices_records_vendor_skill_catalog_metadata(self):
        provider = LLMProvider.objects.get(code="aliyun")

        sync_official_provider_model_prices(
            provider=provider,
            verify_source=False,
        )

        run = PriceCollectionRun.objects.get(source__slug="aliyun-official")
        self.assertEqual(
            run.metadata["catalog_schema_version"],
            MODEL_PRICE_CATALOG_SCHEMA_VERSION,
        )
        self.assertEqual(
            run.metadata["catalog_source_type"],
            "vendor_python_skill",
        )
        self.assertEqual(run.metadata["vendor_skill_provider"], "aliyun")

    @patch("llm_ops.collection_services.sync_official_provider_model_prices")
    def test_sync_configured_provider_prices_continues_after_failure(
        self,
        mock_sync,
    ):
        """One failed official source must not stop other providers."""

        def fake_sync(provider, *, verify_source=True):
            if provider.code == "aliyun":
                raise RuntimeError("source blocked")
            return {
                "models": 1,
                "created": 1,
                "updated": 0,
                "skipped": 0,
                "changed": 1,
                "unchanged": 0,
                "skipped_model_codes": [],
            }

        mock_sync.side_effect = fake_sync

        results = sync_configured_official_model_prices(
            provider_codes=["aliyun", "aliyun-wanx"],
            verify_source=False,
        )

        self.assertIn("source blocked", results["aliyun"]["error"])
        self.assertEqual(results["aliyun"]["models"], 0)
        self.assertEqual(results["aliyun-wanx"]["models"], 1)
        self.assertEqual(mock_sync.call_count, 2)
