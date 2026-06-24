"""Tests for the llm_ops deployment bootstrap and periodic tasks.

These tests cover the deployment guarantees that the pipeline
relies on:

1. ``seed_initial_price_sheet_if_empty`` runs the import on a fresh
   database, but is a no-op when canonical rows already exist.
2. ``seed_initial_price_sheet_safely`` never overwrites manually
   maintained overrides (``ChannelModelPrice.custom_*``,
   ``LLMModel.is_active``, ``PriceCollectionSource.is_enabled``).
3. ``register_periodic_tasks`` exposes a single
   ``llm_ops_official_collect`` entry, and the corresponding Celery
   task is registered with the worker.
"""
from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.test import TestCase

from llm_ops.models import (
    ChannelModelPrice,
    ChannelModelPriceHistory,
    ChannelPriceItem,
    LLMModel,
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    PriceCollectionSource,
    ProcurementChannel,
)
from llm_ops.periodic_tasks import register_periodic_tasks
from llm_ops.seed_data import (
    REAL_RESOURCE_CHANNEL_CODE,
    clean_mock_llm_ops_seed_data,
    is_llm_ops_database_empty,
    seed_initial_price_sheet,
    seed_agione_price_trend_demo,
    seed_initial_price_sheet_if_empty,
    seed_initial_price_sheet_safely,
    cleanup_orphan_meta_models,
    normalize_meta_model_catalog,
    reset_meta_models_canonical,
    resolve_orphan_meta_models,
    seed_yunce_supplier_price_demo,
)
from llm_ops.views import LLMProviderViewSet, MetaModelViewSet


class LLMOpsBootstrapGuardsTests(TestCase):
    """Validate the helper functions that gate auto-bootstrap."""

    def test_is_llm_ops_database_empty_on_fresh_db(self):
        self.assertTrue(is_llm_ops_database_empty())

    def test_is_llm_ops_database_empty_false_when_provider_exists(self):
        LLMProvider.objects.create(name="OpenAI", code="openai")
        # Even without the channel row, the function still treats
        # any provider presence as "populated".
        self.assertFalse(is_llm_ops_database_empty())

    def test_is_llm_ops_database_empty_ignores_operator_channels(self):
        ProcurementChannel.objects.create(
            name="Real Resource",
            code=REAL_RESOURCE_CHANNEL_CODE,
        )
        self.assertTrue(is_llm_ops_database_empty())


class LLMOpsSeedSafelyTests(TestCase):
    """``seed_initial_price_sheet_safely`` must preserve human edits."""

    def setUp(self):
        # Run the safe seed once so the schema has canonical rows.
        stats = seed_initial_price_sheet_safely()
        self.assertGreater(stats["providers"], 0)
        self.assertGreater(stats["models"], 0)
        self.assertGreater(stats["model_price_items"], 0)

    def test_safe_seed_does_not_re_enable_disabled_source(self):
        source = PriceCollectionSource.objects.filter(
            slug__endswith="-sheet",
        ).first()
        source.is_enabled = False
        source.save()

        seed_initial_price_sheet_safely()

        source.refresh_from_db()
        self.assertFalse(source.is_enabled)

    def test_safe_seed_does_not_reactivate_deactivated_model(self):
        model = LLMModel.objects.filter(is_active=True).first()
        model.is_active = False
        model.save()

        seed_initial_price_sheet_safely()

        model.refresh_from_db()
        self.assertFalse(model.is_active)

    def test_safe_seed_is_idempotent(self):
        first_providers = LLMProvider.objects.count()
        first_models = LLMModel.objects.count()
        first_sources = PriceCollectionSource.objects.count()
        first_items = ModelPriceItem.objects.count()

        stats = seed_initial_price_sheet_safely()

        self.assertEqual(stats["providers"], 0)
        self.assertEqual(stats["models"], 0)
        self.assertEqual(stats["model_price_items"], 0)
        self.assertEqual(stats["channel_model_prices"], 0)
        self.assertEqual(LLMProvider.objects.count(), first_providers)
        self.assertEqual(LLMModel.objects.count(), first_models)
        self.assertEqual(
            PriceCollectionSource.objects.count(), first_sources
        )
        self.assertEqual(ModelPriceItem.objects.count(), first_items)

    def test_safe_seed_creates_source_price_items(self):
        sheet_items = ModelPriceItem.objects.filter(
            spec__seed_source="initial_price_sheet",
            is_current=True,
        )
        self.assertTrue(sheet_items.exists())
        self.assertTrue(
            sheet_items.filter(
                source__slug="siliconflow-sheet",
                model__code="deepseek-r1",
                dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            ).exists()
        )
        self.assertTrue(
            sheet_items.filter(
                source__slug="siliconflow-sheet",
                model__code="deepseek-r1",
                dimension=ModelPriceItem.DIMENSION_TEXT_OUTPUT,
            ).exists()
        )


class LLMOpsSeedLegacyTests(TestCase):
    """``seed_initial_price_sheet`` keeps its overwrite semantics.

    The explicit ``manage.py seed_llm_ops_price_sheet`` command still
    re-applies the canonical defaults so operators can re-import after
    editing the price sheet source. This test pins the behaviour and
    documents that it is intentional and distinct from the safe path.
    """

    def test_legacy_seed_overwrites_seed_managed_source_fields(self):
        """Legacy seed re-applies its own source defaults.

        The two seed paths differ in this respect: the safe seed
        leaves seed-managed fields alone on already-existing rows,
        while the legacy seed (used by the management command) is
        the canonical "re-import the price sheet" operation. This
        test pins that difference so a future refactor cannot
        silently make the two paths equivalent.
        """
        seed_initial_price_sheet_safely()
        source = PriceCollectionSource.objects.get(slug="aliyun-sheet")
        source.name = "人工改名价格源"
        source.currency = "USD"
        source.save()

        seed_initial_price_sheet()

        source.refresh_from_db()
        self.assertNotEqual(source.name, "人工改名价格源")
        self.assertEqual(source.currency, "CNY")
        self.assertIsNone(source.channel_id)


class LLMOpsSeedIfEmptyTests(TestCase):
    """``seed_initial_price_sheet_if_empty`` gates explicit bootstrap."""

    def test_runs_seed_on_empty_database(self):
        result = seed_initial_price_sheet_if_empty()
        self.assertIsNotNone(result)
        self.assertGreater(result["providers"], 0)
        self.assertTrue(
            LLMProvider.objects.filter(code="openai").exists()
        )

    def test_returns_none_when_database_is_populated(self):
        LLMProvider.objects.create(name="OpenAI", code="openai")
        result = seed_initial_price_sheet_if_empty()
        self.assertIsNone(result)
        # The provider we just created must not be touched.
        self.assertEqual(LLMProvider.objects.filter(code="openai").count(), 1)


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
                "llm_ops_official_collect",
                "llm_ops_meta_models_dev_sync",
            ],
        )
        entry = TASK_REGISTRY._entries["llm_ops_official_collect"]
        self.assertEqual(
            entry["task"], "llm_ops.tasks.collect_official_model_prices"
        )
        self.assertTrue(entry["enabled"])
        self.assertEqual(
            entry["kwargs"],
            {"provider_codes": None, "verify_source": True},
        )
        meta_entry = TASK_REGISTRY._entries["llm_ops_meta_models_dev_sync"]
        self.assertEqual(
            meta_entry["task"],
            "llm_ops.tasks.sync_meta_models_from_models_dev",
        )

    def test_register_periodic_tasks_is_idempotent_at_register_call(self):
        """Two calls to register_periodic_tasks do not duplicate.

        The management command always clears the global registry before
        re-invoking every app's ``register_periodic_tasks``, so the
        in-memory behaviour here is "latest call wins". This test pins
        that contract so a future refactor cannot accidentally start
        appending duplicate ``PeriodicTask`` rows.
        """
        from core.periodic_registry import TASK_REGISTRY

        TASK_REGISTRY.clear()
        register_periodic_tasks()
        register_periodic_tasks()
        self.assertEqual(
            len(TASK_REGISTRY._entries), 2
        )

    def test_collect_official_model_prices_task_is_registered(self):
        from core.celery import _lazy_autodiscover, app

        _lazy_autodiscover()
        task = app.tasks.get("llm_ops.tasks.collect_official_model_prices")
        self.assertIsNotNone(task)
        expected_name = "llm_ops.tasks.collect_official_model_prices"
        self.assertEqual(task.name, expected_name)
        self.assertTrue(task.acks_late)

    def test_collect_official_model_prices_delegates_to_service(self):
        from llm_ops.tasks import collect_official_model_prices

        with mock.patch(
            "llm_ops.collection_services.sync_configured_official_model_prices"
        ) as mock_sync:
            mock_sync.return_value = {"openai": {"models": 0}}
            result = collect_official_model_prices(
                provider_codes=["openai"],
                verify_source=False,
            )
        mock_sync.assert_called_once_with(
            provider_codes=["openai"],
            verify_source=False,
        )
        self.assertEqual(result, {"openai": {"models": 0}})

    def test_collect_price_source_prices_delegates_to_code_sync(self):
        from llm_ops.tasks import collect_price_source_prices

        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        source = PriceCollectionSource.objects.create(
            name="OpenAI Official",
            slug="openai-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://openai.com/api/pricing/",
            is_enabled=True,
            updates_model_prices=True,
        )

        patch_path = "llm_ops.source_collectors.collect_price_source"
        with mock.patch(patch_path) as mock_collect:
            mock_collect.return_value = {"models": 1}
            result = collect_price_source_prices(
                source_id=source.id,
                verify_source=False,
            )

        mock_collect.assert_called_once_with(
            source,
            verify_source=False,
        )
        self.assertEqual(result, {"models": 1})

    def test_sync_meta_models_from_models_dev_task_delegates_to_service(self):
        from llm_ops.tasks import sync_meta_models_from_models_dev_task

        with mock.patch(
            "llm_ops.collection_services.sync_meta_models_from_models_dev"
        ) as mock_sync:
            mock_sync.return_value = {"models": 1}
            result = sync_meta_models_from_models_dev_task()
        mock_sync.assert_called_once_with()
        self.assertEqual(result, {"models": 1})


class LLMOpsPeriodicApplyTests(TestCase):
    """``apply_registry`` must not overwrite existing PeriodicTask rows.

    Operators routinely tweak schedules from the django_celery_beat
    admin. The contract of the core registry is "do not touch rows
    that already exist"; this test asserts it end-to-end via the
    global ``TASK_REGISTRY.apply``.
    """

    def test_apply_does_not_overwrite_existing_periodic_task(self):
        from django_celery_beat.models import PeriodicTask

        from core.management.commands.register_periodic_tasks import (
            discover_and_register,
        )
        from core.periodic_registry import TASK_REGISTRY

        # First registration: creates the row.
        discover_and_register()
        self.assertTrue(
            PeriodicTask.objects.filter(
                name="llm_ops_official_collect"
            ).exists()
        )
        original = PeriodicTask.objects.get(
            name="llm_ops_official_collect"
        )
        original.enabled = False
        original.save()

        # Second registration: must NOT clobber the operator's
        # ``enabled`` flag.
        discover_and_register()
        original.refresh_from_db()
        self.assertFalse(
            original.enabled,
            "PeriodicTask.enabled must be preserved across re-registrations",
        )
        # Also confirm the registry was cleared and re-populated.
        self.assertIn("llm_ops_official_collect", TASK_REGISTRY._entries)


class LLMOpsMockSeedCleanupTests(TestCase):
    """Default seed must not publish legacy mock/demo supplier rows."""

    def test_default_seed_does_not_create_mock_supplier_data(self):
        stats = seed_initial_price_sheet_safely()

        self.assertGreater(stats["providers"], 0)
        self.assertFalse(
            ProcurementChannel.objects.filter(
                code="yunce-supplier-platform",
            ).exists()
        )
        self.assertFalse(
            ProcurementChannel.objects.filter(
                code=REAL_RESOURCE_CHANNEL_CODE,
            ).exists()
        )
        self.assertFalse(ChannelModelPrice.objects.exists())
        self.assertFalse(
            ProcurementChannel.objects.filter(
                code="demo-premium-supplier",
            ).exists()
        )
        self.assertFalse(
            PriceCollectionSource.objects.filter(
                slug__startswith="yunce-",
            ).exists()
        )
        self.assertFalse(
            PriceCollectionSource.objects.filter(
                slug__endswith="-trend-demo",
            ).exists()
        )

    def test_meta_model_vendor_is_the_company_that_built_it(self):
        """deepseek-r1 must be owned by DeepSeek, not aliyun.

        The price sheet groups DeepSeek under aliyun, but the
        canonical model vendor must follow the company that
        actually built the model. This test pins the rule.
        """
        seed_initial_price_sheet_safely()
        aliyun = LLMProvider.objects.get(code="aliyun")
        deepseek = LLMProvider.objects.get(code="deepseek")
        deepseek_r1 = MetaModel.objects.get(code="deepseek-r1")
        deepseek_v3 = MetaModel.objects.get(code="deepseek-v3")
        qwen_plus = MetaModel.objects.get(code="qwen-plus")
        self.assertEqual(deepseek_r1.vendor, deepseek)
        self.assertIn("deepseek-r1-0528", deepseek_r1.aliases)
        self.assertFalse(
            MetaModel.objects.filter(code="deepseek-r1-0528").exists(),
        )
        self.assertEqual(deepseek_v3.vendor, deepseek)
        self.assertEqual(qwen_plus.vendor, aliyun)

    def test_meta_model_vendor_rehomes_legacy_supplier_assignment(
        self,
    ):
        """A historical supplier vendor assignment is corrected."""
        siliconflow = LLMProvider.objects.create(
            name="\u7845\u57fa\u6d41\u52a8",
            code="siliconflow",
        )
        MetaModel.objects.create(
            name="DeepSeek R1",
            code="deepseek-r1",
            vendor=siliconflow,
        )
        seed_initial_price_sheet_safely()
        deepseek = LLMProvider.objects.get(code="deepseek")
        deepseek_r1 = MetaModel.objects.get(code="deepseek-r1")
        self.assertEqual(deepseek_r1.vendor, deepseek)

    def test_normalize_meta_model_catalog_merges_dated_releases(self):
        """Date/build suffixes belong in aliases, not MetaModel.code."""
        deepseek = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        canonical = MetaModel.objects.create(
            name="DeepSeek R1",
            code="deepseek-r1",
            vendor=deepseek,
            context_window=64000,
        )
        dated = MetaModel.objects.create(
            name="DeepSeek R1 0528",
            code="deepseek-r1-0528",
            vendor=deepseek,
            context_window=128000,
        )
        model = LLMModel.objects.create(
            provider=deepseek,
            meta_model=dated,
            name="DeepSeek R1 0528",
            code="deepseek-r1-0528",
        )

        stats = normalize_meta_model_catalog()

        self.assertEqual(stats["merged"], 1)
        self.assertFalse(
            MetaModel.objects.filter(code="deepseek-r1-0528").exists(),
        )
        canonical.refresh_from_db()
        model.refresh_from_db()
        self.assertEqual(model.meta_model, canonical)
        self.assertEqual(canonical.context_window, 128000)
        self.assertIn("deepseek-r1-0528", canonical.aliases)
        self.assertIn("DeepSeek R1 0528", canonical.aliases)

    def test_normalize_meta_model_catalog_relinks_price_source_rows(self):
        """Existing price-source rows follow their model's meta model."""
        deepseek = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        aliyun = LLMProvider.objects.create(
            name="阿里云",
            code="aliyun",
        )
        canonical = MetaModel.objects.create(
            name="DeepSeek R1",
            code="deepseek-r1",
            vendor=deepseek,
        )
        wrong_meta = MetaModel.objects.create(
            name="阿里云 DeepSeek R1",
            code="aliyun-deepseek-r1",
            vendor=aliyun,
        )
        model = LLMModel.objects.create(
            provider=deepseek,
            meta_model=canonical,
            name="DeepSeek R1 0528",
            code="deepseek-r1-0528",
        )
        item = ModelPriceItem.objects.create(
            provider=deepseek,
            model=model,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal("0.550000"),
            price_fingerprint="legacy-wrong-meta",
        )
        ModelPriceItem.objects.filter(id=item.id).update(meta_model=wrong_meta)

        stats = normalize_meta_model_catalog()

        item.refresh_from_db()
        self.assertEqual(stats["linked_records"], 1)
        self.assertEqual(item.meta_model, canonical)

    def test_resolve_orphan_meta_models_backfills_vendor(self):
        """MetaModel rows without a vendor are auto-rehomed."""
        from llm_ops.seed_data import resolve_orphan_meta_models
        seed_initial_price_sheet_safely()
        aliyun = LLMProvider.objects.get(code="aliyun")
        orphan = MetaModel.objects.create(
            name="Qwen X",
            code="qwen-x",
            vendor=None,
        )
        self.assertIsNone(orphan.vendor_id)
        stats = resolve_orphan_meta_models()
        orphan.refresh_from_db()
        self.assertEqual(orphan.vendor, aliyun)
        self.assertGreaterEqual(stats["resolved"], 1)

    def test_resolve_orphan_meta_models_skips_unknown_codes(self):
        """Unknown codes are surfaced as warnings, not silently dropped."""
        from llm_ops.seed_data import resolve_orphan_meta_models
        seed_initial_price_sheet_safely()
        MetaModel.objects.create(
            name="Mystery Model",
            code="mystery-2026",
            vendor=None,
        )
        stats = resolve_orphan_meta_models()
        self.assertEqual(stats["resolved"], 0)
        self.assertGreaterEqual(stats["unresolved"], 1)

    def test_cleanup_orphan_meta_models_drops_unused_rows(self):
        """Orphan meta models without provider_prices are removed."""
        seed_initial_price_sheet_safely()
        deepseek = LLMProvider.objects.get(code="deepseek")
        MetaModel.objects.create(
            name="Orphan Demo",
            code="orphan-demo",
            vendor=deepseek,
        )
        stats = cleanup_orphan_meta_models()
        self.assertFalse(
            MetaModel.objects.filter(code="orphan-demo").exists(),
        )
        self.assertGreaterEqual(stats["meta_models_deleted"], 1)

    def test_reset_meta_models_canonical_rebuilds_from_sheet(self):
        """Full reset removes every meta model and supplier alias."""
        seed_initial_price_sheet_safely()
        LLMProvider.objects.create(
            name="硅基流动",
            code="siliconflow",
        )
        before_count = MetaModel.objects.count()
        self.assertGreater(before_count, 0)
        reset_stats = reset_meta_models_canonical()
        self.assertEqual(MetaModel.objects.count(), 0)
        self.assertFalse(
            LLMProvider.objects.filter(code="siliconflow").exists(),
        )
        self.assertGreaterEqual(
            reset_stats["meta_models_deleted"], before_count
        )
        seed_stats = seed_initial_price_sheet_safely()
        # Every deepseek model code in the price sheet must end up
        # owned by the deepseek vendor.
        deepseek_codes = [
            "deepseek-r1",
            "deepseek-v3",
            "deepseek-v3.1",
            "deepseek-v3.2",
            "deepseek-v3.2-exp",
        ]
        for code in deepseek_codes:
            meta = MetaModel.objects.get(code=code)
            self.assertEqual(meta.vendor.code, "deepseek")
        self.assertFalse(
            MetaModel.objects.filter(code="deepseek-r1-0528").exists(),
        )
        self.assertIn(
            "deepseek-r1-0528",
            MetaModel.objects.get(code="deepseek-r1").aliases,
        )
        self.assertGreater(seed_stats["models"], 0)

    def test_reset_command_refuses_without_yes(self):
        from io import StringIO

        from django.core.management import call_command
        from django.core.management.base import CommandError

        out = StringIO()
        with self.assertRaises(CommandError):
            call_command("reset_llm_ops_meta_models", stdout=out)

    def test_reset_command_dry_run_is_safe(self):
        from io import StringIO

        from django.core.management import call_command

        seed_initial_price_sheet_safely()
        before = MetaModel.objects.count()
        out = StringIO()
        call_command("reset_llm_ops_meta_models", "--dry-run", stdout=out)
        self.assertEqual(MetaModel.objects.count(), before)
        self.assertIn("[dry-run]", out.getvalue())

    def test_clean_mock_seed_data_removes_legacy_demo_rows(self):
        seed_initial_price_sheet_safely()
        seed_yunce_supplier_price_demo()
        seed_agione_price_trend_demo()
        real_channel = ProcurementChannel.objects.create(
            name="真实资源平台",
            code=REAL_RESOURCE_CHANNEL_CODE,
            currency="USD",
        )
        real_source = PriceCollectionSource.objects.filter(
            slug__endswith="-sheet",
        ).first()
        real_source.channel = real_channel
        real_source.save()
        real_model = LLMModel.objects.first()
        ChannelModelPrice.objects.create(
            channel=real_channel,
            model=real_model,
            meta_model=real_model.meta_model,
            price_source=real_source,
        )
        test_channel = ProcurementChannel.objects.create(
            name="测试 02",
            code="test-02",
            currency="CNY",
        )
        test_source = PriceCollectionSource.objects.create(
            name="测试 02 供应商价格",
            slug="test-02-supplier",
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
        )
        test_model = LLMModel.objects.first()
        ChannelModelPrice.objects.create(
            channel=test_channel,
            model=test_model,
            meta_model=test_model.meta_model,
        )
        ChannelPriceItem.objects.create(
            channel=test_channel,
            model=test_model,
            meta_model=test_model.meta_model,
            source=test_source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="CNY",
            unit_price=Decimal("4"),
            price_fingerprint="legacy-test-fingerprint",
        )

        self.assertTrue(
            ProcurementChannel.objects.filter(
                code="yunce-supplier-platform",
            ).exists()
        )
        self.assertTrue(
            PriceCollectionSource.objects.filter(
                slug="yunce-aliyun-qwen-plus",
            ).exists()
        )
        self.assertTrue(
            ModelPriceItem.objects.filter(
                spec__mock_source="yunce_supplier",
            ).exists()
        )
        self.assertTrue(ChannelModelPriceHistory.objects.exists())

        stats = clean_mock_llm_ops_seed_data()
        second_stats = clean_mock_llm_ops_seed_data()

        self.assertGreater(stats["sources"], 0)
        self.assertGreater(stats["channels"], 0)
        self.assertGreater(stats["channel_model_prices"], 0)
        self.assertGreater(stats["model_price_items"], 0)
        self.assertGreater(stats["channel_model_histories"], 0)
        self.assertFalse(
            ProcurementChannel.objects.filter(
                code="yunce-supplier-platform",
            ).exists()
        )
        self.assertFalse(
            PriceCollectionSource.objects.filter(
                slug__startswith="yunce-",
            ).exists()
        )
        self.assertFalse(
            ProcurementChannel.objects.filter(code="test-02").exists()
        )
        self.assertFalse(
            ProcurementChannel.objects.filter(
                code=REAL_RESOURCE_CHANNEL_CODE,
            ).exists()
        )
        self.assertFalse(
            PriceCollectionSource.objects.filter(
                slug="test-02-supplier",
            ).exists()
        )
        real_source.refresh_from_db()
        self.assertIsNone(real_source.channel_id)
        self.assertEqual(
            sum(second_stats.values()),
            0,
        )


class LLMOpsSupplierAliasApiTests(TestCase):
    """Supplier-only aliases must not appear as meta-model vendors."""

    def test_provider_queryset_hides_supplier_only_aliases(self):
        deepseek = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        LLMProvider.objects.create(
            name="硅基流动",
            code="siliconflow",
        )

        view = LLMProviderViewSet()
        provider_codes = set(
            view.get_queryset().values_list("code", flat=True)
        )

        self.assertIn(deepseek.code, provider_codes)
        self.assertNotIn("siliconflow", provider_codes)

    def test_meta_model_queryset_hides_supplier_only_aliases(self):
        deepseek = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        siliconflow = LLMProvider.objects.create(
            name="硅基流动",
            code="siliconflow",
        )
        MetaModel.objects.create(
            name="DeepSeek V3",
            code="deepseek-v3",
            vendor=deepseek,
        )
        MetaModel.objects.create(
            name="Legacy SiliconFlow Model",
            code="legacy-siliconflow-model",
            vendor=siliconflow,
        )

        view = MetaModelViewSet()
        view.request = mock.Mock(query_params={})
        meta_codes = set(
            view.get_queryset().values_list("code", flat=True)
        )

        self.assertIn("deepseek-v3", meta_codes)
        self.assertNotIn("legacy-siliconflow-model", meta_codes)


class LLMOpsSeedCommandSafeFlagTests(TestCase):
    """The management command exposes a ``--safe`` flag."""

    def test_default_command_overwrites(self):
        from io import StringIO

        from django.core.management import call_command

        seed_initial_price_sheet_safely()
        source = PriceCollectionSource.objects.get(slug="aliyun-sheet")
        source.name = "人工改名价格源"
        source.currency = "USD"
        source.save()

        out = StringIO()
        call_command("seed_llm_ops_price_sheet", stdout=out)

        source.refresh_from_db()
        self.assertNotEqual(source.name, "人工改名价格源")
        self.assertEqual(source.currency, "CNY")
        self.assertIsNone(source.channel_id)
        self.assertIn("[overwrite]", out.getvalue())

    def test_safe_flag_preserves_manual_prices(self):
        from io import StringIO

        from django.core.management import call_command

        seed_initial_price_sheet_safely()
        source = PriceCollectionSource.objects.filter(
            slug__endswith="-sheet",
        ).first()
        source.name = "人工改名价格源"
        source.is_enabled = False
        source.save()

        out = StringIO()
        call_command("seed_llm_ops_price_sheet", "--safe", stdout=out)
        source.refresh_from_db()
        self.assertEqual(source.name, "人工改名价格源")
        self.assertFalse(source.is_enabled)
        self.assertIn("[safe]", out.getvalue())

    def test_clean_mock_flag_removes_legacy_demo_rows(self):
        from io import StringIO

        from django.core.management import call_command

        seed_initial_price_sheet_safely()
        seed_yunce_supplier_price_demo()
        seed_agione_price_trend_demo()

        out = StringIO()
        call_command("seed_llm_ops_price_sheet", "--clean-mock", stdout=out)

        self.assertFalse(
            PriceCollectionSource.objects.filter(
                slug__startswith="yunce-",
            ).exists()
        )
        self.assertFalse(
            ProcurementChannel.objects.filter(
                code="demo-premium-supplier",
            ).exists()
        )
        self.assertFalse(
            ProcurementChannel.objects.filter(
                code=REAL_RESOURCE_CHANNEL_CODE,
            ).exists()
        )
        self.assertIn("Cleaned legacy mock", out.getvalue())


class LLMOpsBootstrapCommandTests(TestCase):
    """The explicit bootstrap command seeds only on a fresh database."""

    def test_bootstrap_command_seeds_empty_database(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("bootstrap_llm_ops_catalog", stdout=out)

        self.assertTrue(LLMProvider.objects.filter(code="openai").exists())
        self.assertIn("Bootstrapped LLM Ops catalog", out.getvalue())

    def test_bootstrap_command_skips_populated_database(self):
        from io import StringIO

        from django.core.management import call_command

        LLMProvider.objects.create(name="OpenAI", code="openai")

        out = StringIO()
        call_command("bootstrap_llm_ops_catalog", stdout=out)

        self.assertEqual(LLMProvider.objects.count(), 1)
        self.assertIn("already initialized", out.getvalue())
