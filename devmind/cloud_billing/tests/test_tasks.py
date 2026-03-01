"""
Unit tests for cloud_billing Celery tasks: collect_billing_data,
check_alert_for_provider, send_alert_notification.
"""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User

from cloud_billing.models import (
    CloudProvider,
    BillingData,
    AlertRule,
    AlertRecord,
)
from cloud_billing.tasks import (
    check_alert_for_provider,
    send_alert_notification,
)
from agentcore_task.adapters.django.models import TaskExecution
from agentcore_task.constants import TaskStatus
from agentcore_task.adapters.django.services.lock import (
    acquire_task_lock,
    release_task_lock,
)


@pytest.mark.django_db
class TestCheckAlertForProvider:
    """
    Tests for check_alert_for_provider task.
    """

    def test_no_active_alert_rule_returns_success_and_updates_status(
        self, cloud_provider, user
    ):
        """
        When provider has no active alert rule, task returns early with SUCCESS
        and updates TaskExecution status (no longer stuck in STARTED).
        """
        assert not AlertRule.objects.filter(
            provider=cloud_provider, is_active=True
        ).exists()
        result = check_alert_for_provider(cloud_provider.id)
        assert result == {
            'checked': False,
            'reason': 'No active alert rule',
        }
        task_ids = list(
            TaskExecution.objects.filter(
                task_name='cloud_billing.tasks.check_alert_for_provider',
                task_kwargs__provider_id=cloud_provider.id,
            ).values_list('task_id', flat=True)
        )
        if task_ids:
            te = TaskExecution.objects.get(task_id=task_ids[-1])
            assert te.status == TaskStatus.SUCCESS
            assert te.result == result

    def test_no_current_billing_data_returns_success_and_updates_status(
        self, cloud_provider, user
    ):
        """
        When provider has alert rule but no current billing data, task returns
        early with SUCCESS and updates TaskExecution status.
        """
        AlertRule.objects.create(
            provider=cloud_provider,
            cost_threshold=Decimal('100.00'),
            growth_threshold=Decimal('50.00'),
            is_active=True,
            created_by=user,
            updated_by=user,
        )
        result = check_alert_for_provider(cloud_provider.id)
        assert result == {
            'checked': False,
            'reason': 'No current billing data',
        }
        task_ids = list(
            TaskExecution.objects.filter(
                task_name='cloud_billing.tasks.check_alert_for_provider',
                task_kwargs__provider_id=cloud_provider.id,
            ).values_list('task_id', flat=True)
        )
        if task_ids:
            te = TaskExecution.objects.get(task_id=task_ids[-1])
            assert te.status == TaskStatus.SUCCESS
            assert te.result == result

    def test_provider_not_found_returns_failure(self):
        """
        When provider_id does not exist, task returns failure result.
        """
        result = check_alert_for_provider(999999)
        assert result == {
            'checked': False,
            'reason': 'Provider not found',
        }

    def test_success_no_alert_triggered(
        self, cloud_provider, user, billing_data, previous_billing_data
    ):
        """
        When provider has billing data and alert rule but thresholds not
        exceeded, task returns checked=True, alerted=False.
        """
        AlertRule.objects.create(
            provider=cloud_provider,
            cost_threshold=Decimal('10000.00'),
            growth_threshold=Decimal('100.00'),
            is_active=True,
            created_by=user,
            updated_by=user,
        )
        result = check_alert_for_provider(cloud_provider.id)
        assert result['checked'] is True
        assert result['alerted'] is False
        assert 'alerts_created' not in result or not result.get(
            'alerts_created', True
        )

    def test_skipped_when_lock_held(self, cloud_provider):
        """
        When prevent_duplicate_task lock is held for same provider_id,
        task returns skipped payload without running.
        """
        lock_name = f"check_alert_for_provider_{cloud_provider.id}"
        acquire_task_lock(lock_name, timeout=60)
        try:
            result = check_alert_for_provider(cloud_provider.id)
            assert result.get('status') == 'skipped'
            assert result.get('reason') in (
                'task_already_running',
                'lock_acquisition_failed',
            )
        finally:
            release_task_lock(lock_name)


@pytest.mark.django_db
class TestSendAlertNotification:
    """Tests for send_alert_notification task."""

    @patch(
        "cloud_billing.tasks.CloudBillingNotificationService"
    )
    def test_uses_provider_config_notification_when_set(
        self,
        mock_service_class,
        alert_record,
    ):
        """
        Task reads provider.config['notification'] (type=webhook,
        channel_uuid).
        """
        import uuid
        channel_uuid = uuid.uuid4()
        provider = alert_record.provider
        provider.config = provider.config or {}
        provider.config["notification"] = {
            "type": "webhook",
            "channel_uuid": str(channel_uuid),
        }
        provider.save()

        mock_service = MagicMock()
        mock_service.send_alert.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        send_alert_notification(alert_record.id)

        mock_service.send_alert.assert_called_once()
        call_args = mock_service.send_alert.call_args
        assert call_args[1]["channel_uuid"] == str(channel_uuid)

    @patch(
        "cloud_billing.tasks.CloudBillingNotificationService"
    )
    def test_no_channel_uuid_uses_default_and_succeeds_when_default_exists(
        self,
        mock_service_class,
        alert_record,
    ):
        """
        When provider has no config['notification'], task passes
        channel_uuid=None; notifier default used if default exists.
        """
        mock_service = MagicMock()
        mock_service.send_alert.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        result = send_alert_notification(alert_record.id)

        assert result["success"] is True
        mock_service.send_alert.assert_called_once()
        call_args = mock_service.send_alert.call_args
        assert call_args[1]["channel_uuid"] is None

    @patch(
        "cloud_billing.tasks.CloudBillingNotificationService"
    )
    def test_no_channel_uuid_service_returns_failure_when_no_default(
        self,
        mock_service_class,
        alert_record,
    ):
        """
        When channel_uuid is None and notifier has no default,
        send_alert returns failure; task records failed status.
        """
        mock_service = MagicMock()
        mock_service.send_alert.return_value = {
            "success": False,
            "error": "Webhook config not found or not active",
        }
        mock_service_class.return_value = mock_service

        result = send_alert_notification(alert_record.id)

        assert result["success"] is False
        alert_record.refresh_from_db()
        assert alert_record.webhook_status == "failed"
