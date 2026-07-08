import sys
from types import ModuleType
from unittest import mock

from django.test import SimpleTestCase

from llm_ops.llm_config import PRICE_SYNC_LLM_NOT_CONFIGURED_MESSAGE
from llm_ops.tasks import run_model_price_sync_agent


class RunModelPriceSyncAgentTaskTests(SimpleTestCase):
    """Celery task retry policy for model price sync."""

    def test_missing_llm_config_fails_without_retry(self):
        agents_module = ModuleType("llm_ops.agents")
        model_price_sync_module = ModuleType(
            "llm_ops.agents.model_price_sync"
        )

        def execute_model_price_sync_agent(**kwargs):
            raise ValueError(PRICE_SYNC_LLM_NOT_CONFIGURED_MESSAGE)

        model_price_sync_module.execute_model_price_sync_agent = (
            execute_model_price_sync_agent
        )

        modules = {
            "llm_ops.agents": agents_module,
            "llm_ops.agents.model_price_sync": model_price_sync_module,
        }
        with (
            mock.patch.dict(sys.modules, modules),
            mock.patch.object(run_model_price_sync_agent, "retry") as retry,
            self.assertLogs("llm_ops.tasks", level="ERROR") as logs,
        ):
            with self.assertRaisesRegex(
                ValueError,
                PRICE_SYNC_LLM_NOT_CONFIGURED_MESSAGE,
            ):
                run_model_price_sync_agent.run()

        retry.assert_not_called()
        self.assertIn("configuration error", "\n".join(logs.output))
