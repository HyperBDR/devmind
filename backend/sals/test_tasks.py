"""
Tests for SALS Celery tasks.

These tests use Celery's apply() method with eager mode
to test task execution without a running worker.
"""
from unittest.mock import patch, Mock

from django.test import TestCase


class TestSyncIncidentsTask(TestCase):
    """Test sync_incidents task."""

    @patch("sals.services.etl.sync_from_api")
    def test_sync_incidents_full_sync(self, mock_sync):
        """Test sync_incidents calls ETL with full_sync=True."""
        mock_sync.return_value = {"status": "ok", "synced": 100}

        from sals.tasks import sync_incidents

        # Use apply() with args/kwargs to simulate task call
        result = sync_incidents.apply(args=[], kwargs={"full_sync": True, "user_id": None})

        mock_sync.assert_called_once_with(full_sync=True)
        self.assertEqual(result.result["status"], "ok")

    @patch("sals.services.etl.sync_from_api")
    def test_sync_incidents_incremental_sync(self, mock_sync):
        """Test sync_incidents calls ETL with full_sync=False."""
        mock_sync.return_value = {"status": "ok", "synced": 10}

        from sals.tasks import sync_incidents

        result = sync_incidents.apply(args=[], kwargs={"full_sync": False, "user_id": None})

        mock_sync.assert_called_once_with(full_sync=False)

    @patch("sals.services.etl.sync_from_api")
    def test_sync_incidents_error_handling(self, mock_sync):
        """Test sync_incidents handles ETL errors and retries."""
        mock_sync.side_effect = Exception("API Error")

        from sals.tasks import sync_incidents

        result = sync_incidents.apply(args=[], kwargs={"full_sync": True, "user_id": None})

        # With eager mode, retry is simulated and exception is raised
        self.assertIsInstance(result.result, Exception)

    @patch("sals.services.etl.sync_from_api")
    @patch("sals.tasks.TaskTracker")
    def test_sync_incidents_with_task_tracking(self, mock_tracker, mock_sync):
        """Test sync_incidents registers task tracker."""
        mock_sync.return_value = {"status": "ok", "synced": 50}
        mock_tracker.register_task.return_value = None
        mock_tracker.update_task_status.return_value = None

        from sals.tasks import sync_incidents

        result = sync_incidents.apply(
            args=[],
            kwargs={"full_sync": True, "user_id": 1},
        )

        # Verify TaskTracker was called
        mock_tracker.register_task.assert_called()


class TestSyncCompaniesTask(TestCase):
    """Test sync_companies task."""

    @patch("sals.services.etl.sync_companies_from_api")
    def test_sync_companies(self, mock_sync):
        """Test sync_companies calls ETL."""
        mock_sync.return_value = {"status": "ok", "added": 5}

        from sals.tasks import sync_companies

        result = sync_companies.apply(args=[], kwargs={"user_id": None})

        mock_sync.assert_called_once()
        self.assertEqual(result.result["added"], 5)


class TestSyncUsersTask(TestCase):
    """Test sync_users task."""

    @patch("sals.services.etl.sync_users_from_api")
    def test_sync_users(self, mock_sync):
        """Test sync_users calls ETL."""
        mock_sync.return_value = {"status": "ok", "added": 10}

        from sals.tasks import sync_users

        result = sync_users.apply(args=[], kwargs={"user_id": None})

        mock_sync.assert_called_once()
        self.assertEqual(result.result["added"], 10)


class TestTaskModuleConstants(TestCase):
    """Test module-level constants."""

    def test_module_name(self):
        """Test MODULE_NAME constant."""
        from sals.tasks import MODULE_NAME

        self.assertEqual(MODULE_NAME, "sals")

    def test_task_names(self):
        """Test task names are correctly namespaced."""
        from sals.tasks import sync_incidents, sync_companies, sync_users

        self.assertEqual(sync_incidents.name, "sals.tasks.sync_incidents")
        self.assertEqual(sync_companies.name, "sals.tasks.sync_companies")
        self.assertEqual(sync_users.name, "sals.tasks.sync_users")
