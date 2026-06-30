import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from llm_ops.models import (
    AuditLog,
    ChannelModelPrice,
    ChannelModelPriceHistory,
    ChannelPriceItem,
    CollectedModelPriceSnapshot,
    LLMModel,
    LLMOpsGlobalConfig,
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    PriceCollectionRun,
    PriceCollectionSource,
    ProcurementChannel,
    ResaleListing,
    ResaleListingExclusion,
    ResaleListingPriceHistory,
    ResalePlatform,
    ResaleWorkflowConfig,
)


class LLMOpsViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username="ops",
            password="secret",
            is_staff=True,
        )
        self.client.force_authenticate(self.user)

    def _create_online_listing(self, **kwargs):
        defaults = {
            "publish_status": ResaleListing.PUBLISH_ONLINE,
            "workflow_status": ResaleListing.WORKFLOW_ONLINE,
            "is_active": True,
        }
        defaults.update(kwargs)
        return ResaleListing.objects.create(**defaults)

    @patch("llm_ops.views.sync_yunce_model_prices")
    def test_yunce_collection_endpoint_returns_sync_stats(self, mock_sync):
        mock_sync.return_value = {
            "models": 3,
            "created": 2,
            "updated": 1,
            "skipped": 0,
        }

        response = self.client.post(
            reverse("llm-ops-yunce-collect"),
            {
                "username": "user",
                "password": "secret",
                "base_url": "https://llm.guohe-sh.com/admin/api",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["models"], 3)
        mock_sync.assert_called_once_with(
            username="user",
            password="secret",
            base_url="https://llm.guohe-sh.com/admin/api",
        )

    @patch("llm_ops.views.sync_yunce_model_prices")
    def test_yunce_collection_endpoint_accepts_source_id(self, mock_sync):
        source = PriceCollectionSource.objects.create(
            name="Yunce Production",
            slug="yunce-production",
            source_type=PriceCollectionSource.SOURCE_TYPE_YUNCE,
            endpoint_url="https://example.com/admin/api",
        )
        mock_sync.return_value = {
            "models": 1,
            "created": 1,
            "updated": 0,
            "skipped": 0,
        }

        response = self.client.post(
            reverse("llm-ops-yunce-collect"),
            {
                "source_id": source.id,
                "username": "user",
                "password": "secret",
                "base_url": "https://example.com/admin/api",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        mock_sync.assert_called_once_with(
            username="user",
            password="secret",
            source=source,
            base_url="https://example.com/admin/api",
        )

    def test_global_config_patch_syncs_periodic_tasks(self):
        from django_celery_beat.models import PeriodicTask

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
            updates_model_prices=True,
        )

        response = self.client.patch(
            reverse("llm-ops-global-config"),
            {
                "meta_model_sync_enabled": True,
                "meta_model_sync_source_url": "https://models.dev/api.json",
                "meta_model_sync_cron": "5 3 * * *",
                "price_collection_enabled": True,
                "price_collection_source_ids": [source.id],
                "price_collection_cron": "10 */6 * * *",
                "feishu_app_id": "cli_xxx",
                "feishu_app_secret": "secret",
                "feishu_approval_code": "approval_code",
                "feishu_tenant_key": "tenant",
                "notes": "global runtime config",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        config = LLMOpsGlobalConfig.objects.get()
        self.assertEqual(config.updated_by, self.user)
        self.assertEqual(config.price_collection_source_ids, [source.id])
        self.assertNotEqual(config.feishu_app_secret, "secret")
        self.assertTrue(
            config.feishu_app_secret.startswith(
                LLMOpsGlobalConfig.ENCRYPTED_SECRET_PREFIX
            )
        )
        self.assertEqual(config.get_feishu_app_secret(), "secret")
        self.assertNotIn("feishu_app_secret", response.data)
        self.assertTrue(response.data["feishu_app_secret_configured"])

        meta_task = PeriodicTask.objects.get(
            name="llm_ops_meta_models_dev_sync"
        )
        price_task = PeriodicTask.objects.get(
            name="llm_ops_model_price_sync_agent"
        )
        self.assertEqual(meta_task.crontab.minute, "5")
        self.assertEqual(meta_task.crontab.hour, "3")
        self.assertIn("models.dev", meta_task.kwargs)
        self.assertEqual(price_task.crontab.minute, "10")
        self.assertEqual(price_task.crontab.hour, "*/6")
        self.assertIn(str(source.id), price_task.kwargs)
        self.assertEqual(
            price_task.task,
            "llm_ops.tasks.run_model_price_sync_agent",
        )

    def test_global_config_all_sources_writes_null_task_source_ids(self):
        from django_celery_beat.models import PeriodicTask

        response = self.client.patch(
            reverse("llm-ops-global-config"),
            {
                "price_collection_enabled": True,
                "price_collection_source_ids": [],
                "price_collection_cron": "10 */6 * * *",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        price_task = PeriodicTask.objects.get(
            name="llm_ops_model_price_sync_agent"
        )
        self.assertIsNone(json.loads(price_task.kwargs)["source_ids"])

    def test_global_config_stale_sources_write_empty_task_source_ids(self):
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
        config.price_collection_source_ids = [source.id]
        config.save()

        response = self.client.patch(
            reverse("llm-ops-global-config"),
            {"notes": "refresh schedule with stale source ids"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        price_task = PeriodicTask.objects.get(
            name="llm_ops_model_price_sync_agent"
        )
        self.assertEqual(json.loads(price_task.kwargs)["source_ids"], [])

    def test_global_config_blank_secret_preserves_existing_secret(self):
        config = LLMOpsGlobalConfig.get_solo()
        config.set_feishu_app_secret("existing-secret")
        config.save()
        stored_secret = config.feishu_app_secret

        response = self.client.patch(
            reverse("llm-ops-global-config"),
            {
                "feishu_app_secret": "",
                "notes": "updated without rotating the secret",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        config.refresh_from_db()
        self.assertEqual(config.feishu_app_secret, stored_secret)
        self.assertEqual(config.get_feishu_app_secret(), "existing-secret")

    def test_global_config_rejects_unknown_price_source_ids(self):
        response = self.client.patch(
            reverse("llm-ops-global-config"),
            {"price_collection_source_ids": [99999]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("price_collection_source_ids", response.data)

    def test_global_config_rejects_unsupported_price_source_ids(self):
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

        response = self.client.patch(
            reverse("llm-ops-global-config"),
            {"price_collection_source_ids": [source.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("price_collection_source_ids", response.data)

    def test_global_config_accepts_existing_stale_price_source_ids(self):
        from django_celery_beat.models import PeriodicTask

        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        source = PriceCollectionSource.objects.create(
            name="OpenAI Official",
            slug="openai-official-existing",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://openai.com/api/pricing/",
            updates_model_prices=True,
        )
        config = LLMOpsGlobalConfig.get_solo()
        config.price_collection_source_ids = [source.id]
        config.save()

        response = self.client.patch(
            reverse("llm-ops-global-config"),
            {
                "price_collection_source_ids": [source.id],
                "price_collection_cron": "10 */6 * * *",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        price_task = PeriodicTask.objects.get(
            name="llm_ops_model_price_sync_agent"
        )
        self.assertEqual(json.loads(price_task.kwargs)["source_ids"], [])

    def test_global_config_sync_disables_legacy_periodic_task(self):
        from django_celery_beat.models import CrontabSchedule, PeriodicTask

        legacy_crontab = CrontabSchedule.objects.create(
            minute="0",
            hour="4",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
        )
        PeriodicTask.objects.create(
            name="llm_ops_official_collect",
            task="llm_ops.tasks.collect_official_model_prices",
            crontab=legacy_crontab,
            kwargs='{"provider_codes": null, "verify_source": true}',
            enabled=True,
        )

        response = self.client.patch(
            reverse("llm-ops-global-config"),
            {
                "price_collection_enabled": False,
                "price_collection_cron": "10 */6 * * *",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        legacy_task = PeriodicTask.objects.get(name="llm_ops_official_collect")
        self.assertFalse(legacy_task.enabled)
        self.assertEqual(legacy_task.crontab_id, legacy_crontab.id)

    def test_global_config_sync_deletes_managed_source_tasks(self):
        from django_celery_beat.models import CrontabSchedule, PeriodicTask

        provider = LLMProvider.objects.create(name="阿里云", code="aliyun")
        current_source = PriceCollectionSource.objects.create(
            name="Aliyun Official",
            slug="aliyun-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://help.aliyun.com/zh/model-studio/model-pricing"
            ),
            updates_model_prices=True,
        )
        obsolete_source = PriceCollectionSource.objects.create(
            name="Obsolete Source",
            slug="obsolete-source",
            endpoint_url="https://obsolete.example.com",
            updates_model_prices=True,
        )
        custom_crontab = CrontabSchedule.objects.create(
            minute="0",
            hour="8",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
        )
        PeriodicTask.objects.create(
            name=f"llm_ops_price_source_collect_{obsolete_source.id}",
            task="llm_ops.tasks.collect_price_source_prices",
            crontab=custom_crontab,
            kwargs=f'{{"source_id": {obsolete_source.id}}}',
            enabled=True,
        )
        PeriodicTask.objects.create(
            name="llm_ops_price_source_collect_custom",
            task="llm_ops.tasks.collect_price_source_prices",
            crontab=custom_crontab,
            kwargs='{"source_id": "custom"}',
            enabled=True,
        )

        response = self.client.patch(
            reverse("llm-ops-global-config"),
            {
                "price_collection_enabled": True,
                "price_collection_source_ids": [current_source.id],
                "price_collection_cron": "10 */6 * * *",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            PeriodicTask.objects.filter(
                name="llm_ops_model_price_sync_agent"
            ).exists()
        )
        self.assertTrue(
            PeriodicTask.objects.filter(
                name="llm_ops_price_source_collect_custom"
            ).exists()
        )
        self.assertFalse(
            PeriodicTask.objects.filter(
                name=(f"llm_ops_price_source_collect_{obsolete_source.id}")
            ).exists()
        )
        self.assertFalse(
            PeriodicTask.objects.filter(
                name=f"llm_ops_price_source_collect_{current_source.id}"
            ).exists()
        )

    def test_global_config_rejects_invalid_cron(self):
        response = self.client.patch(
            reverse("llm-ops-global-config"),
            {"meta_model_sync_cron": "invalid"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("meta_model_sync_cron", response.data)

    @patch("llm_ops.views.import_manual_model_prices")
    def test_manual_price_import_records_pricing_audit(self, mock_import):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        mock_import.return_value = {
            "created_models": 1,
            "updated_models": 0,
            "created_price_items": 2,
        }

        response = self.client.post(
            reverse("llm-ops-manual-price-import"),
            {
                "provider": provider.id,
                "source_name": "Manual Sheet",
                "source_slug": "manual-sheet",
                "currency": "USD",
                "updates_model_prices": True,
                "rows": [
                    {
                        "model_code": "gpt-5",
                        "model_name": "GPT-5",
                        "input_price_per_million": "1.000000",
                        "output_price_per_million": "5.000000",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        source = PriceCollectionSource.objects.get(slug="manual-sheet")
        audit = AuditLog.objects.get(
            target_type="llm_ops.PriceCollectionSource",
            target_id=str(source.id),
        )
        self.assertEqual(audit.action, AuditLog.ACTION_IMPORT)
        self.assertEqual(audit.category, AuditLog.CATEGORY_PRICING)
        self.assertEqual(audit.metadata["row_count"], 1)
        self.assertEqual(audit.metadata["provider_id"], provider.id)
        self.assertNotIn("rows", audit.metadata)

    @patch("llm_ops.views.import_manual_model_prices")
    def test_manual_price_import_accepts_existing_source(self, mock_import):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        source = PriceCollectionSource.objects.create(
            name="OpenAI Manual Sheet",
            slug="openai-manual-sheet",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_MANUAL,
            currency="CNY",
        )
        mock_import.return_value = {
            "created_models": 0,
            "updated_models": 1,
            "created_price_items": 1,
        }

        response = self.client.post(
            reverse("llm-ops-manual-price-import"),
            {
                "source": source.id,
                "updates_model_prices": True,
                "rows": [
                    {
                        "model_code": "gpt-5",
                        "model_name": "GPT-5",
                        "input_price_per_million": "1.000000",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        mock_import.assert_called_once()
        _, kwargs = mock_import.call_args
        self.assertEqual(kwargs["source"], source)
        self.assertEqual(kwargs["provider"], provider)
        self.assertEqual(kwargs["default_currency"], "CNY")
        self.assertFalse(kwargs["updates_model_prices"])
        self.assertEqual(
            AuditLog.objects.filter(target_id=str(source.id)).count(),
            1,
        )

    def test_collection_source_can_be_deleted(self):
        source = PriceCollectionSource.objects.create(
            name="Manual Source",
            slug="manual-source",
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_MANUAL,
        )

        response = self.client.delete(
            reverse("collection-source-detail", args=[source.id]),
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            PriceCollectionSource.objects.filter(id=source.id).exists()
        )
        audit = AuditLog.objects.get(
            target_type="llm_ops.PriceCollectionSource",
            target_id=str(source.id),
        )
        self.assertEqual(audit.action, AuditLog.ACTION_DELETE)
        self.assertEqual(audit.category, AuditLog.CATEGORY_CONFIGURATION)
        self.assertEqual(audit.before["slug"], "manual-source")

    def test_channel_delete_removes_channel_listings_without_auto_conflict(
        self,
    ):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT Delete Test",
            code="gpt-delete-test",
        )
        channel = ProcurementChannel.objects.create(
            name="Delete Channel",
            code="delete-channel",
        )
        platform = ResalePlatform.objects.create(
            name="Delete Platform",
            code="delete-platform",
            currency="CNY",
        )
        auto_listing = ResaleListing.objects.create(
            platform=platform,
            model=model,
            channel=None,
            retail_input_price_per_million="1.000000",
            retail_output_price_per_million="2.000000",
        )
        channel_listing = ResaleListing.objects.create(
            platform=platform,
            model=model,
            channel=channel,
            retail_input_price_per_million="1.100000",
            retail_output_price_per_million="2.200000",
        )

        response = self.client.delete(
            reverse("channel-detail", args=[channel.id]),
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            ProcurementChannel.objects.filter(id=channel.id).exists(),
        )
        self.assertTrue(
            ResaleListing.objects.filter(id=auto_listing.id).exists(),
        )
        self.assertFalse(
            ResaleListing.objects.filter(id=channel_listing.id).exists(),
        )

    def test_channel_update_records_configuration_audit(self):
        channel = ProcurementChannel.objects.create(
            name="Default Channel",
            code="default-channel",
            currency="USD",
        )

        response = self.client.patch(
            reverse("channel-detail", args=[channel.id]),
            {
                "currency": "CNY",
                "settlement_ratio": "0.8000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        audit = AuditLog.objects.get(
            target_type="llm_ops.ProcurementChannel",
            target_id=str(channel.id),
        )
        self.assertEqual(audit.action, AuditLog.ACTION_UPDATE)
        self.assertEqual(audit.category, AuditLog.CATEGORY_CONFIGURATION)
        self.assertEqual(audit.changes["currency"]["before"], "USD")
        self.assertEqual(audit.changes["currency"]["after"], "CNY")

    def test_audit_log_ignores_invalid_forwarded_ip(self):
        channel = ProcurementChannel.objects.create(
            name="Forwarded Channel",
            code="forwarded-channel",
            currency="USD",
        )

        response = self.client.patch(
            reverse("channel-detail", args=[channel.id]),
            {"currency": "CNY"},
            format="json",
            HTTP_X_FORWARDED_FOR="not-an-ip, 10.0.0.1",
        )

        self.assertEqual(response.status_code, 200)
        audit = AuditLog.objects.get(
            target_type="llm_ops.ProcurementChannel",
            target_id=str(channel.id),
        )
        self.assertIsNone(audit.ip_address)

    def test_audit_logs_endpoint_is_read_only_and_filterable(self):
        channel = ProcurementChannel.objects.create(
            name="Default Channel",
            code="default-channel",
            currency="USD",
        )
        self.client.patch(
            reverse("channel-detail", args=[channel.id]),
            {"currency": "CNY"},
            format="json",
        )

        response = self.client.get(
            reverse("audit-log-list"),
            {"category": AuditLog.CATEGORY_CONFIGURATION},
        )
        create_response = self.client.post(
            reverse("audit-log-list"),
            {"action": AuditLog.ACTION_CREATE},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        rows = response.data.get("results", response.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], AuditLog.CATEGORY_CONFIGURATION)
        self.assertEqual(create_response.status_code, 405)

    def test_audit_logs_endpoint_filters_by_names(self):
        provider = LLMProvider.objects.create(name="DeepSeek", code="deepseek")
        model = LLMModel.objects.create(
            provider=provider,
            name="DeepSeek R1",
            code="deepseek-r1",
        )
        channel = ProcurementChannel.objects.create(
            name="Yunce",
            code="yunce",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        listing = ResaleListing.objects.create(
            platform=platform,
            model=model,
            channel=channel,
            retail_input_price_per_million="1.000000",
            retail_output_price_per_million="2.000000",
        )

        self.client.patch(
            reverse("resale-listing-detail", args=[listing.id]),
            {"notes": "name filter test"},
            format="json",
        )

        target_response = self.client.get(
            reverse("audit-log-list"),
            {"target": "DeepSeek R1"},
        )
        actor_response = self.client.get(
            reverse("audit-log-list"),
            {"actor": "ops"},
        )

        self.assertEqual(target_response.status_code, 200)
        self.assertEqual(actor_response.status_code, 200)
        target_rows = target_response.data.get(
            "results",
            target_response.data,
        )
        actor_rows = actor_response.data.get("results", actor_response.data)
        self.assertEqual(len(target_rows), 1)
        self.assertEqual(target_rows[0]["target_repr"], str(listing))
        self.assertEqual(len(actor_rows), 1)
        self.assertEqual(actor_rows[0]["actor_username"], "ops")

    def test_model_price_item_can_be_updated(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        source = PriceCollectionSource.objects.create(
            name="Manual Source",
            slug="manual-source",
            provider=provider,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_MANUAL,
            currency="USD",
        )
        model = LLMModel.objects.create(
            provider=provider,
            source=source,
            name="GPT-4o mini",
            code="gpt-4o-mini",
        )
        item = ModelPriceItem.objects.create(
            provider=provider,
            model=model,
            source=source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price="0.150000",
            price_fingerprint="manual-input",
            spec={},
        )

        response = self.client.patch(
            reverse("model-price-item-detail", args=[item.id]),
            {
                "unit_price": "0.120000",
                "currency": "CNY",
                "spec": {"note": "manual correction"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(str(item.unit_price), "0.120000")
        self.assertEqual(item.currency, "CNY")
        self.assertEqual(item.spec["note"], "manual correction")
        audit = AuditLog.objects.get(
            target_type="llm_ops.ModelPriceItem",
            target_id=str(item.id),
        )
        self.assertEqual(audit.action, AuditLog.ACTION_UPDATE)
        self.assertEqual(audit.category, AuditLog.CATEGORY_PRICING)
        self.assertEqual(audit.actor, self.user)
        self.assertEqual(
            audit.changes["unit_price"]["before"],
            "0.150000",
        )
        self.assertEqual(audit.changes["unit_price"]["after"], "0.120000")

    def test_model_price_item_can_be_deleted(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-4o mini",
            code="gpt-4o-mini",
        )
        item = ModelPriceItem.objects.create(
            provider=provider,
            model=model,
            dimension=ModelPriceItem.DIMENSION_TEXT_OUTPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price="0.600000",
            price_fingerprint="manual-output",
        )

        response = self.client.delete(
            reverse("model-price-item-detail", args=[item.id]),
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(ModelPriceItem.objects.filter(id=item.id).exists())

    def test_model_with_business_links_cannot_be_deleted(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-4o mini",
            code="gpt-4o-mini",
        )
        channel = ProcurementChannel.objects.create(
            name="Default Channel",
            code="default-channel-delete-block",
        )
        channel_price = ChannelModelPrice.objects.create(
            channel=channel,
            model=model,
            meta_model=model.meta_model,
            currency="USD",
        )

        response = self.client.delete(
            reverse("model-detail", args=[model.id]),
        )

        self.assertEqual(response.status_code, 409)
        self.assertTrue(LLMModel.objects.filter(id=model.id).exists())
        self.assertTrue(
            ChannelModelPrice.objects.filter(id=channel_price.id).exists()
        )

    def test_meta_model_with_provider_prices_cannot_be_deleted(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        meta = LLMModel.objects.create(
            provider=provider,
            name="GPT-4o mini",
            code="gpt-4o-mini",
        ).meta_model

        response = self.client.delete(
            reverse("meta-model-detail", args=[meta.id]),
        )

        self.assertEqual(response.status_code, 409)
        self.assertTrue(MetaModel.objects.filter(id=meta.id).exists())

    @patch("llm_ops.views.collect_price_source_prices.delay")
    def test_collection_source_collects_official_provider(self, mock_delay):
        provider = LLMProvider.objects.create(name="阿里云", code="aliyun")
        source = PriceCollectionSource.objects.create(
            name="Aliyun Official",
            slug="aliyun-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://help.aliyun.com/zh/model-studio/model-pricing"
            ),
            is_enabled=True,
            updates_model_prices=True,
        )
        mock_delay.return_value.id = "task-123"

        response = self.client.post(
            reverse("collection-source-collect", args=[source.id]),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["task_id"], "task-123")
        self.assertEqual(response.data["provider_code"], "aliyun")
        self.assertEqual(response.data["source_id"], source.id)
        mock_delay.assert_called_once_with(
            source_id=source.id,
            verify_source=True,
        )
        audit = AuditLog.objects.get(target_id=str(source.id))
        self.assertEqual(audit.action, AuditLog.ACTION_COLLECT)
        self.assertEqual(audit.category, AuditLog.CATEGORY_COLLECTION)
        self.assertEqual(audit.metadata["task_id"], "task-123")

    @patch("llm_ops.views.run_model_price_sync_agent.delay")
    def test_collection_sources_sync_all_submits_supported_sources(
        self,
        mock_delay,
    ):
        aliyun = LLMProvider.objects.create(name="阿里云", code="aliyun")
        aliyun_source = PriceCollectionSource.objects.create(
            name="Aliyun Official",
            slug="aliyun-official",
            provider=aliyun,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://help.aliyun.com/zh/model-studio/model-pricing"
            ),
            is_enabled=True,
            updates_model_prices=True,
        )
        PriceCollectionSource.objects.create(
            name="Aliyun Qwen Plus Official",
            slug="aliyun-qwen-plus-official",
            provider=aliyun,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url=(
                "https://help.aliyun.com/zh/model-studio/model-pricing"
            ),
            is_enabled=True,
            updates_model_prices=True,
        )
        openai = LLMProvider.objects.create(name="OpenAI", code="openai")
        openai_source = PriceCollectionSource.objects.create(
            name="OpenAI Official",
            slug="openai-official",
            provider=openai,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://openai.com/api/pricing/",
            is_enabled=True,
            updates_model_prices=True,
        )
        mock_delay.return_value.id = "task-all"

        response = self.client.post(reverse("collection-source-sync-all"))

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["task_id"], "task-all")
        self.assertEqual(response.data["source_count"], 2)
        self.assertEqual(
            response.data["source_ids"],
            [aliyun_source.id, openai_source.id],
        )
        mock_delay.assert_called_once_with(
            source_ids=[aliyun_source.id, openai_source.id],
            verify_source=True,
        )
        audit = AuditLog.objects.get(
            target_type="llm_ops.PriceCollectionSource",
            action=AuditLog.ACTION_SYNC,
        )
        self.assertEqual(audit.metadata["task_id"], "task-all")
        self.assertEqual(
            audit.metadata["source_ids"],
            [aliyun_source.id, openai_source.id],
        )

    @patch("llm_ops.views.run_model_price_sync_agent.delay")
    def test_collection_sources_sync_all_rejects_without_sources(
        self,
        mock_delay,
    ):
        response = self.client.post(reverse("collection-source-sync-all"))

        self.assertEqual(response.status_code, 400)
        mock_delay.assert_not_called()

    def test_official_provider_options_include_aliyun_presets(self):
        response = self.client.get(
            reverse("collection-source-official-provider-options")
        )

        self.assertEqual(response.status_code, 200)
        provider_codes = {
            item["provider_code"] for item in response.data["results"]
        }
        self.assertIn("aliyun", provider_codes)
        self.assertIn("aliyun-wanx", provider_codes)
        self.assertIn("baidu", provider_codes)
        self.assertIn("volcengine", provider_codes)

    def test_ensure_official_provider_source_creates_aliyun_source(self):
        response = self.client.post(
            reverse("collection-source-ensure-official-provider"),
            {"provider_code": "aliyun"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["provider_created"])
        self.assertTrue(response.data["source_created"])
        self.assertEqual(response.data["source"]["slug"], "aliyun-official")
        self.assertEqual(response.data["source"]["provider_code"], "aliyun")
        self.assertEqual(response.data["source"]["currency"], "CNY")
        provider = LLMProvider.objects.get(code="aliyun")
        source = PriceCollectionSource.objects.get(slug="aliyun-official")
        self.assertEqual(source.provider, provider)
        self.assertEqual(
            source.source_category,
            PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER,
        )
        self.assertTrue(source.updates_model_prices)
        audit = AuditLog.objects.get(target_id=str(source.id))
        self.assertEqual(audit.action, AuditLog.ACTION_CREATE)
        self.assertEqual(audit.category, AuditLog.CATEGORY_CONFIGURATION)
        self.assertEqual(audit.metadata["provider_code"], "aliyun")

    def test_ensure_official_provider_source_is_idempotent(self):
        first = self.client.post(
            reverse("collection-source-ensure-official-provider"),
            {"provider_code": "aliyun"},
            format="json",
        )
        second = self.client.post(
            reverse("collection-source-ensure-official-provider"),
            {"provider_code": "aliyun"},
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.data["provider_created"])
        self.assertFalse(second.data["source_created"])
        self.assertEqual(
            first.data["source"]["id"],
            second.data["source"]["id"],
        )
        self.assertEqual(
            PriceCollectionSource.objects.filter(
                slug="aliyun-official",
            ).count(),
            1,
        )

    @patch("llm_ops.views.collect_price_source_prices.delay")
    def test_collection_source_collect_rejects_disabled_source(
        self,
        mock_delay,
    ):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        source = PriceCollectionSource.objects.create(
            name="OpenAI Official",
            slug="openai-official-disabled",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            is_enabled=False,
            updates_model_prices=True,
        )

        response = self.client.post(
            reverse("collection-source-collect", args=[source.id]),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "Price collection source is disabled.",
        )
        mock_delay.assert_not_called()

    @patch("llm_ops.views.collect_price_source_prices.delay")
    def test_collection_source_collect_rejects_unsupported_source(
        self,
        mock_delay,
    ):
        provider = LLMProvider.objects.create(name="DeepSeek", code="deepseek")
        source = PriceCollectionSource.objects.create(
            name="SiliconFlow Sheet",
            slug="siliconflow-sheet",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            endpoint_url="https://example.com/pricing",
            is_enabled=True,
            updates_model_prices=True,
        )

        response = self.client.post(
            reverse("collection-source-collect", args=[source.id]),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            (
                "This source does not support direct collection yet. "
                "Use manual import or a dedicated collector."
            ),
        )
        mock_delay.assert_not_called()

    @patch("llm_ops.views.source_supports_code_collection")
    @patch("llm_ops.views.collect_price_source_prices.delay")
    def test_collection_source_collect_does_not_require_provider(
        self,
        mock_delay,
        mock_supports_collection,
    ):
        source = PriceCollectionSource.objects.create(
            name="Supplier API",
            slug="supplier-api",
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            endpoint_url="https://example.com/pricing",
            is_enabled=True,
            updates_model_prices=True,
        )
        mock_supports_collection.return_value = True
        mock_delay.return_value.id = "task-456"

        response = self.client.post(
            reverse("collection-source-collect", args=[source.id]),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["task_id"], "task-456")
        self.assertEqual(response.data["provider_code"], "")
        self.assertEqual(response.data["source_id"], source.id)
        mock_delay.assert_called_once_with(
            source_id=source.id,
            verify_source=True,
        )

    def test_collection_run_list_filters_task_logs(self):
        provider = LLMProvider.objects.create(
            name="Alibaba Cloud",
            code="aliyun",
        )
        source = PriceCollectionSource.objects.create(
            name="Aliyun Official",
            slug="aliyun-official",
            provider=provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
        )
        other_source = PriceCollectionSource.objects.create(
            name="Supplier API",
            slug="supplier-api",
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
        )
        target_run = PriceCollectionRun.objects.create(
            source=source,
            status=PriceCollectionRun.STATUS_FAILED,
            error_message="remote page changed",
        )
        PriceCollectionRun.objects.create(
            source=other_source,
            status=PriceCollectionRun.STATUS_SUCCEEDED,
        )

        response = self.client.get(
            reverse("collection-run-list"),
            {
                "provider": "aliyun",
                "q": "page changed",
                "source_category": (
                    PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
                ),
                "status": PriceCollectionRun.STATUS_FAILED,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], target_run.id)

    def test_collected_price_snapshot_list_returns_normalized_rows(self):
        source = PriceCollectionSource.objects.create(
            name="Yunce",
            slug="yunce",
            source_type=PriceCollectionSource.SOURCE_TYPE_YUNCE,
        )
        run = PriceCollectionRun.objects.create(
            source=source,
            status=PriceCollectionRun.STATUS_SUCCEEDED,
            collected_count=1,
        )
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-4o",
            code="gpt-4o",
        )
        CollectedModelPriceSnapshot.objects.create(
            source=source,
            run=run,
            provider=provider,
            model=model,
            source_platform_id="1",
            source_model_id="gpt-4o",
            source_model_name="GPT-4o",
            source_model_type="Text",
            source_provider_name="OpenAI",
            currency="USD",
            normalized_price_rows=[
                {
                    "kind": "text_token",
                    "values": {
                        "input_price": 2.5,
                        "output_price": 10,
                    },
                    "raw": {},
                }
            ],
        )

        response = self.client.get(
            reverse("collected-price-snapshot-list"),
            {"source_model_type": "Text"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["results"][0]["source_model_name"],
            "GPT-4o",
        )
        self.assertEqual(
            response.data["results"][0]["normalized_price_rows"][0]["kind"],
            "text_token",
        )

    def test_summary_only_uses_configured_channel_models(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
            input_price_per_million="2.5",
            output_price_per_million="5",
        )
        channel = ProcurementChannel.objects.create(
            name="Real Resource",
            code="real-resource",
            settlement_ratio="0.8",
        )

        response = self.client.get(
            reverse("llm-ops-summary"),
            {"display_currency": "USD"},
        )

        self.assertEqual(response.status_code, 200)
        row = response.data["procurement"][0]
        self.assertIsNone(row["best_channel"])
        self.assertEqual(row["options"], [])

        ChannelModelPrice.objects.create(channel=channel, model=model)

        response = self.client.get(
            reverse("llm-ops-summary"),
            {"display_currency": "USD"},
        )

        row = response.data["procurement"][0]
        self.assertEqual(row["meta_model_id"], model.meta_model_id)
        self.assertEqual(row["meta_model_name"], "GPT-5")
        self.assertEqual(row["meta_model_code"], "gpt-5")
        self.assertEqual(row["best_channel"]["channel_name"], "Real Resource")
        self.assertEqual(row["best_channel"]["original_currency"], "USD")
        self.assertEqual(row["best_channel"]["settlement_ratio"], 0.8)
        self.assertEqual(
            row["best_channel"]["base_input_price_per_million"],
            2.5,
        )
        self.assertEqual(
            row["best_channel"]["input_price_per_million_settlement_ratio"],
            0.8,
        )
        self.assertEqual(row["best_channel"]["input_price_per_million"], 2.0)

    def test_summary_exposes_channel_model_performance_metrics(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
            input_price_per_million="2.5",
            output_price_per_million="5",
        )
        channel = ProcurementChannel.objects.create(
            name="Real Resource",
            code="real-resource-perf",
        )
        ChannelModelPrice.objects.create(
            channel=channel,
            model=model,
            tpm_limit=1000000,
            rpm_limit=3000,
            latency_ms=180,
        )

        response = self.client.get(
            reverse("llm-ops-summary"),
            {"display_currency": "USD"},
        )

        self.assertEqual(response.status_code, 200)
        row = response.data["procurement"][0]
        option = row["options"][0]
        self.assertEqual(option["tpm_limit"], 1000000)
        self.assertEqual(option["rpm_limit"], 3000)
        self.assertEqual(option["latency_ms"], 180)
        self.assertEqual(row["best_channel"]["tpm_limit"], 1000000)
        self.assertEqual(row["best_channel"]["rpm_limit"], 3000)
        self.assertEqual(row["best_channel"]["latency_ms"], 180)

    def test_summary_uses_meta_model_price_items_for_zero_sku_price(self):
        provider = LLMProvider.objects.create(
            name="Anthropic", code="anthropic"
        )
        official_model = LLMModel.objects.create(
            provider=provider,
            name="Claude Haiku 4.5",
            code="claude-haiku-4-5-official",
            input_price_per_million="1",
            output_price_per_million="5",
        )
        channel_model = LLMModel.objects.create(
            provider=provider,
            meta_model=official_model.meta_model,
            name="Claude Haiku 4.5",
            code="claude-haiku-4-5-channel",
        )
        source = PriceCollectionSource.objects.create(
            name="Anthropic Official",
            slug="anthropic-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
        )
        ModelPriceItem.objects.create(
            provider=provider,
            source=source,
            model=official_model,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price="1",
            price_fingerprint="official-input",
        )
        ModelPriceItem.objects.create(
            provider=provider,
            source=source,
            model=official_model,
            dimension=ModelPriceItem.DIMENSION_TEXT_OUTPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price="5",
            price_fingerprint="official-output",
        )
        channel = ProcurementChannel.objects.create(
            name="Real Resource",
            code="real-resource-zero-sku",
            currency="USD",
        )
        ChannelModelPrice.objects.create(
            channel=channel,
            model=channel_model,
            is_listed=True,
            settlement_ratio="0.5",
        )

        response = self.client.get(
            reverse("llm-ops-summary"),
            {"display_currency": "USD"},
        )

        self.assertEqual(response.status_code, 200)
        row = next(
            item
            for item in response.data["procurement"]
            if item["model_id"] == channel_model.id
        )
        self.assertEqual(row["best_channel"]["input_price_per_million"], 0.5)
        self.assertEqual(row["best_channel"]["output_price_per_million"], 2.5)

    def test_summary_skips_channel_options_without_text_price(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5-no-price",
        )
        channel = ProcurementChannel.objects.create(
            name="Empty Channel",
            code="empty-channel",
        )
        ChannelModelPrice.objects.create(
            channel=channel,
            model=model,
            is_listed=True,
        )

        response = self.client.get(reverse("llm-ops-summary"))

        self.assertEqual(response.status_code, 200)
        row = response.data["procurement"][0]
        self.assertIsNone(row["best_channel"])
        self.assertEqual(row["options"], [])

    def test_channel_model_price_bulk_upsert_updates_existing_rows(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Real Resource",
            code="real-resource",
        )
        source = PriceCollectionSource.objects.create(
            name="Supplier A",
            slug="supplier-a",
            provider=provider,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
        )
        ChannelModelPrice.objects.create(
            channel=channel,
            model=model,
            settlement_ratio="0.9",
        )

        response = self.client.post(
            reverse("channel-model-price-bulk-upsert"),
            {
                "items": [
                    {
                        "channel": channel.id,
                        "model": model.id,
                        "price_source": source.id,
                        "is_listed": True,
                        "settlement_ratio": "0.55",
                        "tpm_limit": 1000000,
                        "rpm_limit": 3000,
                        "latency_ms": 220,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ChannelModelPrice.objects.count(), 1)
        price = ChannelModelPrice.objects.get()
        self.assertEqual(
            str(price.settlement_ratio),
            "0.5500",
        )
        self.assertEqual(price.price_source, source)
        self.assertEqual(price.tpm_limit, 1000000)
        self.assertEqual(price.rpm_limit, 3000)
        self.assertEqual(price.latency_ms, 220)
        self.assertEqual(response.data[0]["tpm_limit"], 1000000)
        self.assertEqual(response.data[0]["rpm_limit"], 3000)
        self.assertEqual(response.data[0]["latency_ms"], 220)
        self.assertEqual(ChannelModelPriceHistory.objects.count(), 1)
        history = ChannelModelPriceHistory.objects.get()
        self.assertEqual(history.price_source, source)
        self.assertEqual(
            history.input_price_per_million,
            model.input_price_per_million,
        )

    def test_channel_model_price_bulk_upsert_syncs_price_items(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Real Resource",
            code="real-resource",
        )
        ModelPriceItem.objects.create(
            provider=provider,
            model=model,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price="2.5",
            price_fingerprint="official-input",
        )

        response = self.client.post(
            reverse("channel-model-price-bulk-upsert"),
            {
                "items": [
                    {
                        "channel": channel.id,
                        "model": model.id,
                        "is_listed": True,
                        "settlement_ratio": "0.5",
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        item = ChannelPriceItem.objects.get()
        self.assertEqual(str(item.unit_price), "1.250000")
        self.assertEqual(item.comparison_status, "below_official")

    def test_channel_model_price_sync_price_items_action(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Real Resource",
            code="real-resource",
            settlement_ratio="0.5",
        )
        ChannelModelPrice.objects.create(
            channel=channel,
            model=model,
            is_listed=True,
        )
        ModelPriceItem.objects.create(
            provider=provider,
            model=model,
            dimension=ModelPriceItem.DIMENSION_TEXT_OUTPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price="10",
            price_fingerprint="official-output",
        )

        response = self.client.post(
            reverse("channel-model-price-sync-price-items"),
            {"channel": channel.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["models"], 1)
        self.assertEqual(response.data["price_items"], 1)
        self.assertEqual(ChannelPriceItem.objects.count(), 1)
        audit = AuditLog.objects.get(
            target_type="llm_ops.ChannelPriceItem",
        )
        self.assertEqual(audit.action, AuditLog.ACTION_SYNC)
        self.assertEqual(audit.category, AuditLog.CATEGORY_PRICING)
        self.assertEqual(audit.metadata["models"], 1)
        self.assertEqual(audit.metadata["price_items"], 1)

    def test_channel_model_price_rejects_negative_custom_price(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Real Resource",
            code="real-resource",
        )

        response = self.client.post(
            reverse("channel-model-price-list"),
            {
                "channel": channel.id,
                "model": model.id,
                "custom_input_price_per_million": "-1",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_resale_listing_bulk_replace_deactivates_previous_listings(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        old_channel = ProcurementChannel.objects.create(
            name="Old Channel",
            code="old-channel",
        )
        best_channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        self._create_online_listing(
            platform=platform,
            model=model,
            channel=old_channel,
            retail_input_price_per_million="2.0",
            retail_output_price_per_million="4.0",
        )

        response = self.client.post(
            reverse("resale-listing-bulk-replace"),
            {
                "items": [
                    {
                        "platform": platform.id,
                        "model": model.id,
                        "channel": best_channel.id,
                        "display_name": "GPT-5",
                        "retail_input_price_per_million": "1.2",
                        "retail_output_price_per_million": "2.4",
                        "is_active": True,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        old_listing = ResaleListing.objects.get(channel=old_channel)
        new_listing = ResaleListing.objects.get(channel=best_channel)
        self.assertFalse(old_listing.is_active)
        self.assertEqual(
            old_listing.publish_status,
            ResaleListing.PUBLISH_OFFLINE,
        )
        self.assertEqual(
            old_listing.workflow_status,
            ResaleListing.WORKFLOW_OFFLINE,
        )
        self.assertFalse(new_listing.is_active)
        self.assertEqual(
            new_listing.publish_status,
            ResaleListing.PUBLISH_NONE,
        )
        self.assertEqual(
            new_listing.workflow_status,
            ResaleListing.WORKFLOW_PENDING_PUBLISH,
        )
        self.assertEqual(ResaleListingPriceHistory.objects.count(), 2)

    def test_resale_listing_bulk_upsert_keeps_previous_listings_active(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        old_channel = ProcurementChannel.objects.create(
            name="Old Channel",
            code="old-channel",
        )
        best_channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        self._create_online_listing(
            platform=platform,
            model=model,
            channel=old_channel,
            retail_input_price_per_million="2.0",
            retail_output_price_per_million="4.0",
        )

        response = self.client.post(
            reverse("resale-listing-bulk-upsert"),
            {
                "items": [
                    {
                        "platform": platform.id,
                        "model": model.id,
                        "channel": best_channel.id,
                        "display_name": "GPT-5",
                        "retail_input_price_per_million": "1.2",
                        "retail_output_price_per_million": "2.4",
                        "is_active": True,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        old_listing = ResaleListing.objects.get(channel=old_channel)
        new_listing = ResaleListing.objects.get(channel=best_channel)
        self.assertTrue(old_listing.is_active)
        self.assertFalse(new_listing.is_active)
        self.assertEqual(
            new_listing.publish_status,
            ResaleListing.PUBLISH_NONE,
        )
        self.assertEqual(
            new_listing.workflow_status,
            ResaleListing.WORKFLOW_PENDING_PUBLISH,
        )
        self.assertEqual(ResaleListingPriceHistory.objects.count(), 1)

    def test_resale_listing_bulk_upsert_allows_channel_after_auto_listing(
        self,
    ):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        ResaleListing.objects.create(
            platform=platform,
            model=model,
            channel=None,
            retail_input_price_per_million="2.0",
            retail_output_price_per_million="4.0",
            is_active=False,
        )

        response = self.client.post(
            reverse("resale-listing-bulk-upsert"),
            {
                "items": [
                    {
                        "platform": platform.id,
                        "model": model.id,
                        "channel": channel.id,
                        "display_name": "GPT-5",
                        "retail_input_price_per_million": "1.2",
                        "retail_output_price_per_million": "2.4",
                        "is_active": True,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        listing = ResaleListing.objects.get(
            platform=platform,
            model=model,
            channel=channel,
        )
        self.assertFalse(listing.is_active)
        self.assertEqual(
            listing.publish_status,
            ResaleListing.PUBLISH_NONE,
        )
        self.assertEqual(
            listing.workflow_status,
            ResaleListing.WORKFLOW_PENDING_PUBLISH,
        )

    def test_resale_listing_bulk_draft_saves_draft_state(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )

        response = self.client.post(
            reverse("resale-listing-bulk-draft"),
            {
                "items": [
                    {
                        "platform": platform.id,
                        "model": model.id,
                        "channel": channel.id,
                        "display_name": "GPT-5",
                        "retail_input_price_per_million": "1.2",
                        "retail_output_price_per_million": "2.4",
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        listing = ResaleListing.objects.get(
            platform=platform,
            model=model,
            channel=channel,
        )
        self.assertFalse(listing.is_active)
        self.assertEqual(listing.publish_status, ResaleListing.PUBLISH_NONE)
        self.assertEqual(
            listing.workflow_status,
            ResaleListing.WORKFLOW_DRAFT,
        )

    def test_resale_listing_bulk_upsert_restores_removed_model(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        ResaleListingExclusion.objects.create(
            platform=platform,
            model=model,
            reason="Hidden",
        )

        response = self.client.post(
            reverse("resale-listing-bulk-upsert"),
            {
                "items": [
                    {
                        "platform": platform.id,
                        "model": model.id,
                        "channel": channel.id,
                        "display_name": "GPT-5",
                        "retail_input_price_per_million": "1.2",
                        "retail_output_price_per_million": "2.4",
                        "is_active": True,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            ResaleListingExclusion.objects.filter(
                platform=platform,
                model=model,
            ).exists()
        )

    def test_resale_listing_bulk_replace_allows_channel_after_auto_listing(
        self,
    ):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        ResaleListing.objects.create(
            platform=platform,
            model=model,
            channel=None,
            retail_input_price_per_million="2.0",
            retail_output_price_per_million="4.0",
            is_active=False,
        )

        response = self.client.post(
            reverse("resale-listing-bulk-replace"),
            {
                "items": [
                    {
                        "platform": platform.id,
                        "model": model.id,
                        "channel": channel.id,
                        "display_name": "GPT-5",
                        "retail_input_price_per_million": "1.2",
                        "retail_output_price_per_million": "2.4",
                        "is_active": True,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        listing = ResaleListing.objects.get(
            platform=platform,
            model=model,
            channel=channel,
        )
        self.assertFalse(listing.is_active)
        self.assertEqual(
            listing.publish_status,
            ResaleListing.PUBLISH_NONE,
        )
        self.assertEqual(
            listing.workflow_status,
            ResaleListing.WORKFLOW_PENDING_PUBLISH,
        )

    def test_resale_listing_exclusion_bulk_upsert_and_restore(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )

        remove_response = self.client.post(
            reverse("resale-listing-exclusion-bulk-upsert"),
            {
                "platform": platform.id,
                "models": [model.id],
                "reason": "Not needed now",
            },
            format="json",
        )

        self.assertEqual(remove_response.status_code, 200)
        self.assertTrue(
            ResaleListingExclusion.objects.filter(
                platform=platform,
                model=model,
                reason="Not needed now",
            ).exists()
        )

        restore_response = self.client.post(
            reverse("resale-listing-exclusion-bulk-restore"),
            {
                "platform": platform.id,
                "models": [model.id],
            },
            format="json",
        )

        self.assertEqual(restore_response.status_code, 200)
        self.assertFalse(
            ResaleListingExclusion.objects.filter(
                platform=platform,
                model=model,
            ).exists()
        )
        actions = list(
            AuditLog.objects.filter(
                target_type="llm_ops.ResaleListingExclusion",
            )
            .order_by("created_at")
            .values_list("action", flat=True)
        )
        self.assertEqual(
            actions,
            [AuditLog.ACTION_CREATE, AuditLog.ACTION_RESTORE],
        )

    def test_resale_listing_bulk_offline_deactivates_selected_models(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        selected_model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        untouched_model = LLMModel.objects.create(
            provider=provider,
            name="GPT-4o",
            code="gpt-4o",
        )
        channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        other_platform = ResalePlatform.objects.create(
            name="Agione Backup",
            code="agione-backup",
        )
        selected_listing = self._create_online_listing(
            platform=platform,
            model=selected_model,
            channel=channel,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )
        untouched_listing = self._create_online_listing(
            platform=platform,
            model=untouched_model,
            channel=channel,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )
        other_platform_listing = self._create_online_listing(
            platform=other_platform,
            model=selected_model,
            channel=channel,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )

        response = self.client.post(
            reverse("resale-listing-bulk-offline"),
            {
                "platform": platform.id,
                "models": [selected_model.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        selected_listing.refresh_from_db()
        untouched_listing.refresh_from_db()
        other_platform_listing.refresh_from_db()
        self.assertFalse(selected_listing.is_active)
        self.assertEqual(
            selected_listing.publish_status,
            ResaleListing.PUBLISH_OFFLINE,
        )
        self.assertEqual(
            selected_listing.workflow_status,
            ResaleListing.WORKFLOW_OFFLINE,
        )
        self.assertTrue(untouched_listing.is_active)
        self.assertTrue(other_platform_listing.is_active)
        self.assertEqual(ResaleListingPriceHistory.objects.count(), 1)

    def test_resale_listing_create_starts_as_draft(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )

        response = self.client.post(
            reverse("resale-listing-list"),
            {
                "platform": platform.id,
                "model": model.id,
                "channel": channel.id,
                "retail_input_price_per_million": "1.2",
                "retail_output_price_per_million": "2.4",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        listing = ResaleListing.objects.get(id=response.data["id"])
        self.assertFalse(listing.is_active)
        self.assertEqual(listing.publish_status, ResaleListing.PUBLISH_NONE)
        self.assertEqual(
            listing.workflow_status,
            ResaleListing.WORKFLOW_DRAFT,
        )

    def test_resale_workflow_config_effective_returns_platform_runtime(self):
        platform, _ = ResalePlatform.objects.update_or_create(
            code="agione",
            defaults={
                "name": "Agione",
                "auto_approve_max_margin_rate": "25.50",
            },
        )

        response = self.client.get(
            reverse("resale-workflow-config-effective"),
            {"platform": platform.id},
        )

        self.assertEqual(response.status_code, 200)
        config = response.data["config"]
        self.assertEqual(response.data["platform"], platform.id)
        self.assertTrue(config["policies"]["auto_approve_enabled"])
        self.assertEqual(
            config["runtime"]["auto_approve_max_margin_rate"],
            25.5,
        )
        self.assertIn(
            "confirm_publish",
            config["runtime"]["transition_actions"],
        )

    def test_resale_workflow_config_effective_persists_edits(self):
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        response = self.client.get(
            reverse("resale-workflow-config-effective"),
            {"platform": platform.id},
        )
        config = response.data["config"]
        config["policies"]["auto_approve_enabled"] = False
        config["nodes"][3]["enabled"] = False

        patch_response = self.client.patch(
            f"{reverse('resale-workflow-config-effective')}"
            f"?platform={platform.id}",
            {"config": config, "notes": "disable auto approval"},
            format="json",
        )

        self.assertEqual(patch_response.status_code, 200)
        saved = ResaleWorkflowConfig.objects.get(platform=platform)
        self.assertFalse(saved.config["policies"]["auto_approve_enabled"])
        self.assertFalse(
            patch_response.data["config"]["policies"]["auto_approve_enabled"]
        )
        self.assertEqual(patch_response.data["notes"], "disable auto approval")
        self.assertIn("runtime", patch_response.data["config"])

    def test_resale_workflow_config_patch_requires_config(self):
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )

        response = self.client.patch(
            f"{reverse('resale-workflow-config-effective')}"
            f"?platform={platform.id}",
            {"notes": "missing config"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "config is required.")
        self.assertFalse(
            ResaleWorkflowConfig.objects.filter(platform=platform).exists()
        )

    def test_resale_workflow_config_rejects_unknown_edge_node(self):
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        payload = {
            "config": {
                "version": 1,
                "policies": {},
                "nodes": [
                    {
                        "id": "start",
                        "label": "Start",
                        "enabled": True,
                    }
                ],
                "edges": [
                    {
                        "id": "bad",
                        "from": "start",
                        "to": "missing",
                        "enabled": True,
                    }
                ],
            }
        }

        response = self.client.patch(
            f"{reverse('resale-workflow-config-effective')}"
            f"?platform={platform.id}",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("unknown node", str(response.data))

    def test_resale_workflow_config_rejects_missing_publish_path(self):
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        response = self.client.get(
            reverse("resale-workflow-config-effective"),
            {"platform": platform.id},
        )
        config = response.data["config"]
        config["policies"]["auto_approve_enabled"] = False
        config["policies"]["manual_confirm_required"] = False
        config["policies"]["feishu_approval_enabled"] = False

        patch_response = self.client.patch(
            f"{reverse('resale-workflow-config-effective')}"
            f"?platform={platform.id}",
            {"config": config},
            format="json",
        )

        self.assertEqual(patch_response.status_code, 400)
        self.assertIn("publishing path", str(patch_response.data))

    def test_resale_listing_bulk_transition_publish_and_offline(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        listing = ResaleListing.objects.create(
            platform=platform,
            model=model,
            channel=channel,
            publish_status=ResaleListing.PUBLISH_NONE,
            workflow_status=ResaleListing.WORKFLOW_PENDING_PUBLISH,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )

        publish_response = self.client.post(
            reverse("resale-listing-bulk-transition"),
            {
                "platform": platform.id,
                "models": [model.id],
                "action": "confirm_publish",
            },
            format="json",
        )

        self.assertEqual(publish_response.status_code, 200)
        listing.refresh_from_db()
        self.assertTrue(listing.is_active)
        self.assertEqual(
            listing.publish_status,
            ResaleListing.PUBLISH_ONLINE,
        )
        self.assertEqual(
            listing.workflow_status,
            ResaleListing.WORKFLOW_ONLINE,
        )
        audit = AuditLog.objects.filter(
            target_type="llm_ops.ResaleListing",
            target_id=str(listing.id),
            action=AuditLog.ACTION_TRANSITION,
            category=AuditLog.CATEGORY_APPROVAL,
        ).latest("created_at")
        self.assertEqual(audit.metadata["workflow_action"], "confirm_publish")

        request_response = self.client.post(
            reverse("resale-listing-bulk-transition"),
            {
                "platform": platform.id,
                "models": [model.id],
                "action": "request_offline",
            },
            format="json",
        )

        self.assertEqual(request_response.status_code, 200)
        listing.refresh_from_db()
        self.assertTrue(listing.is_active)
        self.assertEqual(
            listing.publish_status,
            ResaleListing.PUBLISH_ONLINE,
        )
        self.assertEqual(
            listing.workflow_status,
            ResaleListing.WORKFLOW_PENDING_OFFLINE,
        )

        offline_response = self.client.post(
            reverse("resale-listing-bulk-transition"),
            {
                "platform": platform.id,
                "models": [model.id],
                "action": "confirm_offline",
            },
            format="json",
        )

        self.assertEqual(offline_response.status_code, 200)
        listing.refresh_from_db()
        self.assertFalse(listing.is_active)
        self.assertEqual(
            listing.publish_status,
            ResaleListing.PUBLISH_OFFLINE,
        )
        self.assertEqual(
            listing.workflow_status,
            ResaleListing.WORKFLOW_OFFLINE,
        )

    def test_resale_listing_bulk_transition_rejects_invalid_action(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        self._create_online_listing(
            platform=platform,
            model=model,
            channel=channel,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )

        response = self.client.post(
            reverse("resale-listing-bulk-transition"),
            {
                "platform": platform.id,
                "models": [model.id],
                "action": "confirm_publish",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_resale_listing_bulk_transition_prefers_actionable_listing(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        pending_channel = ProcurementChannel.objects.create(
            name="Pending Channel",
            code="pending-channel",
        )
        online_channel = ProcurementChannel.objects.create(
            name="Online Channel",
            code="online-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        pending_listing = ResaleListing.objects.create(
            platform=platform,
            model=model,
            channel=pending_channel,
            publish_status=ResaleListing.PUBLISH_ONLINE,
            workflow_status=ResaleListing.WORKFLOW_PENDING_UPDATE,
            is_active=True,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )
        self._create_online_listing(
            platform=platform,
            model=model,
            channel=online_channel,
            retail_input_price_per_million="1.3",
            retail_output_price_per_million="2.6",
        )

        response = self.client.post(
            reverse("resale-listing-bulk-transition"),
            {
                "platform": platform.id,
                "models": [model.id],
                "action": "confirm_update",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], pending_listing.id)
        pending_listing.refresh_from_db()
        self.assertEqual(
            pending_listing.workflow_status,
            ResaleListing.WORKFLOW_ONLINE,
        )

    def test_resale_listing_bulk_transition_uses_listing_id(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        draft_channel = ProcurementChannel.objects.create(
            name="Draft Channel",
            code="draft-channel",
        )
        online_channel = ProcurementChannel.objects.create(
            name="Online Channel",
            code="online-channel-listing-id",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        draft_listing = ResaleListing.objects.create(
            platform=platform,
            model=model,
            channel=draft_channel,
            publish_status=ResaleListing.PUBLISH_NONE,
            workflow_status=ResaleListing.WORKFLOW_DRAFT,
            is_active=False,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )
        online_listing = self._create_online_listing(
            platform=platform,
            model=model,
            channel=online_channel,
            retail_input_price_per_million="1.3",
            retail_output_price_per_million="2.6",
        )

        response = self.client.post(
            reverse("resale-listing-bulk-transition"),
            {
                "platform": platform.id,
                "models": [model.id],
                "listings": [draft_listing.id],
                "action": "submit",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], draft_listing.id)
        draft_listing.refresh_from_db()
        online_listing.refresh_from_db()
        self.assertEqual(
            draft_listing.workflow_status,
            ResaleListing.WORKFLOW_PENDING_PUBLISH,
        )
        self.assertEqual(
            online_listing.workflow_status,
            ResaleListing.WORKFLOW_ONLINE,
        )

    def test_resale_listing_bulk_transition_deletes_exact_listing(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        draft_channel = ProcurementChannel.objects.create(
            name="Draft Channel",
            code="draft-channel-delete",
        )
        online_channel = ProcurementChannel.objects.create(
            name="Online Channel",
            code="online-channel-delete",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        draft_listing = ResaleListing.objects.create(
            platform=platform,
            model=model,
            channel=draft_channel,
            publish_status=ResaleListing.PUBLISH_NONE,
            workflow_status=ResaleListing.WORKFLOW_DRAFT,
            is_active=False,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )
        online_listing = self._create_online_listing(
            platform=platform,
            model=model,
            channel=online_channel,
            retail_input_price_per_million="1.3",
            retail_output_price_per_million="2.6",
        )

        response = self.client.post(
            reverse("resale-listing-bulk-transition"),
            {
                "platform": platform.id,
                "listings": [draft_listing.id],
                "action": "delete",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        draft_listing.refresh_from_db()
        online_listing.refresh_from_db()
        self.assertEqual(
            draft_listing.workflow_status,
            ResaleListing.WORKFLOW_DELETED,
        )
        self.assertEqual(
            draft_listing.publish_status,
            ResaleListing.PUBLISH_DELETED,
        )
        self.assertEqual(
            online_listing.workflow_status,
            ResaleListing.WORKFLOW_ONLINE,
        )

    def test_resale_listing_bulk_offline_uses_listing_id(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        first_channel = ProcurementChannel.objects.create(
            name="First Channel",
            code="first-channel-offline",
        )
        second_channel = ProcurementChannel.objects.create(
            name="Second Channel",
            code="second-channel-offline",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        first_listing = self._create_online_listing(
            platform=platform,
            model=model,
            channel=first_channel,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )
        second_listing = self._create_online_listing(
            platform=platform,
            model=model,
            channel=second_channel,
            retail_input_price_per_million="1.3",
            retail_output_price_per_million="2.6",
        )

        response = self.client.post(
            reverse("resale-listing-bulk-offline"),
            {
                "platform": platform.id,
                "listings": [first_listing.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        first_listing.refresh_from_db()
        second_listing.refresh_from_db()
        self.assertEqual(
            first_listing.workflow_status,
            ResaleListing.WORKFLOW_OFFLINE,
        )
        self.assertFalse(first_listing.is_active)
        self.assertEqual(
            second_listing.workflow_status,
            ResaleListing.WORKFLOW_ONLINE,
        )
        self.assertTrue(second_listing.is_active)

    def test_summary_returns_agione_diagnostics(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
            input_price_per_million="1",
            output_price_per_million="2",
        )
        channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        ChannelModelPrice.objects.create(
            channel=channel,
            model=model,
            is_listed=True,
        )
        self._create_online_listing(
            platform=platform,
            model=model,
            channel=channel,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )

        response = self.client.get(reverse("llm-ops-summary"))

        self.assertEqual(response.status_code, 200)
        diagnostic = response.data["agione"]["diagnostics"][0]
        self.assertEqual(diagnostic["status"], "low_coverage")
        self.assertTrue(diagnostic["is_agione_listed"])
        self.assertTrue(diagnostic["has_lowest_listing"])
        self.assertEqual(
            response.data["point_conversion"]["points_per_currency_unit"],
            100.0,
        )

    def test_summary_uses_selected_resale_platform(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
            input_price_per_million="1",
            output_price_per_million="2",
        )
        channel = ProcurementChannel.objects.create(
            name="Best Channel",
            code="best-channel",
        )
        default_platform, _ = ResalePlatform.objects.update_or_create(
            code="agione",
            defaults={"name": "Agione Default"},
        )
        selected_platform = ResalePlatform.objects.create(
            name="Agione Europe",
            code="agione-eu",
            points_per_currency_unit="50",
            service_fee_rate="0.08",
            auto_approve_max_margin_rate="18",
        )
        ChannelModelPrice.objects.create(
            channel=channel,
            model=model,
            is_listed=True,
        )
        self._create_online_listing(
            platform=default_platform,
            model=model,
            channel=channel,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )

        response = self.client.get(
            reverse("llm-ops-summary"),
            {"resale_platform": selected_platform.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["agione"]["platform_id"],
            selected_platform.id,
        )
        self.assertEqual(
            response.data["point_conversion"]["points_per_currency_unit"],
            50.0,
        )
        self.assertEqual(
            response.data["point_conversion"]["service_fee_rate"],
            0.08,
        )
        self.assertEqual(
            response.data["point_conversion"]["auto_approve_max_margin_rate"],
            18.0,
        )
        diagnostic = response.data["agione"]["diagnostics"][0]
        self.assertFalse(diagnostic["is_agione_listed"])
        self.assertEqual(diagnostic["status"], "unlisted")

    def test_summary_converts_cross_currency_channel_options(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
            currency="USD",
            input_price_per_million="1",
            output_price_per_million="1",
        )
        usd_channel = ProcurementChannel.objects.create(
            name="USD Channel",
            code="usd-channel",
            currency="USD",
        )
        cny_channel = ProcurementChannel.objects.create(
            name="CNY Channel",
            code="cny-channel",
            currency="CNY",
        )
        ChannelModelPrice.objects.create(
            channel=usd_channel,
            model=model,
            is_listed=True,
        )
        ChannelModelPrice.objects.create(
            channel=cny_channel,
            model=model,
            is_listed=True,
        )

        response = self.client.get(
            reverse("llm-ops-summary"),
            {"display_currency": "CNY"},
        )

        self.assertEqual(response.status_code, 200)
        row = response.data["procurement"][0]
        self.assertEqual(row["best_channel"]["currency"], "CNY")
        self.assertFalse(row["requires_currency_conversion"])
        self.assertEqual(row["best_channel"]["original_currency"], "CNY")
        usd_option = next(
            item
            for item in row["options"]
            if item["original_currency"] == "USD"
        )
        expected_usd_price = round(
            response.data["currency"]["usd_to_cny_rate"],
            4,
        )
        self.assertEqual(
            usd_option["input_price_per_million"],
            expected_usd_price,
        )
        diagnostic = response.data["agione"]["diagnostics"][0]
        self.assertEqual(diagnostic["status"], "unlisted")
        self.assertEqual(response.data["currency"]["display_currency"], "CNY")

    def test_summary_ignores_agione_listing_for_unlisted_channel_model(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-5",
            code="gpt-5",
        )
        channel = ProcurementChannel.objects.create(
            name="Hidden Channel",
            code="hidden-channel",
        )
        platform, _ = ResalePlatform.objects.get_or_create(
            code="agione",
            defaults={"name": "Agione"},
        )
        ChannelModelPrice.objects.create(
            channel=channel,
            model=model,
            is_listed=False,
        )
        self._create_online_listing(
            platform=platform,
            model=model,
            channel=channel,
            retail_input_price_per_million="1.2",
            retail_output_price_per_million="2.4",
        )

        response = self.client.get(reverse("llm-ops-summary"))

        self.assertEqual(response.status_code, 200)
        diagnostic = response.data["agione"]["diagnostics"][0]
        self.assertEqual(diagnostic["status"], "missing_channel")
        self.assertFalse(diagnostic["is_agione_listed"])
        self.assertEqual(response.data["listings"], [])
