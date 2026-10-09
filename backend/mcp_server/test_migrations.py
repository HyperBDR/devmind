"""Exercise fresh migrations and compatibility with completed legacy ones."""

import importlib
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase

from mcp_server.models import McpOAuthClient, McpRobotCredential

APP = "mcp_server"
NAME = "0001_initial_squashed_0008_mcprobotcredential"
TARGET = (APP, NAME)
MIGRATION = importlib.import_module(f"{APP}.migrations.{NAME}").Migration


class McpMigrationTests(TransactionTestCase):
    def tearDown(self):
        MigrationExecutor(connection).migrate([TARGET])
        super().tearDown()

    def test_only_one_script_creates_final_models_and_rolls_back(self):
        directory = Path(importlib.import_module(APP).__file__).parent
        scripts = list((directory / "migrations").glob("[0-9]*.py"))
        self.assertEqual([path.stem for path in scripts], [NAME])

        executor = MigrationExecutor(connection)
        self.assertEqual(executor.loader.graph.leaf_nodes(APP), [TARGET])
        executor.migrate([(APP, None)])
        self.assertFalse(
            any(
                table.startswith("mcp_")
                for table in connection.introspection.table_names()
            )
        )
        recorder = MigrationRecorder(connection)
        self.assertFalse(recorder.migration_qs.filter(app=APP).exists())

        MigrationExecutor(connection).migrate([TARGET])
        tables = set(connection.introspection.table_names())
        final_models = (
            MigrationExecutor(connection)
            .loader.project_state([TARGET])
            .apps.get_app_config(APP)
            .get_models()
        )
        self.assertEqual(len(list(final_models)), 6)
        for model in (
            MigrationExecutor(connection)
            .loader.project_state([TARGET])
            .apps.get_app_config(APP)
            .get_models()
        ):
            self.assertIn(model._meta.db_table, tables)
        self.assertNotIn("mcp_identity_mappings", tables)

    def test_completed_legacy_migrations_preserve_clients_and_tokens(self):
        user = get_user_model().objects.create_user(username="migration-user")
        client = McpOAuthClient.objects.create(
            client_id="migration-client", metadata={"client_name": "Client"}
        )
        credential = McpRobotCredential.objects.create(
            name="Existing robot",
            user=user,
            token_hash="a" * 64,
            scopes=["quotation:read"],
            issuer="https://devmind.example/",
            resource="https://devmind.example/mcp",
        )
        recorder = MigrationRecorder(connection)
        recorder.migration_qs.filter(app=APP).delete()
        for app, name in MIGRATION.replaces:
            recorder.record_applied(app, name)

        executor = MigrationExecutor(connection)
        self.assertEqual(executor.migration_plan([TARGET]), [])
        executor.migrate([TARGET])
        client.refresh_from_db()
        credential.refresh_from_db()
        self.assertEqual(client.metadata["client_name"], "Client")
        self.assertEqual(credential.user_id, user.pk)
        self.assertEqual(credential.token_hash, "a" * 64)
        self.assertTrue(
            recorder.migration_qs.filter(app=APP, name=NAME).exists()
        )
