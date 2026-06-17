"""Tests for the llm_ops deployment bootstrap and periodic tasks.

These tests cover the four guarantees that the deployment pipeline
relies on:

1. ``seed_initial_price_sheet_if_empty`` runs the import on a fresh
   database, but is a no-op when canonical rows already exist.
2. ``seed_initial_price_sheet_safely`` never overwrites manually
   maintained overrides (``ChannelModelPrice.custom_*``,
   ``LLMModel.is_active``, ``PriceCollectionSource.is_enabled``).
3. The ``post_migrate`` handler registered by ``apps.py`` fires the
   safe seed on a clean database and skips on a populated one.
4. ``register_periodic_tasks`` exposes a single
   ``llm_ops_official_collect`` entry, and the corresponding Celery
   task is registered with the worker.
"""
from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.apps import apps
from django.test import TestCase

from llm_ops.models import (
    ChannelModelPrice,
    ChannelModelPriceHistory,
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
    reset_meta_models_canonical,
    resolve_orphan_meta_models,
    seed_yunce_supplier_price_demo,
)
from llm_ops.signals import auto_seed_initial_price_sheet
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

    def test_is_llm_ops_database_empty_false_when_channel_exists(self):
        ProcurementChannel.objects.create(
            name="Real Resource",
            code=REAL_RESOURCE_CHANNEL_CODE,
        )
        self.assertFalse(is_llm_ops_database_empty())


class LLMOpsSeedSafelyTests(TestCase):
    """``seed_initial_price_sheet_safely`` must preserve human edits."""

    def setUp(self):
        # Run the safe seed once so the schema has canonical rows.
        stats = seed_initial_price_sheet_safely()
        self.assertGreater(stats["providers"], 0)
        self.assertGreater(stats["models"], 0)

    def test_safe_seed_preserves_channel_model_price_custom_prices(self):
        cmp = ChannelModelPrice.objects.filter(
            channel__code=REAL_RESOURCE_CHANNEL_CODE,
        ).first()
        cmp.custom_input_price_per_million = Decimal("9.999999")
        cmp.custom_output_price_per_million = Decimal("8.888888")
        cmp.is_listed = False
        cmp.save()

        seed_initial_price_sheet_safely()

        cmp.refresh_from_db()
        self.assertEqual(
            cmp.custom_input_price_per_million, Decimal("9.999999")
        )
        self.assertEqual(
            cmp.custom_output_price_per_million, Decimal("8.888888")
        )
        # is_listed is a human toggle. Safe seed never re-enables
        # channels the operator took offline.
        self.assertFalse(cmp.is_listed)

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
        first_prices = ChannelModelPrice.objects.count()

        stats = seed_initial_price_sheet_safely()

        self.assertEqual(stats["providers"], 0)
        self.assertEqual(stats["models"], 0)
        self.assertEqual(stats["channel_model_prices"], 0)
        self.assertEqual(LLMProvider.objects.count(), first_providers)
        self.assertEqual(LLMModel.objects.count(), first_models)
        self.assertEqual(
            ChannelModelPrice.objects.count(), first_prices
        )


class LLMOpsSeedLegacyTests(TestCase):
    """``seed_initial_price_sheet`` keeps its overwrite semantics.

    The explicit ``manage.py seed_llm_ops_price_sheet`` command still
    re-applies the canonical defaults so operators can re-import after
    editing the price sheet source. This test pins the behaviour and
    documents that it is intentional and distinct from the safe path.
    """

    def test_legacy_seed_overwrites_seed_managed_fields(self):
        """Legacy seed re-applies its own defaults (is_listed, currency, ...).

        The two seed paths differ in this respect: the safe seed
        leaves seed-managed fields alone on already-existing rows,
        while the legacy seed (used by the management command) is
        the canonical "re-import the price sheet" operation. This
        test pins that difference so a future refactor cannot
        silently make the two paths equivalent.
        """
        seed_initial_price_sheet_safely()
        cmp = ChannelModelPrice.objects.filter(
            channel__code=REAL_RESOURCE_CHANNEL_CODE,
        ).first()
        # Operator flips the channel price offline and overrides the
        # settlement ratio.
        cmp.is_listed = False
        cmp.settlement_ratio = Decimal("0.1234")
        cmp.save()

        seed_initial_price_sheet()

        cmp.refresh_from_db()
        # ``is_listed`` and ``settlement_ratio`` are seed-managed and
        # are restored by the legacy re-import.
        self.assertTrue(cmp.is_listed)
        self.assertNotEqual(cmp.settlement_ratio, Decimal("0.1234"))


class LLMOpsSeedIfEmptyTests(TestCase):
    """``seed_initial_price_sheet_if_empty`` is the auto-seed gate."""

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


class LLMOpsPostMigrateHandlerTests(TestCase):
    """The ``post_migrate`` signal handler fires the safe seed once."""

    def setUp(self):
        # Reset the module-level re-entry flag so each test gets a
        # clean slate regardless of test execution order.
        setattr(
            auto_seed_initial_price_sheet,
            "_llm_ops_bootstrap_post_migrate_seen",
            False,
        )

    def test_handler_seeds_empty_database(self):
        app_config = apps.get_app_config("llm_ops")
        with mock.patch.dict(
            "os.environ",
            {"LLM_OPS_AUTO_SEED_IN_TESTS": "1"},
        ):
            auto_seed_initial_price_sheet(
                sender=app_config, app_config=app_config
            )
        # The handler should have triggered the safe seed and
        # therefore populated the canonical tables.
        self.assertTrue(LLMProvider.objects.exists())
        self.assertTrue(LLMModel.objects.exists())
        self.assertTrue(
            ProcurementChannel.objects.filter(
                code=REAL_RESOURCE_CHANNEL_CODE
            ).exists()
        )

    def test_handler_is_noop_when_database_already_populated(self):
        LLMProvider.objects.create(name="OpenAI", code="openai")
        app_config = apps.get_app_config("llm_ops")
        auto_seed_initial_price_sheet(
            sender=app_config, app_config=app_config
        )
        # Operator's pre-existing provider must remain untouched
        # (no other providers imported).
        self.assertEqual(LLMProvider.objects.count(), 1)
        self.assertEqual(
            LLMProvider.objects.get(code="openai").name, "OpenAI"
        )

    def test_handler_ignores_other_apps(self):
        other = apps.get_app_config("contenttypes")
        auto_seed_initial_price_sheet(
            sender=other, app_config=other
        )
        # The handler must not seed on signals from other apps.
        self.assertFalse(LLMProvider.objects.exists())

    def test_handler_ignores_none_sender(self):
        auto_seed_initial_price_sheet(sender=None)
        self.assertFalse(LLMProvider.objects.exists())

    def test_handler_skips_in_test_mode(self):
        # Even on an empty DB, the handler must not seed during a
        # test run. Tests opt in explicitly by calling
        # ``seed_initial_price_sheet_if_empty`` instead.
        app_config = apps.get_app_config("llm_ops")
        with mock.patch.dict(
            "os.environ",
            {"PYTEST_CURRENT_TEST": "some/test.py::Test"},
        ):
            auto_seed_initial_price_sheet(
                sender=app_config, app_config=app_config
            )
        self.assertFalse(LLMProvider.objects.exists())


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
        deepseek_r1_0528 = MetaModel.objects.get(code="deepseek-r1-0528")
        deepseek_v3 = MetaModel.objects.get(code="deepseek-v3")
        qwen_plus = MetaModel.objects.get(code="qwen-plus")
        self.assertEqual(deepseek_r1.vendor, deepseek)
        self.assertEqual(deepseek_r1_0528.vendor, deepseek)
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
            "deepseek-r1-0528",
            "deepseek-v3",
            "deepseek-v3.1",
            "deepseek-v3.2",
            "deepseek-v3.2-exp",
        ]
        for code in deepseek_codes:
            meta = MetaModel.objects.get(code=code)
            self.assertEqual(meta.vendor.code, "deepseek")
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
        cmp = ChannelModelPrice.objects.filter(
            channel__code=REAL_RESOURCE_CHANNEL_CODE,
        ).first()
        cmp.is_listed = False
        cmp.settlement_ratio = Decimal("0.1234")
        cmp.save()

        out = StringIO()
        call_command("seed_llm_ops_price_sheet", stdout=out)

        cmp.refresh_from_db()
        self.assertTrue(cmp.is_listed)
        self.assertNotEqual(cmp.settlement_ratio, Decimal("0.1234"))
        self.assertIn("[overwrite]", out.getvalue())

    def test_safe_flag_preserves_manual_prices(self):
        from io import StringIO

        from django.core.management import call_command

        seed_initial_price_sheet_safely()
        cmp = ChannelModelPrice.objects.filter(
            channel__code=REAL_RESOURCE_CHANNEL_CODE,
        ).first()
        cmp.is_listed = False
        cmp.settlement_ratio = Decimal("0.2345")
        cmp.save()

        out = StringIO()
        call_command("seed_llm_ops_price_sheet", "--safe", stdout=out)
        cmp.refresh_from_db()
        self.assertFalse(cmp.is_listed)
        self.assertEqual(cmp.settlement_ratio, Decimal("0.2345"))
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
        self.assertIn("Cleaned legacy mock", out.getvalue())


class LLMOpsPostMigrateHandlerErrorPathTests(TestCase):
    """The handler must swallow seed errors so the migration pipeline
    never aborts because of a transient bootstrap problem.

    Auto-seed is best-effort: the operator can re-run
    ``manage.py seed_llm_ops_price_sheet`` after the fact. Crashing
    inside ``post_migrate`` would block the entire deploy.
    """

    def setUp(self):
        setattr(
            auto_seed_initial_price_sheet,
            "_llm_ops_bootstrap_post_migrate_seen",
            False,
        )

    def test_handler_logs_and_swallows_seed_exception(self):
        # The handler imports ``seed_initial_price_sheet_if_empty``
        # lazily from ``llm_ops.seed_data``; patch the source module
        # so we exercise the ``except`` path.
        app_config = apps.get_app_config("llm_ops")
        with mock.patch(
            "llm_ops.seed_data.seed_initial_price_sheet_if_empty",
            side_effect=RuntimeError("boom"),
        ):
            with mock.patch.dict(
                "os.environ",
                {"LLM_OPS_AUTO_SEED_IN_TESTS": "1"},
            ):
                # Must not raise: the post_migrate pipeline keeps
                # running even when the bootstrap step fails.
                auto_seed_initial_price_sheet(
                    sender=app_config, app_config=app_config
                )
        self.assertFalse(LLMProvider.objects.exists())

    def test_handler_reentry_is_a_noop(self):
        """The module-level flag prevents running the seed twice."""
        app_config = apps.get_app_config("llm_ops")
        with mock.patch.dict(
            "os.environ",
            {"LLM_OPS_AUTO_SEED_IN_TESTS": "1"},
        ):
            auto_seed_initial_price_sheet(
                sender=app_config, app_config=app_config
            )
            count_after_first = LLMProvider.objects.count()
            # Second call within the same process: the flag short
            # circuits. Database state must remain identical.
            auto_seed_initial_price_sheet(
                sender=app_config, app_config=app_config
            )
        self.assertEqual(LLMProvider.objects.count(), count_after_first)
