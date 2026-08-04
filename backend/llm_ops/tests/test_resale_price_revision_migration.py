from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ResaleListingPriceRevisionMigrationTests(TransactionTestCase):
    migrate_from = ("llm_ops", "0008_performance_indexes")
    migrate_to = (
        "llm_ops",
        "0009_resalelistingpricerevision_" "resalelistingpriceitem_and_more",
    )

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        self.online_listing_id = self._create_listing(
            old_apps,
            suffix="online",
            publish_status="online",
            workflow_status="online",
            is_active=True,
        )
        self.pending_listing_id = self._create_listing(
            old_apps,
            suffix="pending",
            publish_status="online",
            workflow_status="pending_update",
            is_active=True,
        )

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def _create_listing(
        self,
        apps,
        *,
        suffix,
        publish_status,
        workflow_status,
        is_active,
    ):
        Provider = apps.get_model("llm_ops", "LLMProvider")
        MetaModel = apps.get_model("llm_ops", "MetaModel")
        Model = apps.get_model("llm_ops", "LLMModel")
        Channel = apps.get_model("llm_ops", "ProcurementChannel")
        Platform = apps.get_model("llm_ops", "ResalePlatform")
        Listing = apps.get_model("llm_ops", "ResaleListing")

        provider = Provider.objects.create(
            name=f"Provider {suffix}",
            code=f"provider-{suffix}",
        )
        meta_model = MetaModel.objects.create(
            name=f"Model {suffix}",
            code=f"model-{suffix}",
        )
        model = Model.objects.create(
            provider=provider,
            meta_model=meta_model,
            name=f"Model {suffix}",
            code=f"model-{suffix}",
            currency="USD",
        )
        channel = Channel.objects.create(
            name=f"Channel {suffix}",
            code=f"channel-{suffix}",
        )
        platform = Platform.objects.create(
            name=f"Platform {suffix}",
            code=f"platform-{suffix}",
            currency="CNY",
        )
        listing = Listing.objects.create(
            platform=platform,
            model=model,
            meta_model=meta_model,
            channel=channel,
            currency="",
            retail_input_price_per_million=Decimal("1.200000"),
            retail_output_price_per_million=Decimal("2.400000"),
            retail_cache_input_price_per_million=None,
            publish_status=publish_status,
            workflow_status=workflow_status,
            is_active=is_active,
        )
        return listing.id

    def test_backfills_flat_prices_without_changing_listing_state(self):
        Listing = self.apps.get_model("llm_ops", "ResaleListing")
        Revision = self.apps.get_model(
            "llm_ops",
            "ResaleListingPriceRevision",
        )

        online = Listing.objects.get(pk=self.online_listing_id)
        revision = Revision.objects.get(listing=online)
        self.assertEqual(online.publish_status, "online")
        self.assertEqual(online.workflow_status, "online")
        self.assertTrue(online.is_active)
        self.assertEqual(
            online.retail_input_price_per_million,
            Decimal("1.200000"),
        )
        self.assertEqual(revision.status, "approved")
        self.assertEqual(revision.currency, "CNY")
        self.assertEqual(online.current_price_revision_id, revision.id)
        self.assertIsNone(online.pending_price_revision_id)
        self.assertEqual(
            set(revision.items.values_list("dimension", "unit_price")),
            {
                ("text_input", Decimal("1.200000")),
                ("text_output", Decimal("2.400000")),
            },
        )

        pending = Listing.objects.get(pk=self.pending_listing_id)
        pending_revision = Revision.objects.get(
            pk=pending.pending_price_revision_id
        )
        self.assertEqual(pending.publish_status, "online")
        self.assertEqual(pending.workflow_status, "pending_update")
        self.assertTrue(pending.is_active)
        self.assertEqual(pending_revision.status, "submitted")
        current_revision = Revision.objects.get(
            pk=pending.current_price_revision_id
        )
        self.assertEqual(current_revision.status, "approved")
        self.assertEqual(current_revision.version, 1)
        self.assertEqual(pending_revision.version, 2)
        self.assertEqual(
            pending.pending_price_revision_id,
            pending_revision.id,
        )

    def test_reverse_migration_preserves_legacy_flat_values(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        Listing = old_apps.get_model("llm_ops", "ResaleListing")

        online = Listing.objects.get(pk=self.online_listing_id)

        self.assertEqual(online.publish_status, "online")
        self.assertEqual(online.workflow_status, "online")
        self.assertTrue(online.is_active)
        self.assertEqual(
            online.retail_input_price_per_million,
            Decimal("1.200000"),
        )
        self.assertEqual(
            online.retail_output_price_per_million,
            Decimal("2.400000"),
        )
