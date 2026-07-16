from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from ai_assistant.provider import AssistantCapabilityProvider
from llm_ops.assistant import assistant_provider, get_assistant_capability
from llm_ops.assistant_tools import execute_llm_ops_tool
from llm_ops.models import (
    ChannelModelPrice,
    ChannelModelPriceHistory,
    LLMModel,
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    PriceCollectionRun,
    PriceCollectionSource,
    ProcurementChannel,
)


class LLMOpsAssistantToolTests(TestCase):
    def setUp(self):
        self.provider = LLMProvider.objects.create(
            name="OpenAI",
            code="openai",
        )
        self.operational_meta = MetaModel.objects.create(
            name="GPT Operational",
            code="gpt-operational",
        )
        self.reference_meta = MetaModel.objects.create(
            name="GPT Reference",
            code="gpt-reference",
        )
        self.operational_model = self._create_model(
            self.operational_meta,
            "GPT Operational",
            "gpt-operational",
        )
        self.reference_model = self._create_model(
            self.reference_meta,
            "GPT Reference",
            "gpt-reference",
        )
        self.channel = ProcurementChannel.objects.create(
            name="Primary Channel",
            code="primary-channel",
        )
        ChannelModelPrice.objects.create(
            channel=self.channel,
            model=self.operational_model,
            meta_model=self.operational_meta,
            is_listed=False,
        )

    def _create_model(self, meta_model, name, code):
        return LLMModel.objects.create(
            meta_model=meta_model,
            provider=self.provider,
            name=name,
            code=code,
            currency="USD",
            input_price_per_million=Decimal("1"),
            output_price_per_million=Decimal("2"),
        )

    def test_capability_registers_question_catalog_and_tools(self):
        capability = get_assistant_capability()

        self.assertIsInstance(
            assistant_provider,
            AssistantCapabilityProvider,
        )
        self.assertEqual(capability.app_key, "llm_ops")
        self.assertEqual(capability.required_feature, "llm_ops")
        self.assertEqual(
            {tool.name for tool in capability.tools},
            {
                "llm_ops_get_overview",
                "llm_ops_query_decisions",
                "llm_ops_query_market_prices",
                "llm_ops_query_price_changes",
                "llm_ops_query_source_health",
                "llm_ops_get_operation_entry",
            },
        )
        profile = capability.profile_loader()
        questions = [
            question
            for group in profile["question_groups"]
            for question in group["questions"]
        ]
        self.assertEqual(len(questions), 8)
        self.assertEqual(profile["quick_question_limit"], 4)
        self.assertEqual(
            profile["ui_i18n"]["question_groups_key"],
            "llmOps.assistant.questionGroups",
        )
        self.assertIn("相对路径", capability.instructions)
        self.assertIn("本轮用户问题和回答", capability.instructions)
        self.assertIn("不得从预设问题目录", capability.instructions)

    def test_overview_separates_operational_and_reference_models(self):
        result = execute_llm_ops_tool("llm_ops_get_overview", {})

        self.assertTrue(result["ok"])
        overview = result["result"]
        self.assertEqual(overview["active_models"], 2)
        self.assertEqual(overview["operational_models"], 1)
        self.assertEqual(overview["market_reference_models"], 1)
        self.assertEqual(overview["decision_counts"]["no_supply"], 1)

    def test_decision_query_never_returns_market_reference_as_no_supply(self):
        result = execute_llm_ops_tool(
            "llm_ops_query_decisions",
            {"status": "no_supply"},
        )

        self.assertTrue(result["ok"])
        rows = result["result"]["rows"]
        self.assertEqual(
            [row["model_id"] for row in rows],
            [self.operational_model.id],
        )
        self.assertTrue(
            all(row["operation_scope"] == "operational" for row in rows)
        )

    def test_market_price_query_returns_source_and_price_dimensions(self):
        source = PriceCollectionSource.objects.create(
            name="Official OpenAI",
            slug="official-openai",
            provider=self.provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
        )
        ModelPriceItem.objects.create(
            provider=self.provider,
            model=self.reference_model,
            meta_model=self.reference_meta,
            source=source,
            price_role=LLMModel.PRICE_ROLE_MARKET_REFERENCE,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal("0.25"),
            price_fingerprint="reference-input",
        )

        result = execute_llm_ops_tool(
            "llm_ops_query_market_prices",
            {"query": "GPT Reference"},
        )

        self.assertTrue(result["ok"])
        row = result["result"]["rows"][0]
        self.assertEqual(row["source_name"], "Official OpenAI")
        self.assertEqual(row["dimension"], "text_input")
        self.assertEqual(row["unit_price"], "0.250000")

    def test_source_health_query_returns_latest_failed_run(self):
        source = PriceCollectionSource.objects.create(
            name="Broken Source",
            slug="broken-source",
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
        )
        PriceCollectionRun.objects.create(
            source=source,
            status=PriceCollectionRun.STATUS_FAILED,
            error_message="upstream timeout",
        )

        result = execute_llm_ops_tool(
            "llm_ops_query_source_health",
            {"status": "failed"},
        )

        self.assertTrue(result["ok"])
        row = result["result"]["rows"][0]
        self.assertEqual(row["source_id"], source.id)
        self.assertEqual(row["health_status"], "failed")
        self.assertEqual(row["latest_error"], "upstream timeout")

    def test_price_change_query_ranks_largest_change_first(self):
        now = timezone.now()
        for index, price in enumerate(("1", "3")):
            ChannelModelPriceHistory.objects.create(
                channel=self.channel,
                model=self.operational_model,
                meta_model=self.operational_meta,
                input_price_per_million=Decimal(price),
                output_price_per_million=Decimal(price),
                currency="USD",
                price_fingerprint=f"history-{index}",
                effective_from=now - timedelta(hours=2 - index),
                is_current=index == 1,
            )

        result = execute_llm_ops_tool(
            "llm_ops_query_price_changes",
            {"days": 7},
        )

        self.assertTrue(result["ok"])
        row = result["result"]["rows"][0]
        self.assertEqual(row["model_id"], self.operational_model.id)
        self.assertEqual(row["input_change_percent"], "200.00")

    def test_price_change_query_uses_baseline_before_requested_window(self):
        now = timezone.now()
        ChannelModelPriceHistory.objects.create(
            channel=self.channel,
            model=self.operational_model,
            meta_model=self.operational_meta,
            input_price_per_million=Decimal("1"),
            output_price_per_million=Decimal("2"),
            currency="USD",
            price_fingerprint="before-window",
            effective_from=now - timedelta(days=8),
            is_current=False,
        )
        ChannelModelPriceHistory.objects.create(
            channel=self.channel,
            model=self.operational_model,
            meta_model=self.operational_meta,
            input_price_per_million=Decimal("2"),
            output_price_per_million=Decimal("4"),
            currency="USD",
            price_fingerprint="inside-window",
            effective_from=now - timedelta(hours=1),
            is_current=True,
        )

        result = execute_llm_ops_tool(
            "llm_ops_query_price_changes",
            {"days": 7},
        )

        self.assertTrue(result["ok"])
        row = result["result"]["rows"][0]
        self.assertEqual(row["input_price_before"], "1.000000")
        self.assertEqual(row["input_price_after"], "2.000000")
        self.assertEqual(row["input_change_percent"], "100.00")

    def test_decision_query_bulk_loads_prices_for_channel_overrides(self):
        ChannelModelPrice.objects.filter(
            model=self.operational_model,
        ).update(is_listed=True)

        with CaptureQueriesContext(connection) as baseline_context:
            execute_llm_ops_tool(
                "llm_ops_query_decisions",
                {"status": "all"},
            )

        for index in range(4):
            meta_model = MetaModel.objects.create(
                name=f"Bulk Model {index}",
                code=f"bulk-model-{index}",
            )
            model = self._create_model(
                meta_model,
                f"Bulk Model {index}",
                f"bulk-model-{index}",
            )
            ChannelModelPrice.objects.create(
                channel=self.channel,
                model=model,
                meta_model=meta_model,
                is_listed=True,
            )

        with CaptureQueriesContext(connection) as expanded_context:
            execute_llm_ops_tool(
                "llm_ops_query_decisions",
                {"status": "all"},
            )

        self.assertLessEqual(
            len(expanded_context),
            len(baseline_context) + 1,
        )

    def test_operation_entry_returns_controlled_console_route(self):
        result = execute_llm_ops_tool(
            "llm_ops_get_operation_entry",
            {
                "action": "publish_listing",
                "model_id": self.operational_model.id,
            },
        )

        self.assertTrue(result["ok"])
        entry = result["result"]
        self.assertEqual(entry["section"], "reseller")
        self.assertEqual(
            entry["path"],
            (
                "/llm-ops?section=reseller&model_id="
                f"{self.operational_model.id}"
            ),
        )
        self.assertFalse(entry["executes_mutation"])

    def test_operation_entries_reach_supported_configuration_targets(self):
        platform_entry = execute_llm_ops_tool(
            "llm_ops_get_operation_entry",
            {
                "action": "configure_platform_fee",
                "platform_id": 17,
            },
        )["result"]
        exchange_entry = execute_llm_ops_tool(
            "llm_ops_get_operation_entry",
            {"action": "configure_exchange_rate"},
        )["result"]

        self.assertEqual(
            platform_entry["path"],
            (
                "/llm-ops?section=monitor&open_platform_config=1"
                "&platform_id=17"
            ),
        )
        self.assertEqual(
            exchange_entry["path"],
            "/cloud-billing/billing",
        )
        self.assertEqual(exchange_entry["label"], "查看汇率状态")
