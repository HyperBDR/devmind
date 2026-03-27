"""
Unit tests for cloud_billing Celery tasks: collect_billing_data,
check_alert_for_provider, send_alert_notification.
"""

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.utils import timezone

from cloud_billing.models import (
    CloudProvider,
    BillingData,
    AlertRule,
    AlertRecord,
)
from cloud_billing.tasks import (
    collect_billing_data,
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
            "checked": False,
            "reason": "No active alert rule",
        }
        task_ids = list(
            TaskExecution.objects.filter(
                task_name__startswith=(
                    "cloud_billing.tasks.check_alert_for_provider"
                ),
                task_kwargs__provider_id=cloud_provider.id,
            ).values_list("task_id", flat=True)
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
            cost_threshold=Decimal("100.00"),
            growth_threshold=Decimal("50.00"),
            is_active=True,
            created_by=user,
            updated_by=user,
        )
        result = check_alert_for_provider(cloud_provider.id)
        assert result == {
            "checked": False,
            "reason": "No current billing data",
        }
        task_ids = list(
            TaskExecution.objects.filter(
                task_name__startswith=(
                    "cloud_billing.tasks.check_alert_for_provider"
                ),
                task_kwargs__provider_id=cloud_provider.id,
            ).values_list("task_id", flat=True)
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
            "checked": False,
            "reason": "Provider not found",
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
            cost_threshold=Decimal("10000.00"),
            growth_threshold=Decimal("100.00"),
            is_active=True,
            created_by=user,
            updated_by=user,
        )
        result = check_alert_for_provider(cloud_provider.id)
        assert result["checked"] is True
        assert result["alerted"] is False
        assert "alerts_created" not in result or not result.get(
            "alerts_created", True
        )

    @patch("cloud_billing.tasks.send_alert_notification.delay")
    def test_cost_threshold_triggers_without_previous_billing(
        self,
        mock_send_alert_delay,
        cloud_provider,
        user,
        billing_data,
    ):
        """
        Cost threshold should alert even when there is no previous billing
        record for the current hour.
        """
        AlertRule.objects.create(
            provider=cloud_provider,
            cost_threshold=Decimal("1.00"),
            is_active=True,
            created_by=user,
            updated_by=user,
        )

        result = check_alert_for_provider(cloud_provider.id)

        assert result["checked"] is True
        assert result["alerted"] is True
        assert len(result.get("alerts_created", [])) == 1
        mock_send_alert_delay.assert_called_once()

    @patch("cloud_billing.tasks.send_alert_notification.delay")
    def test_alert_message_includes_provider_notes(
        self,
        mock_send_alert_delay,
        cloud_provider,
        user,
        billing_data,
    ):
        """
        Alert messages should include the provider notes snapshot when present.
        """
        cloud_provider.notes = "默认备注"
        cloud_provider.save(update_fields=["notes"])

        AlertRule.objects.create(
            provider=cloud_provider,
            cost_threshold=Decimal("1.00"),
            is_active=True,
            created_by=user,
            updated_by=user,
        )

        result = check_alert_for_provider(cloud_provider.id)

        assert result["alerted"] is True
        record = AlertRecord.objects.order_by("-created_at").first()
        assert record is not None
        assert "默认备注" in record.alert_message
        mock_send_alert_delay.assert_called_once()

    @patch("cloud_billing.tasks.send_alert_notification.delay")
    @patch("cloud_billing.tasks.get_default_webhook_channel")
    def test_balance_threshold_triggers_alert(
        self,
        mock_get_default_webhook_channel,
        mock_send_alert,
        cloud_provider,
        user,
        billing_data,
        previous_billing_data,
    ):
        """
        Balance threshold alerts should trigger when current balance drops
        below the configured threshold.
        """
        mock_channel = SimpleNamespace(config={"language": "en"})
        mock_get_default_webhook_channel.return_value = (mock_channel, {})
        AlertRule.objects.create(
            provider=cloud_provider,
            balance_threshold=Decimal("550.00"),
            is_active=True,
            created_by=user,
            updated_by=user,
        )

        result = check_alert_for_provider(cloud_provider.id)

        assert result["checked"] is True
        assert result["alerted"] is True
        record = AlertRecord.objects.latest("id")
        assert record.current_balance == Decimal("520.00")
        assert record.balance_threshold == Decimal("550.00")
        assert "remaining balance" in record.alert_message.lower()
        mock_send_alert.assert_called_once_with(record.id)

    @patch("cloud_billing.tasks.send_alert_notification.delay")
    @patch("cloud_billing.tasks.get_default_webhook_channel")
    def test_balance_threshold_alert_includes_notes_for_chinese_channel(
        self,
        mock_get_default_webhook_channel,
        mock_send_alert,
        cloud_provider,
        user,
        billing_data,
        previous_billing_data,
    ):
        mock_channel = SimpleNamespace(config={"language": "zh-hans"})
        mock_get_default_webhook_channel.return_value = (mock_channel, {})
        cloud_provider.provider_type = "baidu"
        cloud_provider.display_name = "百度智能云"
        cloud_provider.config = {
            **(cloud_provider.config or {}),
            "notes": "余额告警测试备注",
        }
        cloud_provider.save(update_fields=["provider_type", "display_name", "config"])

        AlertRule.objects.create(
            provider=cloud_provider,
            balance_threshold=Decimal("550.00"),
            is_active=True,
            created_by=user,
            updated_by=user,
        )

        result = check_alert_for_provider(cloud_provider.id)

        assert result["checked"] is True
        assert result["alerted"] is True
        record = AlertRecord.objects.latest("id")
        assert "备注：余额告警测试备注" in record.alert_message
        assert "账号：" in record.alert_message
        mock_send_alert.assert_called_once_with(record.id)

    @patch("cloud_billing.tasks.send_alert_notification.delay")
    @patch("cloud_billing.tasks.get_email_channel_by_uuid")
    def test_alert_message_uses_configured_email_channel_language(
        self,
        mock_get_email_channel_by_uuid,
        mock_send_alert,
        cloud_provider,
        user,
        billing_data,
        previous_billing_data,
    ):
        mock_channel = SimpleNamespace(config={"language": "zh-hans"})
        mock_get_email_channel_by_uuid.return_value = (mock_channel, {})
        cloud_provider.config = {
            **(cloud_provider.config or {}),
            "notification": {
                "type": "email",
                "channel_uuid": "email-channel-1",
            },
        }
        cloud_provider.save(update_fields=["config"])

        AlertRule.objects.create(
            provider=cloud_provider,
            balance_threshold=Decimal("550.00"),
            is_active=True,
            created_by=user,
            updated_by=user,
        )

        result = check_alert_for_provider(cloud_provider.id)

        assert result["checked"] is True
        assert result["alerted"] is True
        record = AlertRecord.objects.latest("id")
        assert "告警类型：余额阈值告警" in record.alert_message
        mock_send_alert.assert_called_once_with(record.id)

    def test_skipped_when_lock_held(self, cloud_provider):
        """
        When prevent_duplicate_task lock is held for same provider_id,
        task returns skipped payload without running.
        """
        lock_name = f"check_alert_for_provider_{cloud_provider.id}"
        acquire_task_lock(lock_name, timeout=60)
        try:
            result = check_alert_for_provider(cloud_provider.id)
            assert result.get("status") == "skipped"
            assert result.get("reason") in (
                "task_already_running",
                "lock_acquisition_failed",
            )
        finally:
            release_task_lock(lock_name)


@pytest.mark.django_db
class TestCollectBillingData:
    """
    Tests for collect_billing_data task.
    """

    @patch("cloud_billing.tasks.check_alert_for_provider.delay")
    @patch("cloud_billing.tasks.ProviderService")
    @patch("cloud_billing.tasks.TaskTracker.update_task_status")
    @patch("cloud_billing.tasks.TaskTracker.register_task")
    @patch(
        "cloud_billing.tasks.current_task",
        new=SimpleNamespace(request=SimpleNamespace(id="task-1")),
    )
    def test_all_failed_updates_task_as_failure(
        self,
        mock_register_task,
        mock_update_task_status,
        mock_provider_service_class,
        mock_check_alert_delay,
        volcengine_provider,
    ):
        """
        When every provider fails, the Celery task should be marked FAILURE.
        """
        mock_provider_service = MagicMock()
        mock_provider_service.get_billing_info.return_value = {
            "status": "error",
            "error": "Unsupported provider: volcengine",
        }
        mock_provider_service_class.return_value = mock_provider_service

        result = collect_billing_data(user_id=1)

        assert result["total"] == 1
        assert len(result["success"]) == 0
        assert len(result["failed"]) == 1
        assert result["error"].startswith(
            "Billing collection failed for all providers"
        )
        mock_check_alert_delay.assert_not_called()
        mock_update_task_status.assert_called()
        assert (
            mock_update_task_status.call_args.kwargs["status"]
            == TaskStatus.FAILURE
        )
        assert mock_update_task_status.call_args.kwargs["error"].startswith(
            "Billing collection failed for all providers"
        )

    @patch("cloud_billing.tasks.check_alert_for_provider.delay")
    @patch("cloud_billing.tasks.ProviderService")
    def test_partial_success_uses_previous_total_cost_and_updates_balance(
        self,
        mock_provider_service_class,
        mock_check_alert_delay,
        cloud_provider,
    ):
        current_period = timezone.now().strftime("%Y-%m")
        previous_hour = max(timezone.now().hour - 1, 0)
        BillingData.objects.create(
            provider=cloud_provider,
            period=current_period,
            hour=previous_hour,
            total_cost=Decimal("88.88"),
            balance=Decimal("500.00"),
            hourly_cost=Decimal("10.00"),
            currency="USD",
            service_costs={},
            account_id="123456789012",
        )

        mock_provider_service = MagicMock()
        mock_provider_service.get_billing_info.return_value = {
            "status": "partial_success",
            "data": {
                "total_cost": 0.0,
                "balance": 321.45,
                "balance_debug": {"status": "success"},
                "currency": "USD",
                "account_id": "123456789012",
                "cost_status": "error",
                "cost_error": "usageDetails/read denied",
            },
            "error": "usageDetails/read denied",
        }
        mock_provider_service_class.return_value = mock_provider_service

        result = collect_billing_data(provider_id=cloud_provider.id, user_id=1)

        assert len(result["success"]) == 1
        record = BillingData.objects.get(
            provider=cloud_provider,
            account_id="123456789012",
            period=current_period,
            hour=timezone.now().hour,
        )
        assert record.total_cost == Decimal("88.88")
        assert record.balance == Decimal("321.45")
        cloud_provider.refresh_from_db()
        assert cloud_provider.balance == Decimal("321.45")
        assert cloud_provider.balance_currency == "USD"
        mock_check_alert_delay.assert_called_once_with(
            cloud_provider.id,
            cloud_provider.provider_type,
        )

    @patch("cloud_billing.tasks.check_alert_for_provider.delay")
    @patch("cloud_billing.tasks.ProviderService")
    def test_sync_preserves_previous_balance_when_current_balance_missing(
        self,
        mock_provider_service_class,
        mock_check_alert_delay,
        cloud_provider,
    ):
        current_period = timezone.now().strftime("%Y-%m")
        previous_hour = max(timezone.now().hour - 1, 0)
        BillingData.objects.create(
            provider=cloud_provider,
            period=current_period,
            hour=previous_hour,
            total_cost=Decimal("88.88"),
            balance=Decimal("500.00"),
            hourly_cost=Decimal("10.00"),
            currency="USD",
            service_costs={},
            account_id="123456789012",
        )

        mock_provider_service = MagicMock()
        mock_provider_service.get_billing_info.return_value = {
            "status": "success",
            "data": {
                "total_cost": 120.5,
                "balance": None,
                "currency": "USD",
                "account_id": "123456789012",
                "service_costs": {},
            },
        }
        mock_provider_service_class.return_value = mock_provider_service

        result = collect_billing_data(provider_id=cloud_provider.id, user_id=1)

        assert len(result["success"]) == 1
        record = BillingData.objects.get(
            provider=cloud_provider,
            account_id="123456789012",
            period=current_period,
            hour=timezone.now().hour,
        )
        assert record.balance == Decimal("500.00")
        mock_check_alert_delay.assert_called_once_with(
            cloud_provider.id,
            cloud_provider.provider_type,
        )

    @patch("cloud_billing.tasks.check_alert_for_provider.delay")
    @patch("cloud_billing.tasks.ProviderService")
    def test_sync_updates_existing_current_hour_record_with_balance(
        self,
        mock_provider_service_class,
        mock_check_alert_delay,
        cloud_provider,
    ):
        current_period = timezone.now().strftime("%Y-%m")
        current_hour = timezone.now().hour
        BillingData.objects.create(
            provider=cloud_provider,
            period=current_period,
            hour=current_hour,
            total_cost=Decimal("88.88"),
            balance=None,
            hourly_cost=Decimal("10.00"),
            currency="USD",
            service_costs={},
            account_id="123456789012",
        )

        mock_provider_service = MagicMock()
        mock_provider_service.get_billing_info.return_value = {
            "status": "success",
            "data": {
                "total_cost": 120.5,
                "balance": 321.45,
                "currency": "USD",
                "account_id": "123456789012",
                "service_costs": {},
            },
        }
        mock_provider_service_class.return_value = mock_provider_service

        result = collect_billing_data(provider_id=cloud_provider.id, user_id=1)

        assert len(result["success"]) == 1
        record = BillingData.objects.get(
            provider=cloud_provider,
            account_id="123456789012",
            period=current_period,
            hour=current_hour,
        )
        assert record.balance == Decimal("321.45")
        cloud_provider.refresh_from_db()
        assert cloud_provider.balance == Decimal("321.45")
        mock_check_alert_delay.assert_called_once_with(
            cloud_provider.id,
            cloud_provider.provider_type,
        )


@pytest.mark.django_db
class TestSendAlertNotification:
    """Tests for send_alert_notification task."""

    @patch("cloud_billing.tasks.CloudBillingNotificationService")
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

    @patch("cloud_billing.tasks.CloudBillingNotificationService")
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

    @patch("cloud_billing.tasks.CloudBillingNotificationService")
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
