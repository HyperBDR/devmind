import json

from django.test import TestCase

from llm_ops.global_config import sync_global_config_to_beat
from llm_ops.models import (
    LLMOpsGlobalConfig,
    LLMProvider,
    PriceCollectionSource,
)


class LLMOpsGlobalConfigBeatSyncTests(TestCase):
    """Global config beat sync must not leave empty enabled tasks."""

    def test_stale_price_source_selection_disables_price_sync_task(self):
        from django_celery_beat.models import PeriodicTask

        provider = LLMProvider.objects.create(
            name="Legacy Vendor",
            code="legacy-vendor",
        )
        source = PriceCollectionSource.objects.create(
            name="Legacy Official",
            slug="legacy-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://legacy.example.com/pricing/",
            updates_model_prices=True,
        )
        config = LLMOpsGlobalConfig.get_solo()
        config.price_collection_enabled = True
        config.price_collection_source_ids = [source.id]
        config.save()

        with self.assertLogs("llm_ops.global_config", level="WARNING"):
            sync_global_config_to_beat(config)

        price_task = PeriodicTask.objects.get(
            name="llm_ops_model_price_sync_agent"
        )
        kwargs = json.loads(price_task.kwargs)
        self.assertEqual(kwargs["source_ids"], [])
        self.assertFalse(price_task.enabled)

    def test_default_all_sources_keeps_null_task_source_ids_enabled(self):
        from django_celery_beat.models import PeriodicTask

        config = LLMOpsGlobalConfig.get_solo()
        config.price_collection_enabled = True
        config.price_collection_source_ids = []
        config.save()

        sync_global_config_to_beat(config)

        price_task = PeriodicTask.objects.get(
            name="llm_ops_model_price_sync_agent"
        )
        kwargs = json.loads(price_task.kwargs)
        self.assertIsNone(kwargs["source_ids"])
        self.assertTrue(price_task.enabled)
