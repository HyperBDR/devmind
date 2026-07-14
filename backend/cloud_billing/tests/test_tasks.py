"""
Unit tests for cloud_billing Celery tasks: collect_billing_data,
check_alert_for_provider, send_alert_notification.
"""

import datetime
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, call, patch

import pytest

from django.apps import apps
from django.utils import timezone

from agentcore_task.adapters.django.models import TaskExecution
from agentcore_task.adapters.django.services.lock import (
    acquire_task_lock,
    release_task_lock,
)
from agentcore_task.constants import TaskStatus

from cloud_billing.constants import WEBHOOK_STATUS_PENDING
import cloud_billing.tasks as billing_tasks
from cloud_billing.models import (
    AlertRecord,
    AlertRule,
    BillingData,
    RechargeApprovalApproverNotification,
    RechargeApprovalRecord,
)
from cloud_billing.tasks import (
    collect_billing_data,
    check_alert_for_provider,
    send_alert_notification,
    send_recharge_approval_notification,
    submit_recharge_approval,
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

    @patch("cloud_billing.tasks.reconcile_recharge_approvals_for_account")
    def test_reconciles_recharge_fulfillment_from_current_account_health(
        self,
        mock_reconcile,
        cloud_provider,
        user,
        billing_data,
    ):
        AlertRule.objects.create(
            provider=cloud_provider,
            balance_threshold=Decimal("100.00"),
            enable_recharge_recovery_detection=True,
            is_active=True,
            created_by=user,
            updated_by=user,
        )

        result = check_alert_for_provider(cloud_provider.id)

        assert result["checked"] is True
        mock_reconcile.assert_called_once_with(
            provider=cloud_provider,
            recharge_account=billing_data.account_id,
            current_balance=Decimal("520.00"),
            current_days_remaining=None,
            observed_at=ANY,
            allow_provider_fallback=True,
        )

    @patch("cloud_billing.tasks._estimate_days_remaining")
    @patch("cloud_billing.tasks.reconcile_recharge_approvals_for_account")
    def test_reconciles_before_zero_cost_missing_balance_early_return(
        self,
        mock_reconcile,
        mock_estimate_days,
        cloud_provider,
        user,
        billing_data,
    ):
        BillingData.objects.filter(pk=billing_data.pk).update(
            hourly_cost=Decimal("0.00"),
            balance=None,
        )
        AlertRule.objects.create(
            provider=cloud_provider,
            days_remaining_threshold=7,
            enable_recharge_recovery_detection=True,
            is_active=True,
            created_by=user,
            updated_by=user,
        )
        mock_estimate_days.return_value = (Decimal("10.00"), 20)

        result = check_alert_for_provider(cloud_provider.id)

        assert result["checked"] is True
        mock_reconcile.assert_called_once_with(
            provider=cloud_provider,
            recharge_account=billing_data.account_id,
            current_balance=None,
            current_days_remaining=20,
            observed_at=ANY,
            allow_provider_fallback=True,
        )

    @patch("cloud_billing.tasks.reconcile_recharge_approvals_for_account")
    def test_skips_recharge_fulfillment_when_detection_is_disabled(
        self,
        mock_reconcile,
        cloud_provider,
        user,
        billing_data,
    ):
        AlertRule.objects.create(
            provider=cloud_provider,
            balance_threshold=Decimal("100.00"),
            enable_recharge_recovery_detection=False,
            is_active=True,
            created_by=user,
            updated_by=user,
        )

        result = check_alert_for_provider(cloud_provider.id)

        assert result["checked"] is True
        mock_reconcile.assert_not_called()

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
    @patch("cloud_billing.tasks.submit_recharge_approval.delay")
    def test_cost_threshold_does_not_auto_submit_recharge_approval(
        self,
        mock_submit_recharge_approval,
        mock_send_alert_delay,
        cloud_provider,
        user,
        billing_data,
    ):
        """
        Auto recharge approval should only react to balance or days remaining
        alerts, not cost/growth-only alerts.
        """
        cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
        cloud_provider.save(update_fields=["recharge_info"])
        AlertRule.objects.create(
            provider=cloud_provider,
            cost_threshold=Decimal("1.00"),
            auto_submit_recharge_approval=True,
            auto_recharge_amount=Decimal("500.00"),
            is_active=True,
            created_by=user,
            updated_by=user,
        )

        result = check_alert_for_provider(cloud_provider.id)

        assert result["checked"] is True
        assert result["alerted"] is True
        mock_send_alert_delay.assert_called_once()
        mock_submit_recharge_approval.assert_not_called()

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
    def test_alert_message_includes_provider_tags(
        self,
        mock_send_alert_delay,
        cloud_provider,
        user,
        billing_data,
    ):
        """
        Alert messages should include provider tags when present.
        """
        cloud_provider.tags = ["生产", "核心"]
        cloud_provider.save(update_fields=["tags"])

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
        assert "标签：生产、核心" in record.alert_message
        mock_send_alert_delay.assert_called_once()

    @patch("cloud_billing.tasks.send_alert_notification.delay")
    @patch("cloud_billing.tasks.submit_recharge_approval.delay")
    @patch("cloud_billing.tasks.get_default_webhook_channel")
    def test_balance_threshold_triggers_alert(
        self,
        mock_get_default_webhook_channel,
        mock_submit_recharge_approval,
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
        cloud_provider.recharge_info = '{"amount": 288, "recharge_account": "acct-1"}'
        cloud_provider.save(update_fields=["recharge_info"])
        AlertRule.objects.create(
            provider=cloud_provider,
            balance_threshold=Decimal("550.00"),
            auto_submit_recharge_approval=True,
            auto_recharge_amount=Decimal("500.00"),
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
        assert "recharge approval workflow has been triggered" in (
            record.alert_message.lower()
        )
        assert "current progress: creating the approval request" in (
            record.alert_message.lower()
        )
        assert "current approver and node will be sent" in (
            record.alert_message.lower()
        )
        mock_send_alert.assert_called_once_with(record.id)
        mock_submit_recharge_approval.assert_called_once_with(
            cloud_provider.id,
            alert_record_id=record.id,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            billing_account_id=billing_data.account_id,
            amount="500.00",
            currency="USD",
        )

    @patch(
        "cloud_billing.tasks._resolve_current_approver_labels"
    )
    @patch("cloud_billing.tasks.submit_recharge_approval.delay")
    @patch(
        "cloud_billing.tasks."
        "send_pending_recharge_approver_notifications.delay"
    )
    @patch("cloud_billing.tasks.send_alert_notification.delay")
    def test_balance_alert_escalates_the_ongoing_approval(
        self,
        mock_send_alert,
        mock_send_approver_notice,
        mock_submit_recharge,
        mock_resolve_approvers,
        cloud_provider,
        user,
        billing_data,
        previous_billing_data,
    ):
        BillingData.objects.filter(pk=billing_data.pk).update(
            balance=Decimal("40.00")
        )
        cloud_provider.recharge_info = json.dumps(
            {
                "amount": 500,
                "recharge_account": "recharge-account-test",
            }
        )
        cloud_provider.save(update_fields=["recharge_info"])
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            raw_recharge_info=json.dumps(
                {"recharge_account": "recharge-account-test"}
            ),
            context_payload={
                "billing_account_id": billing_data.account_id,
            },
        )
        AlertRule.objects.create(
            provider=cloud_provider,
            balance_threshold=Decimal("100.00"),
            auto_submit_recharge_approval=True,
            auto_recharge_amount=Decimal("500.00"),
            is_active=True,
            created_by=user,
            updated_by=user,
        )
        mock_resolve_approvers.return_value = [
            "Approver A（审批节点 A）"
        ]

        result = check_alert_for_provider(cloud_provider.id)

        assert result["alerted"] is True
        alert_record = AlertRecord.objects.latest("id")
        assert "已有充值审批流程正在进行" in (
            alert_record.alert_message
        )
        assert "当前进度：等待审批" in alert_record.alert_message
        assert "当前审批人：Approver A（审批节点 A）" in (
            alert_record.alert_message
        )
        mock_send_alert.assert_called_once()
        mock_submit_recharge.assert_called_once()
        mock_send_approver_notice.assert_called_once_with(
            record.id,
            notification_key="balance_50",
            escalation_context={
                "level": 50,
                "current_balance": "40.00",
                "balance_threshold": "100.00",
                "balance_ratio": "40.00",
                "currency": "USD",
            },
        )

    @patch(
        "cloud_billing.tasks._resolve_current_approver_labels"
    )
    @patch("cloud_billing.tasks.submit_recharge_approval.delay")
    @patch("cloud_billing.tasks.send_alert_notification.delay")
    @patch("cloud_billing.tasks.get_default_webhook_channel")
    def test_balance_alert_rechecks_approval_after_status_refresh(
        self,
        mock_get_default_webhook_channel,
        mock_send_alert,
        mock_submit_recharge,
        mock_resolve_approvers,
        cloud_provider,
        user,
        billing_data,
        previous_billing_data,
    ):
        """A live terminal approval must not be reported as ongoing."""
        mock_channel = SimpleNamespace(config={"language": "zh-hans"})
        mock_get_default_webhook_channel.return_value = (mock_channel, {})
        cloud_provider.recharge_info = json.dumps(
            {
                "amount": 500,
                "recharge_account": "recharge-account-test",
            }
        )
        cloud_provider.save(update_fields=["recharge_info"])
        approval = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            raw_recharge_info=json.dumps(
                {"recharge_account": "recharge-account-test"}
            ),
            context_payload={
                "billing_account_id": billing_data.account_id,
            },
        )
        AlertRule.objects.create(
            provider=cloud_provider,
            balance_threshold=Decimal("550.00"),
            auto_submit_recharge_approval=True,
            auto_recharge_amount=Decimal("500.00"),
            is_active=True,
            created_by=user,
            updated_by=user,
        )

        def finish_approval(record):
            record.status = RechargeApprovalRecord.STATUS_APPROVED
            record.save(update_fields=["status", "updated_at"])
            return []

        mock_resolve_approvers.side_effect = finish_approval

        result = check_alert_for_provider(cloud_provider.id)

        assert result["alerted"] is True
        alert_record = AlertRecord.objects.latest("id")
        assert "已有充值审批流程正在进行" not in (
            alert_record.alert_message
        )
        assert "正在创建审批单" in alert_record.alert_message
        approval.refresh_from_db()
        assert approval.status == RechargeApprovalRecord.STATUS_APPROVED
        mock_send_alert.assert_called_once_with(alert_record.id)
        mock_submit_recharge.assert_called_once()

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
        cloud_provider.tags = ["预付费", "重点"]
        cloud_provider.config = {
            **(cloud_provider.config or {}),
            "notes": "余额告警测试备注",
        }
        cloud_provider.save(
            update_fields=["provider_type", "display_name", "tags", "config"]
        )

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
        assert "标签：预付费、重点" in record.alert_message
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

    @patch("cloud_billing.tasks.send_alert_notification.delay")
    @patch("cloud_billing.tasks.get_default_webhook_channel")
    def test_days_remaining_threshold_triggers_alert(
        self,
        mock_get_default_webhook_channel,
        mock_send_alert,
        cloud_provider,
        user,
        billing_data,
        previous_billing_data,
    ):
        mock_channel = SimpleNamespace(config={"language": "en"})
        mock_get_default_webhook_channel.return_value = (mock_channel, {})
        now = timezone.now()
        current_day = timezone.localdate(now)
        current_hour = now.hour

        BillingData.objects.filter(pk=billing_data.pk).update(
            period=now.strftime("%Y-%m"),
            day=current_day,
            hour=current_hour,
            collected_at=now,
        )

        for offset in range(1, 7):
            collected_at = now - datetime.timedelta(days=offset)
            collected_day = current_day - datetime.timedelta(days=offset)
            row = BillingData.objects.create(
                provider=cloud_provider,
                period=collected_day.strftime("%Y-%m"),
                day=collected_day,
                hour=current_hour,
                total_cost=Decimal("10.00") * Decimal(7 - offset),
                hourly_cost=Decimal("10.00"),
                balance=Decimal("520.00"),
                currency="USD",
                account_id="123456789012",
            )
            BillingData.objects.filter(pk=row.pk).update(collected_at=collected_at)

        AlertRule.objects.create(
            provider=cloud_provider,
            days_remaining_threshold=200,
            is_active=True,
            created_by=user,
            updated_by=user,
        )

        result = check_alert_for_provider(cloud_provider.id)

        assert result["checked"] is True
        assert result["alerted"] is True
        record = AlertRecord.objects.latest("id")
        assert record.current_days_remaining is not None
        assert record.current_days_remaining < 200
        assert record.days_remaining_threshold == 200
        assert "estimated days remaining" in record.alert_message.lower()
        mock_send_alert.assert_called_once_with(record.id)

    @patch("cloud_billing.tasks.send_alert_notification.delay")
    @patch("cloud_billing.tasks.get_default_webhook_channel")
    def test_days_remaining_threshold_does_not_trigger_without_7_days_history(
        self,
        mock_get_default_webhook_channel,
        mock_send_alert,
        cloud_provider,
        user,
        billing_data,
    ):
        mock_channel = SimpleNamespace(config={"language": "en"})
        mock_get_default_webhook_channel.return_value = (mock_channel, {})
        AlertRule.objects.create(
            provider=cloud_provider,
            days_remaining_threshold=200,
            is_active=True,
            created_by=user,
            updated_by=user,
        )

        result = check_alert_for_provider(cloud_provider.id)

        assert result["checked"] is True
        assert result["alerted"] is False
        assert AlertRecord.objects.count() == 0
        mock_send_alert.assert_not_called()

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

    @patch("cloud_billing.tasks.check_alert_for_provider.delay")
    @patch("cloud_billing.tasks.ProviderService")
    @patch("cloud_billing.tasks.timezone.now")
    def test_sync_keeps_same_hour_snapshots_on_different_days(
        self,
        mock_timezone_now,
        mock_provider_service_class,
        mock_check_alert_delay,
        cloud_provider,
    ):
        first_now = timezone.make_aware(
            datetime.datetime(2026, 4, 6, 8, 0, 0)
        )
        second_now = timezone.make_aware(
            datetime.datetime(2026, 4, 7, 8, 0, 0)
        )

        mock_provider_service = MagicMock()
        mock_provider_service.get_billing_info.side_effect = [
            {
                "status": "success",
                "data": {
                    "total_cost": 22.5,
                    "balance": 100.0,
                    "currency": "CNY",
                    "account_id": "acct-zhipu",
                    "service_costs": {"智谱 AI": 22.5},
                },
            },
            {
                "status": "success",
                "data": {
                    "total_cost": 128.1,
                    "balance": 80.0,
                    "currency": "CNY",
                    "account_id": "acct-zhipu",
                    "service_costs": {"智谱 AI": 128.1},
                },
            },
        ]
        mock_provider_service_class.return_value = mock_provider_service

        mock_timezone_now.return_value = first_now
        collect_billing_data(provider_id=cloud_provider.id, user_id=1)
        mock_timezone_now.return_value = second_now
        collect_billing_data(provider_id=cloud_provider.id, user_id=1)

        rows = list(
            BillingData.objects.filter(
                provider=cloud_provider,
                account_id="acct-zhipu",
                hour=8,
            ).order_by("day")
        )

        assert len(rows) == 2
        assert rows[0].day.isoformat() == "2026-04-06"
        assert rows[0].total_cost == Decimal("22.50")
        assert rows[1].day.isoformat() == "2026-04-07"
        assert rows[1].total_cost == Decimal("128.10")


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

    @patch("cloud_billing.tasks.logger")
    @patch("cloud_billing.tasks.CloudBillingNotificationService")
    def test_channel_config_error_logs_warning_not_error(
        self,
        mock_service_class,
        mock_logger,
        alert_record,
    ):
        """
        Channel configuration failures should not be reported to Sentry as
        application errors.
        """
        mock_service = MagicMock()
        mock_service.send_alert.return_value = {
            "success": False,
            "error": "Channel not found or inactive for channel_uuid",
        }
        mock_service_class.return_value = mock_service

        result = send_alert_notification(alert_record.id)

        assert result["success"] is False
        mock_logger.warning.assert_called()
        mock_logger.error.assert_not_called()


def test_schedules_group_notice_for_detected_balance_recovery(
    monkeypatch,
):
    mock_delay = MagicMock()
    monkeypatch.setattr(
        billing_tasks.send_recharge_approval_notification,
        "delay",
        mock_delay,
    )

    billing_tasks._schedule_recharge_recovery_notifications(
        [
            {
                "record_id": 188,
                "balance_recovery_detected": True,
            },
            {
                "record_id": 189,
                "balance_recovery_detected": False,
            },
        ]
    )

    mock_delay.assert_called_once_with(188, "fulfillment_recovered")


@pytest.mark.django_db
def test_schedules_most_severe_balance_approval_escalation(
    cloud_provider,
    monkeypatch,
):
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
        status=RechargeApprovalRecord.STATUS_SUBMITTED,
        raw_recharge_info='{"recharge_account": "acct-188"}',
    )
    mock_delay = MagicMock()
    monkeypatch.setattr(
        billing_tasks.send_pending_recharge_approver_notifications,
        "delay",
        mock_delay,
    )

    billing_tasks._schedule_balance_approval_escalation(
        provider=cloud_provider,
        recharge_account="acct-188",
        current_balance=Decimal("25.00"),
        balance_threshold=Decimal("100.00"),
        currency="CNY",
    )

    mock_delay.assert_called_once_with(
        record.id,
        notification_key="balance_30",
        escalation_context={
            "level": 30,
            "current_balance": "25.00",
            "balance_threshold": "100.00",
            "balance_ratio": "25.00",
            "currency": "CNY",
        },
    )


@pytest.mark.django_db
def test_schedules_fifty_percent_balance_approval_escalation(
    cloud_provider,
    monkeypatch,
):
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
        status=RechargeApprovalRecord.STATUS_SUBMITTED,
        raw_recharge_info='{"recharge_account": "acct-188"}',
    )
    mock_delay = MagicMock()
    monkeypatch.setattr(
        billing_tasks.send_pending_recharge_approver_notifications,
        "delay",
        mock_delay,
    )

    billing_tasks._schedule_balance_approval_escalation(
        provider=cloud_provider,
        recharge_account="acct-188",
        current_balance=Decimal("40.00"),
        balance_threshold=Decimal("100.00"),
        currency="CNY",
    )

    mock_delay.assert_called_once_with(
        record.id,
        notification_key="balance_50",
        escalation_context={
            "level": 50,
            "current_balance": "40.00",
            "balance_threshold": "100.00",
            "balance_ratio": "40.00",
            "currency": "CNY",
        },
    )


@pytest.mark.django_db
def test_balance_escalation_uses_single_account_fallback(
    cloud_provider,
    monkeypatch,
):
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
        status=RechargeApprovalRecord.STATUS_SUBMITTED,
        raw_recharge_info="",
    )
    mock_delay = MagicMock()
    monkeypatch.setattr(
        billing_tasks.send_pending_recharge_approver_notifications,
        "delay",
        mock_delay,
    )

    billing_tasks._schedule_balance_approval_escalation(
        provider=cloud_provider,
        recharge_account="",
        current_balance=Decimal("40.00"),
        balance_threshold=Decimal("100.00"),
        currency="CNY",
        allow_provider_fallback=True,
    )

    assert mock_delay.call_args.args[0] == record.id


@pytest.mark.django_db
def test_does_not_backfill_fifty_percent_after_thirty_percent_notice(
    cloud_provider,
    monkeypatch,
):
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
        status=RechargeApprovalRecord.STATUS_SUBMITTED,
        raw_recharge_info='{"recharge_account": "acct-188"}',
    )
    RechargeApprovalApproverNotification.objects.create(
        record=record,
        recipient_user_id="user-finance",
        notification_key="balance_30",
        status=RechargeApprovalApproverNotification.STATUS_SENT,
    )
    mock_delay = MagicMock()
    monkeypatch.setattr(
        billing_tasks.send_pending_recharge_approver_notifications,
        "delay",
        mock_delay,
    )

    billing_tasks._schedule_balance_approval_escalation(
        provider=cloud_provider,
        recharge_account="acct-188",
        current_balance=Decimal("40.00"),
        balance_threshold=Decimal("100.00"),
        currency="CNY",
    )

    mock_delay.assert_not_called()


@pytest.mark.django_db
def test_balance_escalation_uses_unrounded_ratio_for_threshold(
    cloud_provider,
    monkeypatch,
):
    RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
        status=RechargeApprovalRecord.STATUS_SUBMITTED,
        raw_recharge_info='{"recharge_account": "acct-188"}',
    )
    mock_delay = MagicMock()
    monkeypatch.setattr(
        billing_tasks.send_pending_recharge_approver_notifications,
        "delay",
        mock_delay,
    )

    billing_tasks._schedule_balance_approval_escalation(
        provider=cloud_provider,
        recharge_account="acct-188",
        current_balance=Decimal("50.004"),
        balance_threshold=Decimal("100.00"),
        currency="CNY",
    )

    mock_delay.assert_not_called()


@pytest.mark.django_db
class TestSendRechargeApprovalNotification:
    """Tests for recharge approval notification fan-out."""

    @patch("cloud_billing.tasks.RechargeApprovalNotificationService")
    def test_copies_notification_to_configured_submitter_user_id(
        self,
        mock_service_class,
        cloud_provider,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            resolved_submitter_user_id="ou_submitter",
        )
        mock_service = MagicMock()
        mock_service.send_recharge_notification.return_value = {
            "success": True,
            "error": None,
        }
        mock_service.send_submitter_copy.return_value = {
            "success": True,
            "skipped": False,
            "recipient_user_id": "ou_submitter",
            "message_id": "om_123",
            "error": None,
        }
        mock_service_class.return_value = mock_service

        result = send_recharge_approval_notification(
            record.id,
            "submitted",
        )

        mock_service.send_recharge_notification.assert_called_once()
        mock_service.send_submitter_copy.assert_called_once_with(
            record,
            "submitted",
        )
        assert result["success"] is True
        assert result["submitter_copy"]["recipient_user_id"] == (
            "ou_submitter"
        )

    @patch("cloud_billing.tasks.RechargeApprovalNotificationService")
    def test_group_notification_includes_current_approver_names(
        self,
        mock_service_class,
        cloud_provider,
        monkeypatch,
    ):
        """Group cards should show live pending approvers and node names."""
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            feishu_instance_code="instance-code",
            feishu_approval_code="approval-code",
        )
        monkeypatch.setattr(
            billing_tasks,
            "get_recharge_approval_progress",
            lambda approval: [
                {
                    "node_name": "审批节点 A",
                    "status": "PENDING",
                    "approver_names": ["Approver A"],
                },
                {
                    "node_name": "审批节点 B",
                    "status": "PENDING",
                    "approver_names": ["Approver B"],
                },
            ],
        )
        mock_service = MagicMock()
        mock_service.send_recharge_notification.return_value = {
            "success": True,
            "error": None,
        }
        mock_service.send_submitter_copy.return_value = {
            "success": True,
            "error": None,
        }
        mock_service_class.return_value = mock_service

        send_recharge_approval_notification(record.id, "submitted")

        assert mock_service.send_recharge_notification.call_args.kwargs[
            "current_approvers"
        ] == [
            "Approver A（审批节点 A）",
            "Approver B（审批节点 B）",
        ]

    @patch("cloud_billing.tasks.RechargeApprovalNotificationService")
    def test_balance_recovery_notifies_group_without_submitter_copy(
        self,
        mock_service_class,
        cloud_provider,
        monkeypatch,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            feishu_instance_code="instance-recovered",
            feishu_approval_code="approval-recovered",
            fulfillment_status=(
                RechargeApprovalRecord.FULFILLMENT_RECOVERED
            ),
            fulfillment_evidence={
                "estimated_recharge_amount": "420.00",
            },
        )
        mock_refresh = MagicMock(
            return_value={"is_ongoing": True}
        )
        monkeypatch.setattr(
            billing_tasks,
            "refresh_recharge_approval_record_status",
            mock_refresh,
            raising=False,
        )
        monkeypatch.setattr(
            billing_tasks,
            "_resolve_current_approver_labels",
            lambda approval: ["Approver A（审批节点 A）"],
        )
        mock_service = mock_service_class.return_value
        mock_service.send_recharge_notification.return_value = {
            "success": True,
            "error": None,
        }

        result = send_recharge_approval_notification(
            record.id,
            "fulfillment_recovered",
        )

        mock_refresh.assert_called_once_with(record)
        mock_service.send_recharge_notification.assert_called_once_with(
            record=record,
            notification_type="fulfillment_recovered",
            channel_uuid=None,
            channel_type="webhook",
            current_approvers=["Approver A（审批节点 A）"],
        )
        mock_service.send_submitter_copy.assert_not_called()
        assert result["success"] is True
        assert result["submitter_copy"]["skipped"] is True

    @patch("cloud_billing.tasks.RechargeApprovalNotificationService")
    def test_skips_stale_submitted_notice_after_terminal_refresh(
        self,
        mock_service_class,
        cloud_provider,
        monkeypatch,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            feishu_instance_code="instance-finished",
            feishu_approval_code="approval-finished",
        )

        def finish_approval(approval):
            approval.status = RechargeApprovalRecord.STATUS_APPROVED
            return []

        monkeypatch.setattr(
            billing_tasks,
            "_resolve_current_approver_labels",
            finish_approval,
        )

        result = send_recharge_approval_notification(
            record.id,
            "submitted",
        )

        assert result["success"] is True
        assert result["skipped"] is True
        assert result["reason"] == "stale_submitted_notification"
        mock_service_class.assert_not_called()

    @patch("cloud_billing.tasks.RechargeApprovalNotificationService")
    def test_still_copies_to_submitter_when_channel_delivery_raises(
        self,
        mock_service_class,
        cloud_provider,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            resolved_submitter_user_id="ou_submitter",
        )
        mock_service = MagicMock()
        mock_service.send_recharge_notification.side_effect = RuntimeError(
            "invalid channel config"
        )
        mock_service.send_submitter_copy.return_value = {
            "success": True,
            "skipped": False,
            "recipient_user_id": "ou_submitter",
            "message_id": "om_123",
            "error": None,
        }
        mock_service_class.return_value = mock_service

        result = send_recharge_approval_notification(
            record.id,
            "submitted",
        )

        mock_service.send_submitter_copy.assert_called_once_with(
            record,
            "submitted",
        )
        assert result["success"] is False
        assert result["submitter_copy"]["success"] is True
        assert result["channel_notification"]["error"] == (
            "invalid channel config"
        )

    @patch("cloud_billing.tasks.RechargeApprovalNotificationService")
    def test_schedules_submitter_only_retry_after_delivery_failure(
        self,
        mock_service_class,
        cloud_provider,
        monkeypatch,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            resolved_submitter_user_id="user-submitter",
        )
        mock_service = MagicMock()
        mock_service.send_recharge_notification.return_value = {
            "success": True,
            "error": None,
        }
        mock_service.send_submitter_copy.return_value = {
            "success": False,
            "error": "Feishu connection reset",
        }
        mock_service_class.return_value = mock_service
        mock_retry = MagicMock()
        monkeypatch.setattr(
            billing_tasks,
            "send_recharge_approval_submitter_copy",
            SimpleNamespace(apply_async=mock_retry),
            raising=False,
        )

        result = send_recharge_approval_notification(
            record.id,
            "submitted",
        )

        assert result["channel_notification"]["success"] is True
        assert result["submitter_copy"]["success"] is False
        mock_retry.assert_called_once_with(
            args=[record.id, "submitted"],
            kwargs={"attempt": 1},
            countdown=60,
        )

    @patch("cloud_billing.tasks.RechargeApprovalNotificationService")
    def test_submitter_retry_skips_stale_submitted_notification(
        self,
        mock_service_class,
        cloud_provider,
        monkeypatch,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            resolved_submitter_user_id="user-submitter",
        )

        def finish_approval(approval):
            approval.status = RechargeApprovalRecord.STATUS_APPROVED
            return {"is_ongoing": False}

        monkeypatch.setattr(
            billing_tasks,
            "refresh_recharge_approval_record_status",
            finish_approval,
        )

        result = billing_tasks.send_recharge_approval_submitter_copy(
            record.id,
            "submitted",
        )

        assert result["success"] is True
        assert result["skipped"] is True
        assert result["reason"] == "stale_submitted_notification"
        mock_service_class.assert_not_called()


@pytest.mark.django_db
class TestSendPendingRechargeApproverNotifications:
    """Tests for node-aware approver reminders and recipient deduplication."""

    @patch("cloud_billing.tasks.RechargeApprovalNotificationService")
    def test_notifies_each_approver_only_once(
        self,
        mock_service_class,
        cloud_provider,
        monkeypatch,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            feishu_instance_code="instance-188",
            feishu_approval_code="approval-188",
        )
        monkeypatch.setattr(
            billing_tasks,
            "get_pending_recharge_approval_targets",
            lambda approval: [
                {
                    "user_id": "user-finance",
                    "node_id": "node-finance",
                    "node_name": "财务审批",
                    "task_id": "task-188",
                }
            ],
            raising=False,
        )
        mock_service = MagicMock()
        mock_service.send_approver_reminder.return_value = {
            "success": True,
            "recipient_user_id": "user-finance",
            "message_id": "message-188",
            "error": None,
        }
        mock_service_class.return_value = mock_service
        mock_retry = MagicMock()
        monkeypatch.setattr(
            billing_tasks.send_pending_recharge_approver_notifications,
            "apply_async",
            mock_retry,
        )

        first = billing_tasks.send_pending_recharge_approver_notifications(
            record.id
        )
        second = billing_tasks.send_pending_recharge_approver_notifications(
            record.id
        )

        delivery_model = apps.get_model(
            "cloud_billing",
            "RechargeApprovalApproverNotification",
        )
        delivery = delivery_model.objects.get(
            record=record,
            recipient_user_id="user-finance",
        )
        mock_service.send_approver_reminder.assert_called_once_with(
            record,
            recipient_user_id="user-finance",
            node_name="财务审批",
        )
        assert first["notified"] == 1
        assert second["skipped"] == 1
        assert delivery.status == "sent"
        assert delivery.message_id == "message-188"
        mock_retry.assert_called_once_with(
            args=[record.id],
            countdown=(
                billing_tasks.APPROVER_NOTIFICATION_LEASE_SECONDS
            ),
        )

    @patch("cloud_billing.tasks.RechargeApprovalNotificationService")
    def test_notifies_once_for_each_balance_escalation_level(
        self,
        mock_service_class,
        cloud_provider,
        monkeypatch,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            feishu_instance_code="instance-escalation",
            feishu_approval_code="approval-escalation",
        )
        target = {
            "user_id": "user-finance",
            "node_id": "node-finance",
            "node_name": "财务审批",
            "task_id": "task-escalation",
        }
        monkeypatch.setattr(
            billing_tasks,
            "get_pending_recharge_approval_targets",
            lambda approval: [target],
        )
        monkeypatch.setattr(
            billing_tasks.send_pending_recharge_approver_notifications,
            "apply_async",
            MagicMock(),
        )
        mock_service = mock_service_class.return_value
        mock_service.send_approver_reminder.return_value = {
            "success": True,
            "message_id": "message-escalation",
            "error": None,
        }
        escalation_context = {
            "level": 50,
            "current_balance": "40.00",
            "balance_threshold": "100.00",
            "balance_ratio": "40.00",
            "currency": "CNY",
        }

        regular = (
            billing_tasks.send_pending_recharge_approver_notifications(
                record.id
            )
        )
        escalated = (
            billing_tasks.send_pending_recharge_approver_notifications(
                record.id,
                notification_key="balance_50",
                escalation_context=escalation_context,
            )
        )
        repeated = (
            billing_tasks.send_pending_recharge_approver_notifications(
                record.id,
                notification_key="balance_50",
                escalation_context=escalation_context,
            )
        )

        delivery_model = apps.get_model(
            "cloud_billing",
            "RechargeApprovalApproverNotification",
        )
        assert regular["notified"] == 1
        assert escalated["notified"] == 1
        assert repeated["skipped"] == 1
        assert delivery_model.objects.filter(record=record).count() == 2
        assert set(
            delivery_model.objects.filter(record=record).values_list(
                "notification_key",
                flat=True,
            )
        ) == {"pending", "balance_50"}
        assert mock_service.send_approver_reminder.call_count == 2
        mock_service.send_approver_reminder.assert_has_calls(
            [
                call(
                    record,
                    recipient_user_id="user-finance",
                    node_name="财务审批",
                ),
                call(
                    record,
                    recipient_user_id="user-finance",
                    node_name="财务审批",
                    escalation_context=escalation_context,
                ),
            ]
        )

    @patch("cloud_billing.tasks.RechargeApprovalNotificationService")
    def test_escalation_discovery_retry_preserves_balance_context(
        self,
        mock_service_class,
        cloud_provider,
        monkeypatch,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            feishu_instance_code="instance-escalation-discovery",
            feishu_approval_code="approval-escalation-discovery",
        )
        monkeypatch.setattr(
            billing_tasks,
            "get_pending_recharge_approval_targets",
            lambda approval: [],
        )
        mock_retry = MagicMock()
        monkeypatch.setattr(
            billing_tasks.send_pending_recharge_approver_notifications,
            "apply_async",
            mock_retry,
        )
        escalation_context = {
            "level": 30,
            "current_balance": "25.00",
            "balance_threshold": "100.00",
            "balance_ratio": "25.00",
            "currency": "CNY",
        }

        result = (
            billing_tasks.send_pending_recharge_approver_notifications(
                record.id,
                notification_key="balance_30",
                escalation_context=escalation_context,
            )
        )

        assert result["retry_scheduled"] is True
        mock_retry.assert_called_once_with(
            args=[record.id],
            kwargs={
                "discovery_attempt": 1,
                "notification_key": "balance_30",
                "escalation_context": escalation_context,
            },
            countdown=10,
        )

    @patch("cloud_billing.tasks.RechargeApprovalNotificationService")
    def test_escalation_delivery_retries_preserve_balance_context(
        self,
        mock_service_class,
        cloud_provider,
        monkeypatch,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            feishu_instance_code="instance-escalation-retry",
            feishu_approval_code="approval-escalation-retry",
        )
        monkeypatch.setattr(
            billing_tasks,
            "get_pending_recharge_approval_targets",
            lambda approval: [
                {
                    "user_id": "user-finance",
                    "node_id": "node-finance",
                    "node_name": "财务审批",
                    "task_id": "task-escalation-retry",
                }
            ],
        )
        mock_service = mock_service_class.return_value
        mock_service.send_approver_reminder.return_value = {
            "success": False,
            "message_id": "",
            "error": "Feishu connection reset",
        }
        mock_retry = MagicMock()
        monkeypatch.setattr(
            billing_tasks.send_pending_recharge_approver_notifications,
            "apply_async",
            mock_retry,
        )
        escalation_context = {
            "level": 50,
            "current_balance": "40.00",
            "balance_threshold": "100.00",
            "balance_ratio": "40.00",
            "currency": "CNY",
        }
        retry_kwargs = {
            "notification_key": "balance_50",
            "escalation_context": escalation_context,
        }

        result = (
            billing_tasks.send_pending_recharge_approver_notifications(
                record.id,
                **retry_kwargs,
            )
        )

        assert result["failed"] == 1
        assert result["retry_scheduled"] is True
        assert mock_retry.call_args_list == [
            call(
                args=[record.id],
                kwargs=retry_kwargs,
                countdown=(
                    billing_tasks.APPROVER_NOTIFICATION_LEASE_SECONDS
                ),
            ),
            call(
                args=[record.id],
                kwargs=retry_kwargs,
                countdown=(
                    billing_tasks.APPROVER_NOTIFICATION_RETRY_BASE_SECONDS
                ),
            ),
        ]

    @patch("cloud_billing.tasks.RechargeApprovalNotificationService")
    def test_retries_when_live_instance_has_no_approver_targets_yet(
        self,
        mock_service_class,
        cloud_provider,
        monkeypatch,
    ):
        """A newly created instance may not expose task_list immediately."""
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            feishu_instance_code="instance-eventual",
            feishu_approval_code="approval-eventual",
        )
        monkeypatch.setattr(
            billing_tasks,
            "get_pending_recharge_approval_targets",
            lambda approval: [],
        )
        mock_retry = MagicMock()
        monkeypatch.setattr(
            billing_tasks.send_pending_recharge_approver_notifications,
            "apply_async",
            mock_retry,
        )

        result = billing_tasks.send_pending_recharge_approver_notifications(
            record.id,
        )

        assert result["targets"] == 0
        assert result["retry_scheduled"] is True
        mock_retry.assert_called_once_with(
            args=[record.id],
            kwargs={"discovery_attempt": 1},
            countdown=10,
        )

    @patch("cloud_billing.tasks.RechargeApprovalNotificationService")
    def test_retries_after_an_unexpected_delivery_error(
        self,
        mock_service_class,
        cloud_provider,
        monkeypatch,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            feishu_instance_code="instance-retry",
            feishu_approval_code="approval-retry",
        )
        monkeypatch.setattr(
            billing_tasks,
            "get_pending_recharge_approval_targets",
            lambda approval: [
                {
                    "user_id": "user-finance",
                    "node_id": "node-finance",
                    "node_name": "财务审批",
                    "task_id": "task-retry",
                }
            ],
            raising=False,
        )
        mock_service = MagicMock()
        mock_service.send_approver_reminder.side_effect = [
            RuntimeError("Feishu connection reset"),
            {
                "success": True,
                "recipient_user_id": "user-finance",
                "message_id": "message-retry",
                "error": None,
            },
        ]
        mock_service_class.return_value = mock_service
        mock_retry = MagicMock()
        monkeypatch.setattr(
            billing_tasks.send_pending_recharge_approver_notifications,
            "apply_async",
            mock_retry,
        )

        first = billing_tasks.send_pending_recharge_approver_notifications(
            record.id
        )
        second = billing_tasks.send_pending_recharge_approver_notifications(
            record.id
        )
        third = billing_tasks.send_pending_recharge_approver_notifications(
            record.id
        )

        delivery_model = apps.get_model(
            "cloud_billing",
            "RechargeApprovalApproverNotification",
        )
        delivery = delivery_model.objects.get(
            record=record,
            recipient_user_id="user-finance",
        )
        assert first["failed"] == 1
        assert [
            item.kwargs["countdown"]
            for item in mock_retry.call_args_list
        ] == [300, 60, 300]
        assert second["notified"] == 1
        assert third["skipped"] == 1
        assert mock_service.send_approver_reminder.call_count == 2
        assert delivery.status == "sent"
        assert delivery.attempt_count == 2
        assert delivery.message_id == "message-retry"

    @patch("cloud_billing.tasks.RechargeApprovalNotificationService")
    def test_reclaims_a_stale_sending_notification(
        self,
        mock_service_class,
        cloud_provider,
        monkeypatch,
    ):
        """A worker interruption must not leave a permanent sending claim."""
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            feishu_instance_code="instance-stale",
            feishu_approval_code="approval-stale",
        )
        target = {
            "user_id": "user-finance",
            "node_id": "node-finance",
            "node_name": "财务审批",
            "task_id": "task-stale",
        }
        monkeypatch.setattr(
            billing_tasks,
            "get_pending_recharge_approval_targets",
            lambda approval: [target],
        )
        delivery_model = apps.get_model(
            "cloud_billing",
            "RechargeApprovalApproverNotification",
        )
        delivery = delivery_model.objects.create(
            record=record,
            recipient_user_id="user-finance",
            node_id="node-finance",
            node_name="财务审批",
            task_id="task-stale",
            status="sending",
            attempt_count=1,
        )
        delivery_model.objects.filter(pk=delivery.pk).update(
            updated_at=(
                timezone.now() - datetime.timedelta(minutes=10)
            )
        )
        mock_service = MagicMock()
        mock_service.send_approver_reminder.return_value = {
            "success": True,
            "message_id": "message-stale",
            "error": None,
        }
        mock_service_class.return_value = mock_service

        result = billing_tasks.send_pending_recharge_approver_notifications(
            record.id
        )

        delivery.refresh_from_db()
        assert result["notified"] == 1
        assert delivery.status == "sent"
        assert delivery.attempt_count == 2

    @patch("cloud_billing.tasks.RechargeApprovalNotificationService")
    def test_stops_retrying_stale_sending_notification_at_limit(
        self,
        mock_service_class,
        cloud_provider,
        monkeypatch,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            feishu_instance_code="instance-attempt-limit",
            feishu_approval_code="approval-attempt-limit",
        )
        target = {
            "user_id": "user-finance",
            "node_id": "node-finance",
            "node_name": "财务审批",
            "task_id": "task-attempt-limit",
        }
        monkeypatch.setattr(
            billing_tasks,
            "get_pending_recharge_approval_targets",
            lambda approval: [target],
        )
        delivery = (
            RechargeApprovalApproverNotification.objects.create(
                record=record,
                recipient_user_id="user-finance",
                node_id="node-finance",
                node_name="财务审批",
                task_id="task-attempt-limit",
                status=(
                    RechargeApprovalApproverNotification.STATUS_SENDING
                ),
                attempt_count=(
                    billing_tasks.APPROVER_NOTIFICATION_MAX_ATTEMPTS
                ),
            )
        )
        RechargeApprovalApproverNotification.objects.filter(
            pk=delivery.pk
        ).update(
            updated_at=(
                timezone.now() - datetime.timedelta(minutes=10)
            )
        )
        mock_retry = MagicMock()
        monkeypatch.setattr(
            billing_tasks.send_pending_recharge_approver_notifications,
            "apply_async",
            mock_retry,
        )

        result = (
            billing_tasks.send_pending_recharge_approver_notifications(
                record.id
            )
        )

        delivery.refresh_from_db()
        assert result["skipped"] == 1
        assert result.get("retry_scheduled") is not True
        assert delivery.status == (
            RechargeApprovalApproverNotification.STATUS_FAILED
        )
        assert delivery.attempt_count == (
            billing_tasks.APPROVER_NOTIFICATION_MAX_ATTEMPTS
        )
        mock_retry.assert_not_called()
        (
            mock_service_class.return_value.send_approver_reminder
            .assert_not_called()
        )

    @patch("cloud_billing.tasks.RechargeApprovalNotificationService")
    def test_retries_after_an_active_sending_lease_expires(
        self,
        mock_service_class,
        cloud_provider,
        monkeypatch,
    ):
        """A quick Celery redelivery must revisit an active lease later."""
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            feishu_instance_code="instance-active-lease",
            feishu_approval_code="approval-active-lease",
        )
        target = {
            "user_id": "user-finance",
            "node_id": "node-finance",
            "node_name": "财务审批",
            "task_id": "task-active-lease",
        }
        monkeypatch.setattr(
            billing_tasks,
            "get_pending_recharge_approval_targets",
            lambda approval: [target],
        )
        delivery_model = apps.get_model(
            "cloud_billing",
            "RechargeApprovalApproverNotification",
        )
        delivery_model.objects.create(
            record=record,
            recipient_user_id="user-finance",
            node_id="node-finance",
            node_name="财务审批",
            task_id="task-active-lease",
            status="sending",
            attempt_count=1,
        )
        mock_retry = MagicMock()
        monkeypatch.setattr(
            billing_tasks.send_pending_recharge_approver_notifications,
            "apply_async",
            mock_retry,
        )

        result = billing_tasks.send_pending_recharge_approver_notifications(
            record.id
        )

        assert result["skipped"] == 1
        assert result["retry_scheduled"] is True
        assert result["retry_countdown"] == (
            billing_tasks.APPROVER_NOTIFICATION_LEASE_SECONDS
        )
        mock_retry.assert_called_once_with(
            args=[record.id],
            countdown=(
                billing_tasks.APPROVER_NOTIFICATION_LEASE_SECONDS
            ),
        )
        (
            mock_service_class.return_value.send_approver_reminder
            .assert_not_called()
        )


@pytest.mark.django_db
class TestSubmitRechargeApproval:
    """Tests for submit_recharge_approval task."""

    @patch("cloud_billing.tasks.execute_recharge_approval_agent")
    @patch(
        "cloud_billing.tasks.current_task",
        new=SimpleNamespace(request=SimpleNamespace(id="approval-task-logs")),
    )
    def test_submit_recharge_approval_records_detailed_task_logs(
        self,
        mock_execute_agent,
        cloud_provider,
    ):
        """
        TaskExecution metadata should include detailed recharge approval steps.
        """
        cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
        cloud_provider.save(update_fields=["recharge_info"])
        feishu_request_payload = {
            "approval_code": "approval_188",
            "user_id": "ou_submitter_188",
            "form": json.dumps(
                [
                    {
                        "id": "f_remark",
                        "type": "input",
                        "value": (
                            "示例业务备注\n"
                            "户名：示例收款方有限公司\n"
                            "账号：0000000000000000000"
                        ),
                    }
                ],
                ensure_ascii=False,
            ),
        }
        mock_execute_agent.return_value = {
            "request_payload": {"amount": 188, "recharge_account": "acct-188"},
            "feishu_request_payload": feishu_request_payload,
            "submission_payload": {"ok": True},
            "submitter_identifier": "",
            "resolved_submitter_user_id": "",
            "submitter_user_label": "",
            "instance_code": "ins_188",
            "approval_code": "approval_188",
            "status": "PENDING",
            "success": True,
            "summary": "submitted",
        }

        result = submit_recharge_approval(
            cloud_provider.id,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
        )

        assert result["success"] is True
        execution = TaskExecution.objects.get(task_id="approval-task-logs")
        logs = execution.metadata["logs"]
        messages = [item["message"] for item in logs]
        assert any("Starting recharge approval submission" in item for item in messages)
        assert any("Loaded provider" in item for item in messages)
        assert any("Created recharge approval record" in item for item in messages)
        assert any("Executing recharge approval agent" in item for item in messages)
        assert any("Recharge approval agent completed successfully" in item for item in messages)
        assert any(
            "Feishu approval instance create request payload" in item
            and "***REDACTED***" in item
            and "示例收款方有限公司" not in item
            and "0000000000000000000" not in item
            for item in messages
        )
        assert (
            execution.metadata["feishu_request_payload"]["form"][0]["value"]
            == "***REDACTED***"
        )
        assert (
            execution.metadata["feishu_request_payload_redacted"]["form"][0][
                "value"
            ]
            == "***REDACTED***"
        )
        assert execution.metadata["log_summary"]["total"] >= 5

    @patch(
        "cloud_billing.tasks."
        "send_pending_recharge_approver_notifications.delay"
    )
    @patch("cloud_billing.tasks.execute_recharge_approval_agent")
    def test_submit_recharge_approval_creates_record(
        self,
        mock_execute_agent,
        mock_approver_notification_delay,
        cloud_provider,
    ):
        """
        Task should create a recharge approval record for manual submissions.
        """
        cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
        cloud_provider.save(update_fields=["recharge_info"])
        mock_execute_agent.return_value = {
            "request_payload": {"amount": 188, "recharge_account": "acct-188"},
            "submission_payload": {"ok": True},
            "submitter_identifier": "",
            "resolved_submitter_user_id": "",
            "submitter_user_label": "",
            "instance_code": "ins_188",
            "approval_code": "approval_188",
            "status": "PENDING",
            "success": True,
            "summary": "submitted",
        }

        result = submit_recharge_approval(
            cloud_provider.id,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
        )

        assert result["success"] is True
        record = RechargeApprovalRecord.objects.get(
            feishu_instance_code="ins_188"
        )
        assert record.provider == cloud_provider
        assert record.status == RechargeApprovalRecord.STATUS_SUBMITTED
        assert record.trigger_source == RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL
        mock_approver_notification_delay.assert_called_once_with(record.id)

    @patch("cloud_billing.tasks.execute_recharge_approval_agent")
    def test_submit_recharge_approval_defaults_alert_expected_date_to_three_days(
        self,
        mock_execute_agent,
        cloud_provider,
        monkeypatch,
    ):
        """
        Alert-triggered submissions should default expected_date to three days out.
        """
        cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
        cloud_provider.save(update_fields=["recharge_info"])
        monkeypatch.setattr(
            timezone,
            "localdate",
            lambda: datetime.date(2026, 4, 22),
        )
        mock_execute_agent.return_value = {
            "request_payload": {"amount": 188, "recharge_account": "acct-188"},
            "submission_payload": {"ok": True},
            "submitter_identifier": "",
            "resolved_submitter_user_id": "",
            "submitter_user_label": "",
            "instance_code": "ins_188",
            "approval_code": "approval_188",
            "status": "PENDING",
            "success": True,
            "summary": "submitted",
        }

        result = submit_recharge_approval(
            cloud_provider.id,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            alert_record_id=None,
        )

        assert result["success"] is True
        raw_recharge_info = mock_execute_agent.call_args.kwargs["raw_recharge_info"]
        assert json.loads(raw_recharge_info)["expected_date"] == "2026-04-25"

    @patch("cloud_billing.tasks.execute_recharge_approval_agent")
    def test_submit_recharge_approval_uses_explicit_alert_amount(
        self,
        mock_execute_agent,
        cloud_provider,
        monkeypatch,
    ):
        """
        Alert-triggered submissions should use the configured manual amount.
        """
        cloud_provider.recharge_info = (
            '{"recharge_account": "acct-188", "amount": 188}'
        )
        cloud_provider.save(update_fields=["recharge_info"])
        monkeypatch.setattr(
            timezone,
            "localdate",
            lambda: datetime.date(2026, 4, 22),
        )
        record = AlertRecord.objects.create(
            provider=cloud_provider,
            alert_rule=None,
            alert_type=AlertRecord.ALERT_TYPE_DAYS_REMAINING,
            current_cost=Decimal("100.50"),
            previous_cost=Decimal("80.00"),
            increase_cost=Decimal("20.50"),
            increase_percent=Decimal("25.63"),
            currency="CNY",
            current_balance=Decimal("407.52"),
            balance_threshold=None,
            current_days_remaining=1598,
            days_remaining_threshold=3000,
            alert_message="days remaining alert",
            webhook_status=WEBHOOK_STATUS_PENDING,
        )
        mock_execute_agent.return_value = {
            "request_payload": {
                "recharge_account": "acct-188",
                "amount": 358,
                "currency": "CNY",
            },
            "submission_payload": {"ok": True},
            "submitter_identifier": "",
            "resolved_submitter_user_id": "",
            "submitter_user_label": "",
            "instance_code": "ins_188",
            "approval_code": "approval_188",
            "status": "PENDING",
            "success": True,
            "summary": "submitted",
        }

        result = submit_recharge_approval(
            cloud_provider.id,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            alert_record_id=record.id,
            amount="500.00",
            currency="CNY",
        )

        assert result["success"] is True
        raw_recharge_info = mock_execute_agent.call_args.kwargs["raw_recharge_info"]
        payload = json.loads(raw_recharge_info)
        assert payload["amount"] == "500.00"
        assert payload["currency"] == "CNY"
        assert payload["expected_date"] == "2026-04-25"

    @patch("cloud_billing.tasks.execute_recharge_approval_agent")
    def test_submit_recharge_approval_populates_alert_context_labels(
        self,
        mock_execute_agent,
        cloud_provider,
    ):
        """
        Alert-triggered submissions should persist explicit trigger and submitter
        labels even when the caller does not pass a human operator.
        """
        cloud_provider.recharge_info = (
            '{"recharge_account": "demo-account-001", '
            '"recharge_customer_name": "示例云科技有限公司", '
            '"payment_company": "示例云科技有限公司", '
            '"payment_way": "公司支付", '
            '"payment_type": "仅充值", '
            '"remit_method": "转账"}'
        )
        cloud_provider.save(update_fields=["recharge_info"])
        alert_record = AlertRecord.objects.create(
            provider=cloud_provider,
            alert_rule=None,
            alert_type=AlertRecord.ALERT_TYPE_DAYS_REMAINING,
            current_cost=Decimal("100.50"),
            previous_cost=Decimal("80.00"),
            increase_cost=Decimal("20.50"),
            increase_percent=Decimal("25.63"),
            currency="CNY",
            current_balance=Decimal("0.00"),
            balance_threshold=None,
            current_days_remaining=1598,
            days_remaining_threshold=3000,
            alert_message="days remaining alert",
            webhook_status=WEBHOOK_STATUS_PENDING,
        )
        mock_execute_agent.return_value = {
            "request_payload": {
                "recharge_account": "demo-account-001",
                "recharge_customer_name": "示例云科技有限公司",
                "amount": 358,
                "currency": "CNY",
                "payment_company": "示例云科技有限公司",
                "payment_way": "公司支付",
                "payment_type": "仅充值",
                "remit_method": "转账",
            },
            "submission_payload": {"ok": True},
            "submitter_identifier": "",
            "resolved_submitter_user_id": "",
            "submitter_user_label": "",
            "instance_code": "ins_188",
            "approval_code": "approval_188",
            "status": "PENDING",
            "success": True,
            "summary": "submitted",
        }

        result = submit_recharge_approval(
            cloud_provider.id,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            alert_record_id=alert_record.id,
            billing_account_id="billing-account-001",
        )

        assert result["success"] is True
        record = RechargeApprovalRecord.objects.get(feishu_instance_code="ins_188")
        assert record.triggered_by_username_snapshot == "系统自动触发"
        assert record.submitter_user_label == "系统自动提交"
        assert record.trigger_reason == (
            "剩余天数不足（当前预计 1598 天，阈值 3000 天）"
        )
        assert record.context_payload["triggered_by"] == "系统自动触发"
        assert record.context_payload["submitter_label"] == "系统自动提交"
        assert record.context_payload["billing_account_id"] == (
            "billing-account-001"
        )
        assert record.context_payload["current_balance"] == "0.00"
        assert record.context_payload["trigger_reason"] == (
            "剩余天数不足（当前预计 1598 天，阈值 3000 天）"
        )

    @patch("cloud_billing.tasks.execute_recharge_approval_agent")
    def test_submit_recharge_approval_uses_request_account_id(
        self,
        mock_execute_agent,
        cloud_provider,
    ):
        """
        Task should bind the submitted recharge info to the explicit account_id
        provided by the caller.
        """
        cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-old"}'
        cloud_provider.save(update_fields=["recharge_info"])
        mock_execute_agent.return_value = {
            "request_payload": {"amount": 188, "recharge_account": "acct-new"},
            "submission_payload": {"ok": True},
            "submitter_identifier": "",
            "resolved_submitter_user_id": "",
            "submitter_user_label": "",
            "instance_code": "ins_new",
            "approval_code": "approval_new",
            "status": "PENDING",
            "success": True,
            "summary": "submitted",
        }

        result = submit_recharge_approval(
            cloud_provider.id,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
            account_id="acct-new",
        )

        assert result["success"] is True
        assert result["instance_code"] == "ins_new"
        raw_recharge_info = mock_execute_agent.call_args.kwargs["raw_recharge_info"]
        assert json.loads(raw_recharge_info)["recharge_account"] == "acct-new"

    @patch("cloud_billing.tasks.check_ongoing_recharge_approval_submission")
    @patch("cloud_billing.tasks.resolve_submitter_identity")
    @patch("cloud_billing.tasks.execute_recharge_approval_agent")
    def test_submit_recharge_approval_blocks_ongoing_account(
        self,
        mock_execute_agent,
        mock_resolve_submitter_identity,
        mock_inspect_account_state,
        cloud_provider,
        monkeypatch,
    ):
        """
        Task should stop before agent execution when the same recharge account
        already has a live pending approval, regardless of submitter.
        """
        cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
        cloud_provider.config = {
            "recharge_approval": {
                "submitter_identifier": "finance@example.com",
                "resolved_submitter_user_id": "ou_123",
            }
        }
        cloud_provider.save(update_fields=["recharge_info", "config"])
        monkeypatch.setenv("FEISHU_APPROVAL_CODE", "approval_188")
        existing = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
            raw_recharge_info='{"amount": 188, "recharge_account": "acct-188"}',
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            submitter_identifier="other@example.com",
            resolved_submitter_user_id="ou_999",
            feishu_instance_code="ins_188",
            feishu_approval_code="approval_188",
        )
        mock_pending_notification_delay = MagicMock()
        monkeypatch.setattr(
            billing_tasks.send_pending_recharge_approver_notifications,
            "delay",
            mock_pending_notification_delay,
        )
        mock_inspect_account_state.return_value = {
            "blocked": True,
            "reason": "ongoing_approval_exists",
            "record_id": existing.id,
            "status": "PENDING",
            "instance_code": "ins_188",
            "approval_code": "approval_188",
            "recharge_account": "acct-188",
            "message": (
                "充值账号 acct-188 已有一笔正在审批中的充值申请；"
                "实例号：ins_188；审批码：approval_188；状态：PENDING，"
                "请先确认上一单是否已结束，再继续提交。"
            ),
            "account_state": {
                "state": "ongoing",
                "approval_code": "approval_188",
                "recharge_account": "acct-188",
                "instance_code": "ins_188",
                "serial_number": "SN-188",
                "status": "PENDING",
                "user_id": "ou_999",
                "start_time": "2025-01-01T00:00:00Z",
            },
        }

        result = submit_recharge_approval(
            cloud_provider.id,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
            submitter_identifier="finance@example.com",
            submitter_user_label="Finance",
        )

        assert result["success"] is False
        assert result["reason"] == "ongoing_approval_exists"
        assert result["record_id"] == existing.id
        assert "实例号：ins_188" in result["message"]
        mock_pending_notification_delay.assert_called_once_with(existing.id)
        mock_execute_agent.assert_not_called()
        mock_resolve_submitter_identity.assert_not_called()

    @patch("cloud_billing.tasks.check_ongoing_recharge_approval_submission")
    @patch("cloud_billing.tasks.resolve_submitter_identity")
    @patch("cloud_billing.tasks.execute_recharge_approval_agent")
    def test_submit_recharge_approval_blocks_ongoing_account_without_instance_code(
        self,
        mock_execute_agent,
        mock_resolve_submitter_identity,
        mock_inspect_account_state,
        cloud_provider,
    ):
        """
        Task should surface a clearer message when the ongoing approval has no
        Feishu instance code.
        """
        cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
        cloud_provider.save(update_fields=["recharge_info"])
        mock_inspect_account_state.return_value = {
            "blocked": True,
            "reason": "ongoing_approval_exists",
            "record_id": 42,
            "status": "PENDING",
            "instance_code": "",
            "approval_code": "approval_188",
            "recharge_account": "acct-188",
            "message": (
                "充值账号 acct-188 已有一笔正在审批中的充值申请；"
                "本地记录：42；审批码：approval_188；状态：PENDING；"
                "本地状态说明：Waiting for approval，"
                "请先确认上一单是否已结束，再继续提交。"
            ),
            "account_state": {
                "state": "ongoing",
                "approval_code": "approval_188",
                "recharge_account": "acct-188",
                "instance_code": "",
                "serial_number": "SN-188",
                "status": "PENDING",
                "user_id": "ou_999",
                "start_time": "2025-01-01T00:00:00Z",
            },
        }

        result = submit_recharge_approval(
            cloud_provider.id,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
            submitter_identifier="finance@example.com",
            submitter_user_label="Finance",
        )

        assert result["success"] is False
        assert result["record_id"] == 42
        assert "本地记录：42" in result["message"]
        assert "本地状态说明：Waiting for approval" in result["message"]
        mock_execute_agent.assert_not_called()
        mock_resolve_submitter_identity.assert_not_called()

    @patch("cloud_billing.tasks.check_ongoing_recharge_approval_submission")
    @patch("cloud_billing.tasks.resolve_submitter_identity")
    @patch("cloud_billing.tasks.execute_recharge_approval_agent")
    def test_submit_recharge_approval_allows_same_submitter_different_account(
        self,
        mock_execute_agent,
        mock_resolve_submitter_identity,
        mock_inspect_account_state,
        cloud_provider,
        monkeypatch,
    ):
        """
        Task should allow a new submission when only the submitter matches and
        the recharge account is different.
        """
        cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188-new"}'
        cloud_provider.config = {
            "recharge_approval": {
                "submitter_identifier": "finance@example.com",
                "resolved_submitter_user_id": "ou_123",
            }
        }
        cloud_provider.save(update_fields=["recharge_info", "config"])
        monkeypatch.setenv("FEISHU_APPROVAL_CODE", "approval_old")
        RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
            raw_recharge_info='{"amount": 188, "recharge_account": "acct-188-old"}',
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            submitter_identifier="finance@example.com",
            resolved_submitter_user_id="ou_123",
            feishu_instance_code="ins_old",
            feishu_approval_code="approval_old",
        )
        mock_inspect_account_state.return_value = {
            "blocked": False,
            "reason": "",
            "record_id": 0,
            "status": "APPROVED",
            "instance_code": "ins_old",
            "approval_code": "approval_old",
            "recharge_account": "acct-188-old",
            "account_state": {
                "state": "finished",
                "approval_code": "approval_old",
                "recharge_account": "acct-188-old",
                "instance_code": "ins_old",
                "serial_number": "SN-old",
                "status": "APPROVED",
                "user_id": "ou_123",
                "start_time": "2025-01-01T00:00:00Z",
            },
        }
        mock_resolve_submitter_identity.return_value = (
            "finance@example.com",
            "Finance",
            "ou_123",
        )
        mock_execute_agent.return_value = {
            "request_payload": {
                "amount": 188,
                "recharge_account": "acct-188-new",
            },
            "submission_payload": {"ok": True},
            "submitter_identifier": "finance@example.com",
            "resolved_submitter_user_id": "ou_123",
            "submitter_user_label": "Finance",
            "instance_code": "ins_188_new",
            "approval_code": "approval_188_new",
            "status": "PENDING",
            "success": True,
            "summary": "submitted",
        }

        result = submit_recharge_approval(
            cloud_provider.id,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
            submitter_identifier="finance@example.com",
            submitter_user_label="Finance",
        )

        assert result["success"] is True
        assert result["instance_code"] == "ins_188_new"
        mock_execute_agent.assert_called_once()

    def test_submit_recharge_approval_rejects_missing_info(
        self,
        cloud_provider,
        monkeypatch,
    ):
        """
        Task should fail fast when provider recharge info is empty.
        """
        monkeypatch.delenv("FEISHU_APPROVAL_CODE", raising=False)
        result = submit_recharge_approval(
            cloud_provider.id,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
        )

        assert result["success"] is False
        assert result["reason"] == "missing_recharge_info"
