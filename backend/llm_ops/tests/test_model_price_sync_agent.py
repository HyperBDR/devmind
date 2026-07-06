from unittest import mock

from django.test import TestCase

from llm_ops.agents.model_price_sync import (
    LiteLLMTrackedChatModel,
    ModelPriceSyncAgentRunner,
    build_llm_ops_agent_model,
)
from llm_ops.models import (
    LLMOpsGlobalConfig,
    LLMProvider,
    PriceCollectionSource,
)


class ModelPriceSyncAgentRunnerTests(TestCase):
    """Runtime Agent orchestration must stay above collector persistence."""

    def test_model_builder_uses_azure_deployment_from_config(self):
        settings_payload = {
            "provider": "azure_openai",
            "model": "gpt-4o",
            "api_key": "key",
            "api_base": "https://example.openai.azure.com/",
            "config": {
                "deployment": "prod-gpt-4o",
                "api_version": "2024-10-01-preview",
            },
        }

        with mock.patch(
            "llm_ops.agents.model_price_sync.definition."
            "resolve_price_sync_llm_settings",
            return_value=settings_payload,
        ):
            result = build_llm_ops_agent_model()

        self.assertIsInstance(result, LiteLLMTrackedChatModel)
        self.assertEqual(result.provider, "azure_openai")
        self.assertEqual(result.model_name, "gpt-4o")
        self.assertEqual(
            result.config_payload["deployment"],
            "prod-gpt-4o",
        )
        self.assertEqual(
            result.config_payload["api_version"],
            "2024-10-01-preview",
        )

    def test_model_builder_uses_litellm_for_anthropic_config(self):
        with mock.patch(
            "llm_ops.agents.model_price_sync.definition."
            "resolve_price_sync_llm_settings",
            return_value={
                "provider": "anthropic",
                "model": "claude-sonnet-4",
                "api_key": "key",
                "api_base": "https://api.anthropic.com",
                "config_uuid": "8b33ddcb-2896-4df4-bbfc-85b42cb65ec7",
                "config": {},
            },
        ):
            result = build_llm_ops_agent_model()

        self.assertIsInstance(result, LiteLLMTrackedChatModel)
        self.assertEqual(result.provider, "anthropic")
        self.assertEqual(result.model_name, "claude-sonnet-4")
        self.assertEqual(
            result.config_uuid,
            "8b33ddcb-2896-4df4-bbfc-85b42cb65ec7",
        )

    def test_model_builder_normalizes_google_config_to_gemini(self):
        with mock.patch(
            "llm_ops.agents.model_price_sync.definition."
            "resolve_price_sync_llm_settings",
            return_value={
                "provider": "google",
                "model": "gemini-2.5-pro",
                "api_key": "key",
                "api_base": "",
                "config": {},
            },
        ):
            result = build_llm_ops_agent_model()

        self.assertIsInstance(result, LiteLLMTrackedChatModel)
        self.assertEqual(result.provider, "gemini")
        self.assertEqual(result.model_name, "gemini-2.5-pro")
        self.assertEqual(result.config_payload["api_key"], "key")

    def test_skill_tools_list_configured_sources_from_global_config(self):
        provider = LLMProvider.objects.create(name="阿里云", code="aliyun")
        selected = PriceCollectionSource.objects.create(
            name="Aliyun Official",
            slug="aliyun-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://help.aliyun.com/zh/model-studio/model-pricing"
            ),
            currency="CNY",
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )
        PriceCollectionSource.objects.create(
            name="Manual Sheet",
            slug="manual-sheet",
            source_category=PriceCollectionSource.SOURCE_CATEGORY_MANUAL,
            endpoint_url="https://example.com/manual",
            currency="USD",
            is_enabled=True,
            updates_model_prices=False,
        )
        config = LLMOpsGlobalConfig.get_solo()
        config.price_collection_source_ids = [selected.id]
        config.save()

        runner = ModelPriceSyncAgentRunner(config=config)
        tools = {
            tool.name: tool
            for tool in runner.get_skill_tools("model-price-sync")
        }

        payload = tools["list_configured_price_sources"].invoke({})

        self.assertEqual(len(payload["sources"]), 1)
        self.assertEqual(payload["sources"][0]["id"], selected.id)
        self.assertEqual(payload["sources"][0]["provider_code"], "aliyun")

    def test_system_prompt_includes_official_source_sync_contract(self):
        runner = ModelPriceSyncAgentRunner()

        prompt = "\n".join(runner.build_system_prompt_fragments())

        self.assertIn("Official Source Contract", prompt)
        self.assertIn("standard JSON catalog", prompt)
        self.assertIn("SKU-level evidence", prompt)
        self.assertIn("Do not merge `deepseek-v3`", prompt)
        self.assertIn("Result Logging", prompt)

    def test_skill_tools_collect_vendor_price_catalog_without_persisting(self):
        provider = LLMProvider.objects.create(name="阿里云", code="aliyun")
        source = PriceCollectionSource.objects.create(
            name="Aliyun Official",
            slug="aliyun-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://help.aliyun.com/zh/model-studio/model-pricing"
            ),
            currency="CNY",
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )
        runner = ModelPriceSyncAgentRunner(
            source_ids=[source.id],
            verify_source=False,
        )
        tools = {
            tool.name: tool
            for tool in runner.get_skill_tools("model-price-sync")
        }

        payload = tools["collect_vendor_price_catalog"].invoke(
            {"source_id": source.id}
        )

        self.assertEqual(
            payload["schema_version"],
            "llm_ops.model_price_catalog.v1",
        )
        self.assertEqual(payload["source_type"], "provider_adapter")
        self.assertEqual(payload["provider"]["code"], "aliyun")
        self.assertGreater(payload["total_models"], 0)
        self.assertEqual(provider.models.count(), 0)
        self.assertEqual(source.collection_runs.count(), 0)

    def test_collect_source_delegates_to_platform_collector(self):
        provider = LLMProvider.objects.create(name="阿里云", code="aliyun")
        source = PriceCollectionSource.objects.create(
            name="Aliyun Official",
            slug="aliyun-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://help.aliyun.com/zh/model-studio/model-pricing"
            ),
            currency="CNY",
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )
        runner = ModelPriceSyncAgentRunner(
            source_ids=[source.id],
            verify_source=False,
        )

        with mock.patch(
            "llm_ops.agents.model_price_sync.definition.collect_price_source"
        ) as mock_collect:
            mock_collect.return_value = {"models": 1, "changed": 1}
            result = runner.collect_source(source.id)

        mock_collect.assert_called_once_with(source, verify_source=False)
        self.assertEqual(result, {"models": 1, "changed": 1})
        self.assertEqual(runner.succeeded, 1)
        self.assertEqual(runner.source_results["aliyun-official"], result)

    def test_execute_collects_code_supported_sources_without_agent(self):
        provider = LLMProvider.objects.create(name="阿里云", code="aliyun")
        source = PriceCollectionSource.objects.create(
            name="Aliyun Official",
            slug="aliyun-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://help.aliyun.com/zh/model-studio/model-pricing"
            ),
            currency="CNY",
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )
        runner = ModelPriceSyncAgentRunner(
            source_ids=[source.id],
            verify_source=False,
        )

        with (
            mock.patch(
                "llm_ops.agents.model_price_sync.definition."
                "build_llm_ops_agent_model"
            ) as mock_build_model,
            mock.patch(
                "llm_ops.agents.model_price_sync.definition."
                "collect_price_source"
            ) as mock_collect,
        ):
            mock_collect.return_value = {"models": 1, "changed": 1}
            result = runner.execute()

        mock_build_model.assert_not_called()
        mock_collect.assert_called_once_with(source, verify_source=False)
        self.assertEqual(result["success"], True)
        self.assertEqual(result["sources"], 1)
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(
            result["source_results"]["aliyun-official"],
            {"models": 1, "changed": 1},
        )

    def test_explicit_source_ids_keep_supported_auto_sources(self):
        provider = LLMProvider.objects.create(name="阿里云", code="aliyun")
        source = PriceCollectionSource.objects.create(
            name="Aliyun Official",
            slug="aliyun-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://help.aliyun.com/zh/model-studio/model-pricing"
            ),
            currency="CNY",
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )
        runner = ModelPriceSyncAgentRunner(source_ids=[source.id])

        self.assertEqual(runner.list_configured_sources(), [source])

    def test_explicit_source_ids_skip_non_auto_sources(self):
        provider = LLMProvider.objects.create(name="阿里云", code="aliyun")
        source = PriceCollectionSource.objects.create(
            name="Aliyun Qwen Plus Official",
            slug="aliyun-qwen-plus-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://help.aliyun.com/zh/model-studio/model-pricing"
            ),
            currency="CNY",
            is_enabled=True,
            updates_model_prices=True,
        )
        runner = ModelPriceSyncAgentRunner(source_ids=[source.id])

        self.assertEqual(runner.list_configured_sources(), [])

    def test_stale_global_selection_does_not_fallback_to_all(self):
        openai = LLMProvider.objects.create(name="OpenAI", code="openai")
        source = PriceCollectionSource.objects.create(
            name="OpenAI Official",
            slug="openai-official",
            provider=openai,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://openai.com/api/pricing/",
            currency="USD",
            is_enabled=True,
            updates_model_prices=True,
        )
        aliyun = LLMProvider.objects.create(name="阿里云", code="aliyun")
        PriceCollectionSource.objects.create(
            name="Aliyun Official",
            slug="aliyun-official",
            provider=aliyun,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://help.aliyun.com/zh/model-studio/model-pricing"
            ),
            currency="CNY",
            is_enabled=True,
            updates_model_prices=True,
        )
        config = LLMOpsGlobalConfig.get_solo()
        config.price_collection_source_ids = [source.id]
        config.save()
        runner = ModelPriceSyncAgentRunner(config=config)

        self.assertEqual(runner.list_configured_sources(), [])

    def test_execute_returns_noop_when_global_collection_disabled(self):
        config = LLMOpsGlobalConfig.get_solo()
        config.price_collection_enabled = False
        config.save()
        runner = ModelPriceSyncAgentRunner(config=config)

        with mock.patch(
            "llm_ops.agents.model_price_sync.definition."
            "build_llm_ops_agent_model"
        ) as mock_build_model:
            result = runner.execute()

        mock_build_model.assert_not_called()
        self.assertEqual(
            result,
            {
                "success": True,
                "sources": 0,
                "succeeded": 0,
                "failed": 0,
                "skipped": 0,
                "source_results": {},
                "error_message": "",
            },
        )

    def test_execute_returns_noop_when_selected_sources_are_unsupported(self):
        unknown = LLMProvider.objects.create(
            name="Unknown AI",
            code="unknown-ai",
        )
        source = PriceCollectionSource.objects.create(
            name="Unknown Official",
            slug="unknown-ai-official",
            provider=unknown,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://example.com/pricing",
            currency="USD",
            is_enabled=True,
            updates_model_prices=True,
        )
        runner = ModelPriceSyncAgentRunner(source_ids=[source.id])

        with mock.patch(
            "llm_ops.agents.model_price_sync.definition."
            "build_llm_ops_agent_model"
        ) as mock_build_model:
            result = runner.execute()

        mock_build_model.assert_not_called()
        self.assertEqual(result["sources"], 0)
        self.assertEqual(result["succeeded"], 0)
        self.assertEqual(result["failed"], 0)

    def test_collect_source_skips_disabled_sources_without_collecting(self):
        provider = LLMProvider.objects.create(name="阿里云", code="aliyun")
        source = PriceCollectionSource.objects.create(
            name="Aliyun Official",
            slug="aliyun-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://help.aliyun.com/zh/model-studio/model-pricing"
            ),
            currency="CNY",
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=False,
            updates_model_prices=True,
        )
        runner = ModelPriceSyncAgentRunner(source_ids=[source.id])

        with mock.patch(
            "llm_ops.agents.model_price_sync.definition.collect_price_source"
        ) as mock_collect:
            result = runner.collect_source(source.id)

        mock_collect.assert_not_called()
        self.assertEqual(result, {"skipped": True})
        self.assertEqual(runner.skipped, 1)

    def test_collect_source_records_failure_without_raising(self):
        provider = LLMProvider.objects.create(name="阿里云", code="aliyun")
        source = PriceCollectionSource.objects.create(
            name="Aliyun Official",
            slug="aliyun-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://help.aliyun.com/zh/model-studio/model-pricing"
            ),
            currency="CNY",
            collection_method=(
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            is_enabled=True,
            updates_model_prices=True,
        )
        runner = ModelPriceSyncAgentRunner(source_ids=[source.id])

        with mock.patch(
            "llm_ops.agents.model_price_sync.definition.collect_price_source"
        ) as mock_collect:
            mock_collect.side_effect = RuntimeError("upstream timeout")
            result = runner.collect_source(source.id)

        self.assertEqual(
            result,
            {"success": False, "error": "upstream timeout"},
        )
        self.assertEqual(runner.failed, 1)
        self.assertEqual(runner.source_results["aliyun-official"], result)
