"""Tests for LLM Ops catalog maintenance without seed bootstrap."""

from __future__ import annotations

from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from llm_ops.catalog_maintenance import (
    clean_legacy_llm_ops_demo_data,
    is_llm_ops_database_empty,
    normalize_meta_model_catalog,
    reset_meta_models_canonical,
    resolve_orphan_meta_models,
)
from llm_ops.collection_services import (
    reset_official_price_catalog,
    supported_official_provider_options,
)
from llm_ops.collectors.official import OFFICIAL_PROVIDER_CONFIGS
from llm_ops.management.commands.cleanup_llm_ops_seed_prices import (
    build_cleanup_plan,
    execute_cleanup,
)
from llm_ops.models import (
    ChannelModelPrice,
    LLMModel,
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    PriceCollectionRun,
    PriceCollectionSource,
    ProcurementChannel,
    ResaleListing,
    ResaleListingPriceHistory,
    ResalePlatform,
)
from llm_ops.periodic_tasks import register_periodic_tasks


class LLMOpsCatalogStateHelperTests(TestCase):
    """Validate helper functions that inspect catalogue state."""

    def test_is_llm_ops_database_empty_on_fresh_db(self):
        self.assertTrue(is_llm_ops_database_empty())

    def test_is_llm_ops_database_empty_false_when_provider_exists(self):
        LLMProvider.objects.create(name="OpenAI", code="openai")
        self.assertFalse(is_llm_ops_database_empty())

    def test_is_llm_ops_database_empty_ignores_operator_channels(self):
        ProcurementChannel.objects.create(
            name="Real Resource",
            code="real-resource-platform",
        )
        self.assertTrue(is_llm_ops_database_empty())

    def test_deleting_source_preserves_collection_run_audit(self):
        source = PriceCollectionSource.objects.create(
            name="OpenAI Official",
            slug="openai-official",
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
        )
        run = PriceCollectionRun.objects.create(source=source)

        source.delete()

        run.refresh_from_db()
        self.assertIsNone(run.source_id)


class LLMOpsCatalogMaintenanceTests(TestCase):
    """Catalog maintenance is separate from seed bootstrap."""

    def test_resolve_orphan_meta_models_uses_canonical_vendor_rules(self):
        MetaModel.objects.create(name="DeepSeek R1", code="deepseek-r1")

        stats = resolve_orphan_meta_models()

        meta = MetaModel.objects.get(code="deepseek-r1")
        self.assertEqual(stats["resolved"], 1)
        self.assertEqual(meta.vendor.code, "deepseek")

    def test_normalize_meta_model_catalog_merges_release_rows(self):
        provider = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        canonical = MetaModel.objects.create(
            name="DeepSeek R1",
            code="deepseek-r1",
            vendor=provider,
        )
        release = MetaModel.objects.create(
            name="DeepSeek R1 0528",
            code="deepseek-r1-0528",
            vendor=provider,
        )
        model = LLMModel.objects.create(
            provider=provider,
            meta_model=release,
            name="DeepSeek R1 0528",
            code="deepseek-r1-0528",
        )

        stats = normalize_meta_model_catalog()

        model.refresh_from_db()
        canonical.refresh_from_db()
        self.assertEqual(stats["merged"], 1)
        self.assertEqual(model.meta_model, canonical)
        self.assertFalse(
            MetaModel.objects.filter(code="deepseek-r1-0528").exists(),
        )

    def test_reset_meta_models_canonical_does_not_repopulate(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        meta = MetaModel.objects.create(
            name="GPT-4o mini",
            code="gpt-4o-mini",
            vendor=provider,
        )
        LLMModel.objects.create(
            provider=provider,
            meta_model=meta,
            name="GPT-4o mini",
            code="gpt-4o-mini",
        )

        stats = reset_meta_models_canonical()

        self.assertGreaterEqual(stats["meta_models_deleted"], 1)
        self.assertFalse(MetaModel.objects.exists())
        self.assertFalse(LLMModel.objects.exists())

    def test_meta_model_reset_dry_run_does_not_delete_orphans(self):
        meta = MetaModel.objects.create(
            name="Orphan GPT",
            code="gpt-orphan",
        )

        call_command(
            "reset_llm_ops_meta_models",
            "--dry-run",
            stdout=StringIO(),
        )

        self.assertTrue(MetaModel.objects.filter(id=meta.id).exists())
        self.assertFalse(LLMProvider.objects.filter(code="openai").exists())

    def test_clean_legacy_demo_data_removes_test_rows(self):
        PriceCollectionSource.objects.create(
            name="测试价格源",
            slug="test-source",
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
        )

        stats = clean_legacy_llm_ops_demo_data()

        self.assertEqual(stats["sources"], 1)
        self.assertFalse(PriceCollectionSource.objects.exists())

    def test_clean_legacy_demo_data_removes_channel_listings_first(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT Demo",
            code="gpt-demo",
        )
        channel = ProcurementChannel.objects.create(
            name="Demo Baseline",
            code="demo-baseline-supplier",
        )
        platform = ResalePlatform.objects.create(
            name="Demo Platform",
            code="demo-platform",
        )
        auto_listing = ResaleListing.objects.create(
            platform=platform,
            model=model,
            channel=None,
            retail_input_price_per_million=Decimal("1.000000"),
            retail_output_price_per_million=Decimal("2.000000"),
        )
        channel_listing = ResaleListing.objects.create(
            platform=platform,
            model=model,
            channel=channel,
            retail_input_price_per_million=Decimal("1.100000"),
            retail_output_price_per_million=Decimal("2.100000"),
        )
        auto_history = ResaleListingPriceHistory.objects.create(
            platform=platform,
            model=model,
            channel=None,
            retail_input_price_per_million=Decimal("1.000000"),
            retail_output_price_per_million=Decimal("2.000000"),
            price_fingerprint="same-price",
            effective_from="2026-01-01T00:00:00Z",
        )
        channel_history = ResaleListingPriceHistory.objects.create(
            platform=platform,
            model=model,
            channel=channel,
            retail_input_price_per_million=Decimal("1.000000"),
            retail_output_price_per_million=Decimal("2.000000"),
            price_fingerprint="same-price",
            effective_from="2026-01-01T00:00:00Z",
        )

        stats = clean_legacy_llm_ops_demo_data()

        self.assertEqual(stats["resale_listings"], 1)
        self.assertEqual(stats["resale_listing_histories"], 1)
        self.assertFalse(
            ProcurementChannel.objects.filter(id=channel.id).exists()
        )
        self.assertTrue(
            ResaleListing.objects.filter(id=auto_listing.id).exists()
        )
        self.assertFalse(
            ResaleListing.objects.filter(id=channel_listing.id).exists()
        )
        self.assertTrue(
            ResaleListingPriceHistory.objects.filter(
                id=auto_history.id
            ).exists()
        )
        self.assertFalse(
            ResaleListingPriceHistory.objects.filter(
                id=channel_history.id
            ).exists()
        )


class LLMOpsOfficialProviderOptionTests(TestCase):
    """Official source options are dynamic presets, not seed data."""

    def test_supported_official_provider_options_do_not_create_rows(self):
        options = supported_official_provider_options()

        provider_codes = {option["provider_code"] for option in options}
        self.assertIn("aliyun", provider_codes)
        self.assertIn("baidu", provider_codes)
        self.assertFalse(LLMProvider.objects.exists())
        self.assertFalse(PriceCollectionSource.objects.exists())


class LLMOpsOfficialPriceResetCommandTests(TestCase):
    """Official reset command keeps reset and sync scopes aligned."""

    def test_reset_preserves_provider_source_for_resync(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        meta = MetaModel.objects.create(
            name="GPT-4o mini",
            code="gpt-4o-mini",
            vendor=provider,
        )
        source = PriceCollectionSource.objects.create(
            name="OpenAI 官方价格",
            slug="openai-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://openai.com/api/pricing/",
            updates_model_prices=True,
        )
        model = LLMModel.objects.create(
            provider=provider,
            meta_model=meta,
            source=source,
            name="GPT-4o mini",
            code="gpt-4o-mini",
            price_role=LLMModel.PRICE_ROLE_OFFICIAL,
            input_price_per_million=Decimal("0.150000"),
            output_price_per_million=Decimal("0.600000"),
            source_url=source.endpoint_url,
        )
        ModelPriceItem.objects.create(
            provider=provider,
            model=model,
            meta_model=meta,
            source=source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal("0.150000"),
            price_fingerprint="official-price-fingerprint",
            is_current=True,
        )

        stats = reset_official_price_catalog(provider_codes=["openai"])

        model.refresh_from_db()
        self.assertEqual(stats["models_reset"], 1)
        self.assertEqual(model.source_id, source.id)
        self.assertEqual(model.price_role, LLMModel.PRICE_ROLE_OFFICIAL)
        self.assertEqual(model.input_price_per_million, Decimal("0"))
        self.assertEqual(model.output_price_per_million, Decimal("0"))
        self.assertFalse(ModelPriceItem.objects.filter(source=source).exists())

    def test_reset_migrates_legacy_source_model_to_provider_source(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        meta = MetaModel.objects.create(
            name="GPT-4o mini",
            code="gpt-4o-mini",
            vendor=provider,
        )
        provider_source = PriceCollectionSource.objects.create(
            name="OpenAI 官方价格",
            slug="openai-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://openai.com/api/pricing/",
            updates_model_prices=True,
        )
        legacy_source = PriceCollectionSource.objects.create(
            name="OpenAI / GPT-4o mini 官方价格",
            slug="openai-gpt-4o-mini-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            updates_model_prices=True,
        )
        model = LLMModel.objects.create(
            provider=provider,
            meta_model=meta,
            source=legacy_source,
            name="GPT-4o mini",
            code="gpt-4o-mini",
            price_role=LLMModel.PRICE_ROLE_OFFICIAL,
            input_price_per_million=Decimal("0.150000"),
            output_price_per_million=Decimal("0.600000"),
        )

        reset_official_price_catalog(provider_codes=["openai"])

        model.refresh_from_db()
        self.assertEqual(model.source_id, provider_source.id)
        self.assertEqual(model.input_price_per_million, Decimal("0"))
        self.assertFalse(
            PriceCollectionSource.objects.filter(id=legacy_source.id).exists()
        )

    def test_reset_deduplicates_legacy_model_before_source_migration(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        meta = MetaModel.objects.create(
            name="GPT-4.1 mini",
            code="gpt-4.1-mini",
            vendor=provider,
        )
        provider_source = PriceCollectionSource.objects.create(
            name="OpenAI 官方价格",
            slug="openai-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://openai.com/api/pricing/",
            updates_model_prices=True,
        )
        legacy_source = PriceCollectionSource.objects.create(
            name="OpenAI / GPT-4.1 mini 官方价格",
            slug="openai-gpt-4-1-mini-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            updates_model_prices=True,
        )
        provider_model = LLMModel.objects.create(
            provider=provider,
            meta_model=meta,
            source=provider_source,
            name="GPT-4.1 mini",
            code="gpt-4.1-mini",
            price_role=LLMModel.PRICE_ROLE_OFFICIAL,
            input_price_per_million=Decimal("0.400000"),
            output_price_per_million=Decimal("1.600000"),
        )
        legacy_model = LLMModel.objects.create(
            provider=provider,
            meta_model=meta,
            source=legacy_source,
            name="GPT-4.1 mini",
            code="gpt-4.1-mini",
            price_role=LLMModel.PRICE_ROLE_OFFICIAL,
            input_price_per_million=Decimal("0.400000"),
            output_price_per_million=Decimal("1.600000"),
        )

        stats = reset_official_price_catalog(provider_codes=["openai"])

        provider_model.refresh_from_db()
        legacy_model.refresh_from_db()
        self.assertEqual(stats["models_reset"], 2)
        self.assertEqual(stats["legacy_models_deduplicated"], 1)
        self.assertIsNone(legacy_model.source_id)
        self.assertEqual(legacy_model.price_role, LLMModel.PRICE_ROLE_UNKNOWN)
        self.assertEqual(
            LLMModel.objects.filter(
                provider=provider,
                source=provider_source,
                code="gpt-4.1-mini",
            ).count(),
            1,
        )
        self.assertEqual(provider_model.input_price_per_million, Decimal("0"))
        self.assertFalse(
            PriceCollectionSource.objects.filter(id=legacy_source.id).exists()
        )

    def test_reset_keeps_non_legacy_official_source_for_same_provider(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        meta = MetaModel.objects.create(
            name="GPT-4o mini",
            code="gpt-4o-mini",
            vendor=provider,
        )
        source = PriceCollectionSource.objects.create(
            name="OpenAI enterprise official",
            slug="openai-enterprise-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://example.com/openai-enterprise",
            updates_model_prices=True,
        )
        model = LLMModel.objects.create(
            provider=provider,
            meta_model=meta,
            source=source,
            name="GPT-4o mini",
            code="gpt-4o-mini",
            price_role=LLMModel.PRICE_ROLE_OFFICIAL,
            input_price_per_million=Decimal("0.150000"),
            output_price_per_million=Decimal("0.600000"),
        )
        item = ModelPriceItem.objects.create(
            provider=provider,
            model=model,
            meta_model=meta,
            source=source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal("0.150000"),
            price_fingerprint="operator-source-price-fingerprint",
            is_current=True,
        )

        stats = reset_official_price_catalog(provider_codes=["openai"])

        model.refresh_from_db()
        self.assertEqual(stats["sources_matched"], 0)
        self.assertTrue(
            PriceCollectionSource.objects.filter(id=source.id).exists()
        )
        self.assertEqual(model.source_id, source.id)
        self.assertEqual(model.input_price_per_million, Decimal("0.150000"))
        self.assertTrue(ModelPriceItem.objects.filter(id=item.id).exists())

    @patch(
        "llm_ops.management.commands.reset_llm_ops_official_prices."
        "sync_configured_official_model_prices"
    )
    @patch(
        "llm_ops.management.commands.reset_llm_ops_official_prices."
        "reset_official_price_catalog"
    )
    def test_all_sync_passes_explicit_provider_codes(
        self,
        mock_reset,
        mock_sync,
    ):
        mock_reset.return_value = {
            "sources_matched": 0,
            "provider_sources_kept": 0,
            "legacy_sources_deleted": 0,
            "legacy_models_deduplicated": 0,
            "models_reset": 0,
            "price_items_deleted": 0,
            "snapshots_deleted": 0,
            "history_deleted": 0,
            "runs_deleted": 0,
            "legacy_source_slugs": [],
        }
        mock_sync.return_value = {}
        provider_codes = sorted(OFFICIAL_PROVIDER_CONFIGS)

        call_command(
            "reset_llm_ops_official_prices",
            "--all",
            "--sync",
            "--yes",
            stdout=StringIO(),
        )

        mock_reset.assert_called_once_with(
            provider_codes=provider_codes,
            dry_run=False,
        )
        mock_sync.assert_called_once_with(
            provider_codes=provider_codes,
            verify_source=True,
        )


class LLMOpsSeedCleanupCommandTests(TestCase):
    """Seed cleanup must not delete operator-created sources."""

    def test_cleanup_only_removes_legacy_sources(self):
        provider = LLMProvider.objects.create(name="百度", code="baidu")
        meta = MetaModel.objects.create(
            name="ERNIE 4.0",
            code="ernie-4.0",
            vendor=provider,
        )
        provider_source = PriceCollectionSource.objects.create(
            name="百度 官方价格",
            slug="baidu-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            updates_model_prices=True,
        )
        manual_source = PriceCollectionSource.objects.create(
            name="百度 人工价格",
            slug="baidu-manual",
            provider=provider,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_MANUAL,
        )
        supplier_source = PriceCollectionSource.objects.create(
            name="百度 供货商价格",
            slug="baidu-supplier",
            provider=provider,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
        )
        legacy_source = PriceCollectionSource.objects.create(
            name="百度 / ERNIE 4.0 官方价格",
            slug="baidu-ernie-4-0-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            updates_model_prices=True,
        )
        LLMModel.objects.create(
            provider=provider,
            meta_model=meta,
            source=legacy_source,
            name="ERNIE 4.0",
            code="ernie-4.0",
        )

        plan = build_cleanup_plan(("baidu",))

        self.assertEqual(plan["provider_ids"], [])
        self.assertEqual(plan["source_ids"], [legacy_source.id])

        execute_cleanup(plan)

        self.assertTrue(LLMProvider.objects.filter(id=provider.id).exists())
        self.assertTrue(
            PriceCollectionSource.objects.filter(
                id=provider_source.id,
            ).exists()
        )
        self.assertTrue(
            PriceCollectionSource.objects.filter(id=manual_source.id).exists()
        )
        self.assertTrue(
            PriceCollectionSource.objects.filter(
                id=supplier_source.id,
            ).exists()
        )
        self.assertFalse(
            PriceCollectionSource.objects.filter(id=legacy_source.id).exists()
        )
        self.assertFalse(LLMModel.objects.filter(code="ernie-4.0").exists())

    def test_cleanup_detaches_legacy_model_with_business_links(self):
        provider = LLMProvider.objects.create(name="百度", code="baidu")
        meta = MetaModel.objects.create(
            name="ERNIE 4.0",
            code="ernie-4.0",
            vendor=provider,
        )
        channel = ProcurementChannel.objects.create(
            name="Real Channel",
            code="real-channel",
        )
        legacy_source = PriceCollectionSource.objects.create(
            name="百度 / ERNIE 4.0 官方价格",
            slug="baidu-ernie-4-0-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            updates_model_prices=True,
        )
        model = LLMModel.objects.create(
            provider=provider,
            meta_model=meta,
            source=legacy_source,
            name="ERNIE 4.0",
            code="ernie-4.0",
            price_role=LLMModel.PRICE_ROLE_OFFICIAL,
            input_price_per_million=Decimal("1.000000"),
            output_price_per_million=Decimal("2.000000"),
        )
        channel_price = ChannelModelPrice.objects.create(
            channel=channel,
            model=model,
            meta_model=meta,
            currency="CNY",
        )

        plan = build_cleanup_plan(("baidu",))
        stats = execute_cleanup(plan)

        model.refresh_from_db()
        self.assertEqual(stats["models_detached"], 1)
        self.assertIsNone(model.source_id)
        self.assertEqual(model.price_role, LLMModel.PRICE_ROLE_UNKNOWN)
        self.assertEqual(model.input_price_per_million, Decimal("0"))
        self.assertTrue(
            ChannelModelPrice.objects.filter(id=channel_price.id).exists()
        )
        self.assertFalse(
            PriceCollectionSource.objects.filter(id=legacy_source.id).exists()
        )


class LLMOpsPeriodicTasksTests(TestCase):
    """The Celery task and periodic entry are wired up correctly."""

    def test_register_periodic_tasks_registers_llm_ops_entries(self):
        from core.periodic_registry import TASK_REGISTRY

        TASK_REGISTRY.clear()
        register_periodic_tasks()
        names = list(TASK_REGISTRY._entries.keys())
        self.assertEqual(
            names,
            [
                "llm_ops_model_price_sync_agent",
                "llm_ops_meta_models_dev_sync",
            ],
        )
        price_entry = TASK_REGISTRY._entries["llm_ops_model_price_sync_agent"]
        self.assertEqual(
            price_entry["task"],
            "llm_ops.tasks.run_model_price_sync_agent",
        )
        self.assertEqual(
            price_entry["kwargs"],
            {"source_ids": None, "verify_source": True},
        )

        meta_entry = TASK_REGISTRY._entries["llm_ops_meta_models_dev_sync"]
        self.assertEqual(
            meta_entry["task"],
            "llm_ops.tasks.sync_meta_models_from_models_dev",
        )
