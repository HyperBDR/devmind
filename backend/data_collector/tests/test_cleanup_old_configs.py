"""
Tests for cleanup_old_configs management command.
"""
from io import StringIO

from django.contrib.auth.models import User
from django.test import TestCase
from django.core.management import call_command

from data_collector.models import CollectorConfig


class TestCleanupOldConfigsCommand(TestCase):
    """Test cleanup_old_configs command."""

    def setUp(self):
        """Set up test users (one per config due to unique constraint)."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.user2 = User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
        )
        self.user3 = User.objects.create_user(
            username="testuser3",
            email="test3@example.com",
            password="testpass123",
        )

        # Create a config with table_name in auth
        self.config_with_table_name = CollectorConfig.objects.create(
            user=self.user,
            platform="after_sales_incident",
            key="test-config-1",
            value={
                "base_url": "https://example.com",
                "auth": {
                    "username": "test",
                    "password": "test",
                    "table_name": "incident",
                },
            },
            is_enabled=True,
        )

        # Create a config with table_name at top level (different user)
        self.config_with_top_level_table_name = CollectorConfig.objects.create(
            user=self.user2,
            platform="after_sales_incident",
            key="test-config-2",
            value={
                "base_url": "https://example.com",
                "auth": {"username": "test", "password": "test"},
                "table_name": "incident",
            },
            is_enabled=True,
        )

        # Create a config without table_name (different user)
        self.config_without_table_name = CollectorConfig.objects.create(
            user=self.user3,
            platform="after_sales_incident",
            key="test-config-3",
            value={
                "base_url": "https://example.com",
                "auth": {"username": "test", "password": "test"},
            },
            is_enabled=True,
        )

    def test_cleanup_removes_table_name_from_auth(self):
        """Test cleanup removes table_name from auth section."""
        from data_collector.management.commands.cleanup_old_configs import (
            cleanup_after_sales_incident_table_name,
        )

        cleaned = cleanup_after_sales_incident_table_name(dry_run=False)

        # Should clean 2 configs (not the one without table_name)
        self.assertEqual(cleaned, 2)

        # Refresh from DB
        self.config_with_table_name.refresh_from_db()
        self.assertNotIn("table_name", self.config_with_table_name.value["auth"])

    def test_cleanup_removes_top_level_table_name(self):
        """Test cleanup removes table_name from top level of value."""
        from data_collector.management.commands.cleanup_old_configs import (
            cleanup_after_sales_incident_table_name,
        )

        cleanup_after_sales_incident_table_name(dry_run=False)

        self.config_with_top_level_table_name.refresh_from_db()
        self.assertNotIn("table_name", self.config_with_top_level_table_name.value)

    def test_cleanup_does_not_modify_clean_config(self):
        """Test cleanup doesn't modify configs without table_name."""
        from data_collector.management.commands.cleanup_old_configs import (
            cleanup_after_sales_incident_table_name,
        )

        original_value = self.config_without_table_name.value.copy()

        cleanup_after_sales_incident_table_name(dry_run=False)

        self.config_without_table_name.refresh_from_db()
        self.assertEqual(
            self.config_without_table_name.value.get("auth", {}).get("table_name"),
            None,
        )

    def test_cleanup_dry_run_does_not_modify(self):
        """Test dry_run doesn't modify database."""
        from data_collector.management.commands.cleanup_old_configs import (
            cleanup_after_sales_incident_table_name,
        )

        original_value = self.config_with_table_name.value.copy()

        cleaned = cleanup_after_sales_incident_table_name(dry_run=True)

        self.assertEqual(cleaned, 2)

        self.config_with_table_name.refresh_from_db()
        self.assertEqual(self.config_with_table_name.value, original_value)

    def test_command_dry_run_output(self):
        """Test command outputs correct dry run message."""
        output = StringIO()
        call_command("cleanup_old_configs", "--dry-run", stdout=output)

        self.assertIn("DRY RUN", output.getvalue())
        self.assertIn("Would clean 2", output.getvalue())

    def test_command_execute_output(self):
        """Test command outputs correct cleanup message."""
        output = StringIO()
        call_command("cleanup_old_configs", stdout=output)

        self.assertIn("Cleaned 2", output.getvalue())
        self.assertIn("Cleanup completed", output.getvalue())


class TestCleanupWithOtherPlatforms(TestCase):
    """Test cleanup doesn't affect other platform configs."""

    def setUp(self):
        """Set up test user and data."""
        self.user = User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
        )

        # JIRA config with some data
        self.jira_config = CollectorConfig.objects.create(
            user=self.user,
            platform="jira",
            key="jira-config",
            value={
                "base_url": "https://jira.example.com",
                "auth": {"username": "test"},
            },
            is_enabled=True,
        )

        # after_sales_incident config
        self.asi_config = CollectorConfig.objects.create(
            user=self.user,
            platform="after_sales_incident",
            key="asi-config",
            value={
                "base_url": "https://support.example.com",
                "auth": {
                    "username": "test",
                    "password": "test",
                    "table_name": "incident",
                },
            },
            is_enabled=True,
        )

    def test_cleanup_only_affects_after_sales_incident(self):
        """Test cleanup only affects after_sales_incident platform."""
        from data_collector.management.commands.cleanup_old_configs import (
            cleanup_after_sales_incident_table_name,
        )

        cleanup_after_sales_incident_table_name(dry_run=False)

        # JIRA config should be unchanged
        self.jira_config.refresh_from_db()
        self.assertEqual(
            self.jira_config.value["base_url"], "https://jira.example.com"
        )

        # ASI config should have table_name removed
        self.asi_config.refresh_from_db()
        self.assertNotIn("table_name", self.asi_config.value["auth"])
