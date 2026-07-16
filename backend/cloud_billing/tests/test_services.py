"""
Tests for cloud billing services.
"""

import json
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from cloud_billing.models import (
    AlertRecord,
    BillingData,
    RechargeApprovalRecord,
)
from cloud_billing.services.notification_service import (
    CloudBillingNotificationService,
    RechargeApprovalNotificationService,
)
from cloud_billing.services.provider_service import ProviderService


@pytest.mark.django_db
class TestProviderService:
    """
    Tests for ProviderService.
    """

    @patch("cloud_billing.services.provider_service.ProviderFactory")
    def test_create_provider_success(self, mock_factory):
        """
        Test creating a provider successfully.
        Service normalizes config (e.g. api_key/api_secret for aws).
        """
        mock_provider_instance = Mock()
        mock_factory.create_provider.return_value = mock_provider_instance

        service = ProviderService()
        result = service.create_provider(
            "aws", {"api_key": "test", "api_secret": "test"}
        )

        assert result == mock_provider_instance
        mock_factory.create_provider.assert_called_once_with(
            "aws", {"api_key": "test", "api_secret": "test"}
        )

    @patch("cloud_billing.services.provider_service.ProviderFactory")
    def test_create_provider_import_error(self, mock_factory):
        """
        Test that ImportError from factory is propagated.
        """
        mock_factory.create_provider.side_effect = ImportError(
            "No module named cloud_billings"
        )

        service = ProviderService()
        with pytest.raises(ImportError, match="cloud_billings"):
            service.create_provider("aws", {})

    @patch("cloud_billing.services.provider_service.BillingService")
    def test_get_billing_info_success(self, mock_billing_service):
        """
        Test getting billing info successfully.
        """
        mock_instance = Mock()
        mock_instance.get_billing_info.return_value = {
            "status": "success",
            "data": {
                "total_cost": 100.50,
                "currency": "USD",
                "service_costs": {"ec2": 50.00},
            },
        }
        mock_billing_service.return_value = mock_instance

        service = ProviderService()
        result = service.get_billing_info(
            "aws",
            {"access_key": "test", "secret_key": "test"},
            period="2025-01",
        )

        assert result["status"] == "success"
        assert "data" in result

    @patch("cloud_billing.services.provider_service.BillingService")
    def test_get_billing_info_error(self, mock_billing_service):
        """
        Test handling errors when getting billing info.
        """
        mock_billing_service.side_effect = Exception("API Error")

        service = ProviderService()
        with pytest.raises(Exception):
            service.get_billing_info("aws", {}, period="2025-01")

    @patch("cloud_billing.services.provider_service.BillingService")
    def test_get_billing_info_classifies_volcengine_timeout(
        self, mock_billing_service
    ):
        """
        Volcengine service timeouts should be treated as cloud API errors.
        """
        mock_instance = Mock()
        mock_instance.get_billing_info.return_value = {
            "status": "error",
            "data": None,
            "error": (
                "InternalServiceTimeout: Internal Service is timeout. "
                "Pls Contact With Admin"
            ),
        }
        mock_billing_service.return_value = mock_instance

        service = ProviderService()
        result = service.get_billing_info(
            "volcengine",
            {"api_key": "test", "api_secret": "test"},
            period="2026-06",
        )

        assert result["status"] == "error"
        assert result["error_code"] == "volcengine_timeout"
        assert result["is_api_error"] is True
        assert result["required_permissions"] == []

    @patch("cloud_billing.services.provider_service.ProviderFactory")
    def test_create_provider_volcengine_normalizes_config(self, mock_factory):
        """
        Test Volcengine config normalization before provider creation.
        """
        mock_provider_instance = Mock()
        mock_factory.create_provider.return_value = mock_provider_instance

        service = ProviderService()
        result = service.create_provider(
            "volcengine",
            {
                "VOLCENGINE_ACCESS_KEY_ID": "test_key",
                "VOLCENGINE_SECRET_ACCESS_KEY": "test_secret",
                "VOLCENGINE_REGION": "cn-north-1",
                "VOLCENGINE_ENDPOINT": "https://billing.volcengineapi.com",
                "VOLCENGINE_PAYER_ID": "2100052604",
            },
        )

        assert result == mock_provider_instance
        mock_factory.create_provider.assert_called_once_with(
            "volcengine",
            {
                "api_key": "test_key",
                "api_secret": "test_secret",
                "region": "cn-north-1",
                "endpoint": "https://billing.volcengineapi.com",
                "payer_id": "2100052604",
            },
        )

    @patch("cloud_billing.services.provider_service.ProviderFactory")
    def test_create_provider_tencentcloud_normalizes_config(
        self, mock_factory
    ):
        """
        Test Tencent Cloud config normalization before provider creation.
        """
        mock_provider_instance = Mock()
        mock_factory.create_provider.return_value = mock_provider_instance

        service = ProviderService()
        result = service.create_provider(
            "tencentcloud",
            {
                "TENCENT_ACCESS_KEY_ID": "test_key",
                "TENCENT_ACCESS_KEY_SECRET": "test_secret",
                "TENCENT_APP_ID": "10001",
                "TENCENT_REGION": "ap-guangzhou",
                "TENCENT_ENDPOINT": "billing.tencentcloudapi.com",
                "TENCENT_TIMEOUT": 45,
                "TENCENT_MAX_RETRIES": 5,
            },
        )

        assert result == mock_provider_instance
        mock_factory.create_provider.assert_called_once_with(
            "tencentcloud",
            {
                "access_key_id": "test_key",
                "access_key_secret": "test_secret",
                "app_id": "10001",
                "region": "ap-guangzhou",
                "endpoint": "billing.tencentcloudapi.com",
                "timeout": 45,
                "max_retries": 5,
            },
        )

    @patch("cloud_billing.services.provider_service.ProviderFactory")
    def test_create_provider_azure_normalizes_billing_account_id(
        self, mock_factory
    ):
        """Test Azure config normalization includes billing account id."""
        mock_provider_instance = Mock()
        mock_factory.create_provider.return_value = mock_provider_instance

        service = ProviderService()
        result = service.create_provider(
            "azure",
            {
                "AZURE_CLIENT_ID": "client",
                "AZURE_CLIENT_SECRET": "secret",
                "AZURE_TENANT_ID": "tenant",
                "AZURE_SUBSCRIPTION_ID": "sub",
                "AZURE_BILLING_ACCOUNT_ID": "billing-001",
            },
        )

        assert result == mock_provider_instance
        mock_factory.create_provider.assert_called_once_with(
            "azure",
            {
                "client_id": "client",
                "client_secret": "secret",
                "tenant_id": "tenant",
                "subscription_id": "sub",
                "billing_account_id": "billing-001",
            },
        )

    @patch("cloud_billing.services.provider_service.ProviderFactory")
    def test_create_provider_baidu_normalizes_config(self, mock_factory):
        """Test Baidu config normalization before provider creation."""
        mock_provider_instance = Mock()
        mock_factory.create_provider.return_value = mock_provider_instance

        service = ProviderService()
        service.create_provider(
            "baidu",
            {
                "BAIDU_ACCESS_KEY_ID": "test_key",
                "BAIDU_SECRET_ACCESS_KEY": "test_secret",
            },
        )

    @patch("cloud_billing.services.provider_service.ProviderFactory")
    def test_create_provider_zhipu_normalizes_config(self, mock_factory):
        """Test Zhipu config normalization before provider creation."""
        mock_provider_instance = Mock()
        mock_factory.create_provider.return_value = mock_provider_instance

        service = ProviderService()
        result = service.create_provider(
            "zhipu",
            {
                "ZHIPU_USERNAME": "tester",
                "ZHIPU_PASSWORD": "secret",
                "ZHIPU_ORGANIZATION": "org-123",
                "ZHIPU_PROJECT": "proj-456",
            },
        )

        assert result == mock_provider_instance
        mock_factory.create_provider.assert_called_once_with(
            "zhipu",
            {
                "username": "tester",
                "password": "secret",
            },
        )

    @patch("cloud_billing.services.provider_service.ProviderFactory")
    def test_create_provider_deepseek_normalizes_config(self, mock_factory):
        """Test DeepSeek API key normalization before provider creation."""
        mock_provider_instance = Mock()
        mock_factory.create_provider.return_value = mock_provider_instance

        service = ProviderService()
        result = service.create_provider(
            "deepseek",
            {
                "DEEPSEEK_API_KEY": "sk-test-key",
                "DEEPSEEK_TIMEOUT": 15,
            },
        )

        assert result == mock_provider_instance
        mock_factory.create_provider.assert_called_once_with(
            "deepseek",
            {
                "api_key": "sk-test-key",
                "timeout": 15,
            },
        )

    def test_classify_deepseek_invalid_api_key(self):
        """Classify DeepSeek HTTP 401 as a credential error."""
        result = ProviderService()._classify_error(
            "deepseek",
            "401 Client Error: Unauthorized",
        )

        assert result == {
            "error_code": "deepseek_invalid_api_key",
            "error_type": "credential_error",
            "required_permissions": [],
        }

    @patch("cloud_billing.services.provider_service.ProviderFactory")
    def test_create_provider_yunce_normalizes_config(self, mock_factory):
        """Test Yunce credential normalization before provider creation."""
        mock_provider_instance = Mock()
        mock_factory.create_provider.return_value = mock_provider_instance

        result = ProviderService().create_provider(
            "yunce",
            {
                "YUNCE_USERNAME": "account",
                "YUNCE_PASSWORD": "pass",
                "YUNCE_API_KEY": "sk-selected-secret",
                "YUNCE_TIMEOUT": 20,
            },
        )

        assert result == mock_provider_instance
        mock_factory.create_provider.assert_called_once_with(
            "yunce",
            {
                "username": "account",
                "password": "pass",
                "api_key": "sk-selected-secret",
                "timeout": 20,
            },
        )

    def test_classify_yunce_unauthorized(self):
        """Classify Yunce HTTP 401 as a credential error."""
        result = ProviderService()._classify_error(
            "yunce",
            "401 Client Error: Unauthorized",
        )

        assert result == {
            "error_code": "yunce_invalid_credentials",
            "error_type": "credential_error",
            "required_permissions": [],
        }

    @patch(
        "cloud_billing.services.provider_service."
        "ProviderService.create_provider"
    )
    def test_validate_credentials_success(self, mock_create_provider):
        """
        Test validating credentials successfully.
        Implementation returns valid, error_code, account_id (no message).
        """
        mock_provider = Mock()
        mock_provider.validate_credentials.return_value = True
        mock_provider.get_account_id.return_value = "123456789012"
        mock_create_provider.return_value = mock_provider

        service = ProviderService()
        result = service.validate_credentials(
            "aws", {"api_key": "test", "api_secret": "test"}
        )

        assert result["valid"] is True
        assert result["account_id"] == "123456789012"
        assert result.get("error_code") is None

    @patch(
        "cloud_billing.services.provider_service."
        "ProviderService.create_provider"
    )
    def test_validate_credentials_invalid(self, mock_create_provider):
        """
        Test validating invalid credentials.
        """
        mock_provider = Mock()
        mock_provider.validate_credentials.return_value = False
        mock_create_provider.return_value = mock_provider

        service = ProviderService()
        result = service.validate_credentials(
            "aws", {"api_key": "invalid", "api_secret": "invalid"}
        )

        assert result["valid"] is False
        assert result["account_id"] == ""
        assert result.get("error_code") == "validation_failed"

    @patch(
        "cloud_billing.services.provider_service."
        "ProviderService.create_provider"
    )
    def test_validate_credentials_exception(self, mock_create_provider):
        """
        Test handling exceptions during credential validation.
        Exception path returns error_code (e.g. network_error).
        """
        mock_create_provider.side_effect = Exception("Connection error")

        service = ProviderService()
        result = service.validate_credentials("aws", {})

        assert result["valid"] is False
        assert result.get("error_code") == "network_error"

    @patch(
        "cloud_billing.services.provider_service."
        "ProviderService.create_provider"
    )
    def test_get_account_id_success(self, mock_create_provider):
        """
        Test getting account ID successfully.
        """
        mock_provider = Mock()
        mock_provider.get_account_id.return_value = "123456789012"
        mock_create_provider.return_value = mock_provider

        service = ProviderService()
        result = service.get_account_id(
            "aws", {"access_key": "test", "secret_key": "test"}
        )

        assert result == "123456789012"

    @patch(
        "cloud_billing.services.provider_service."
        "ProviderService.create_provider"
    )
    def test_get_account_id_error(self, mock_create_provider):
        """
        Test handling errors when getting account ID.
        """
        mock_provider = Mock()
        mock_provider.get_account_id.side_effect = Exception("API Error")
        mock_create_provider.return_value = mock_provider

        service = ProviderService()
        with pytest.raises(Exception):
            service.get_account_id("aws", {})


@pytest.mark.django_db
class TestCloudBillingNotificationService:
    """
    Tests for CloudBillingNotificationService.

    These tests focus on the business logic of converting
    cloud billing data to notification format.
    """

    @patch("cloud_billing.services.notification_service.send_notification")
    @patch(
        "cloud_billing.services.notification_service."
        "get_webhook_channel_by_uuid"
    )
    def test_send_alert_feishu(
        self, mock_get_by_uuid, mock_send_task, alert_record
    ):
        """
        Test sending alert via Feishu (unified send_notification webhook).
        """
        from uuid import uuid4

        ch_uuid = uuid4()
        mock_channel = type(
            "Channel",
            (),
            {
                "uuid": ch_uuid,
                "config": {"language": "zh-hans"},
            },
        )()
        mock_config = {"is_active": True, "provider": "feishu"}
        mock_get_by_uuid.return_value = (mock_channel, mock_config)

        service = CloudBillingNotificationService()
        result = service.send_alert(alert_record, channel_uuid=str(ch_uuid))

        assert result["success"] is True
        mock_send_task.delay.assert_called_once()
        call_kwargs = mock_send_task.delay.call_args[1]
        assert call_kwargs["notification_type"] == "webhook"
        assert call_kwargs["channel_uuid"] == str(ch_uuid)
        params = call_kwargs["params"]
        assert params["provider_type"] == "feishu"
        payload = params["payload"]
        assert payload["msg_type"] == "interactive"
        assert "card" in payload
        assert payload["card"]["schema"] == "2.0"
        assert "elements" not in payload["card"]
        assert payload["card"]["body"]["elements"]
        assert "header" in payload["card"]
        assert call_kwargs["source_app"] == "cloud_billing"
        assert call_kwargs["source_type"] == "alert"
        assert str(alert_record.id) == call_kwargs["source_id"]

    @patch("cloud_billing.services.notification_service.send_notification")
    @patch(
        "cloud_billing.services.notification_service."
        "get_webhook_channel_by_uuid"
    )
    def test_send_alert_wechat(
        self, mock_get_by_uuid, mock_send_task, alert_record
    ):
        """
        Test sending alert via WeChat (unified send_notification webhook).
        """
        from uuid import uuid4

        ch_uuid = uuid4()
        mock_channel = type(
            "Channel",
            (),
            {
                "uuid": ch_uuid,
                "config": {"language": "zh-hans"},
            },
        )()
        mock_config = {"is_active": True, "provider": "wechat"}
        mock_get_by_uuid.return_value = (mock_channel, mock_config)

        service = CloudBillingNotificationService()
        result = service.send_alert(alert_record, channel_uuid=str(ch_uuid))

        assert result["success"] is True
        mock_send_task.delay.assert_called_once()
        call_kwargs = mock_send_task.delay.call_args[1]
        assert call_kwargs["notification_type"] == "webhook"
        assert call_kwargs["channel_uuid"] == str(ch_uuid)
        params = call_kwargs["params"]
        assert params["provider_type"] == "wechat"
        payload = params["payload"]
        assert payload["msgtype"] == "markdown"
        assert "markdown" in payload
        assert "content" in payload["markdown"]

    @patch("cloud_billing.services.notification_service.send_notification")
    @patch(
        "cloud_billing.services.notification_service."
        "get_default_webhook_channel"
    )
    def test_send_alert_uses_default_when_channel_uuid_is_none(
        self,
        mock_get_default,
        mock_send_task,
        alert_record,
    ):
        """
        When channel_uuid is None, use notifier default.
        Unified task called with channel_uuid=None; notifier resolves default.
        """
        mock_channel = type(
            "Channel",
            (),
            {
                "uuid": __import__("uuid").uuid4(),
                "config": {"language": "zh-hans"},
            },
        )()
        mock_config = {"is_active": True, "provider": "feishu"}
        mock_get_default.return_value = (mock_channel, mock_config)

        service = CloudBillingNotificationService()
        result = service.send_alert(alert_record, channel_uuid=None)

        assert result["success"] is True
        mock_send_task.delay.assert_called_once()
        call_kwargs = mock_send_task.delay.call_args[1]
        assert call_kwargs["notification_type"] == "webhook"
        assert call_kwargs["channel_uuid"] == str(mock_channel.uuid)
        assert call_kwargs["params"]["provider_type"] == "feishu"

    @patch("cloud_billing.services.notification_service.send_notification")
    def test_send_alert_email_without_channel_uuid_returns_error(
        self,
        mock_send_task,
        alert_record,
    ):
        """
        Email notification requires channel_uuid; do not silently fallback.
        """
        service = CloudBillingNotificationService()
        result = service.send_alert(
            alert_record,
            channel_uuid=None,
            channel_type="email",
        )
        assert result["success"] is False
        assert "channel_uuid is required" in result["error"]
        mock_send_task.delay.assert_not_called()

    @patch(
        "cloud_billing.services.notification_service."
        "get_default_webhook_channel"
    )
    def test_send_alert_no_default_returns_error_when_channel_uuid_none(
        self,
        mock_get_default,
        alert_record,
    ):
        """
        When channel_uuid is None and notifier has no default, return error.
        """
        mock_get_default.return_value = (None, None)

        service = CloudBillingNotificationService()
        result = service.send_alert(alert_record, channel_uuid=None)

        assert result["success"] is False
        err = result["error"].lower()
        assert "not found" in err or "not active" in err

    @patch("cloud_billing.services.notification_service.send_notification")
    @patch(
        "cloud_billing.services.notification_service."
        "get_webhook_channel_by_uuid"
    )
    def test_send_alert_with_channel_uuid(
        self, mock_get_by_uuid, mock_send_task, alert_record
    ):
        """
        Test sending alert with channel_uuid; unified task gets params.
        """
        from uuid import uuid4

        ch_uuid = uuid4()
        mock_channel = type(
            "Channel",
            (),
            {
                "id": 1,
                "uuid": ch_uuid,
                "config": {"language": "zh-hans"},
            },
        )()
        mock_config = {"is_active": True, "provider": "feishu"}
        mock_get_by_uuid.return_value = (mock_channel, mock_config)

        service = CloudBillingNotificationService()
        result = service.send_alert(alert_record, channel_uuid=str(ch_uuid))

        assert result["success"] is True
        mock_send_task.delay.assert_called_once()
        call_kwargs = mock_send_task.delay.call_args[1]
        assert call_kwargs["notification_type"] == "webhook"
        assert call_kwargs["channel_uuid"] == str(ch_uuid)
        assert call_kwargs["params"]["provider_type"] == "feishu"

    def test_generate_feishu_payload_uses_localized_title(
        self, alert_record
    ):
        service = CloudBillingNotificationService()

        payload = service._generate_feishu_payload(alert_record, "zh-hans")

        # Verify the payload uses Feishu card format (msg_type=interactive)
        assert payload["msg_type"] == "interactive"
        assert "card" in payload
        assert "header" in payload["card"]
        assert "title" in payload["card"]["header"]
        assert "content" in payload["card"]["header"]["title"]
        # Title contains the localized text
        assert "云平台账单" in payload["card"]["header"]["title"]["content"]

    def test_feishu_alert_preserves_existing_approval_progress(
        self,
        alert_record,
    ):
        alert_record.alert_message = (
            "告警类型：余额阈值告警\n"
            "充值审批：已有充值审批流程正在进行；"
            "当前进度：等待审批；"
            "当前审批人：Approver A（审批节点 A）。"
        )

        payload = CloudBillingNotificationService()._generate_feishu_payload(
            alert_record,
            "zh-hans",
        )
        approval_content = next(
            element["content"]
            for element in payload["card"]["body"]["elements"]
            if element.get("tag") == "markdown"
            and "充值审批" in element.get("content", "")
        )

        assert approval_content == (
            "**充值审批**：已有充值审批流程正在进行\n"
            "**当前进度**：等待审批\n"
            "**当前审批人**：Approver A（审批节点 A）。"
        )

    def test_feishu_alert_adds_collapsible_approval_progress(
        self,
        alert_record,
        monkeypatch,
    ):
        """Ongoing approvals should expose their node progress on demand."""
        alert_record.alert_message = (
            "告警类型：余额阈值告警\n"
            "账号：billing-account-test\n"
            "充值审批：已有充值审批流程正在进行；"
            "当前进度：等待审批；"
            "当前审批人：Approver B（审批节点 B）。"
        )
        service = CloudBillingNotificationService()
        monkeypatch.setattr(
            service,
            "_get_recharge_approval_progress",
            lambda record: [
                {
                    "node_name": "发起",
                    "node_kind": "start",
                    "status": "APPROVED",
                    "approver_names": ["Test Initiator"],
                    "end_time": "1000",
                },
                {
                    "node_name": "审批节点 A",
                    "status": "APPROVED",
                    "approver_names": ["Approver A"],
                    "end_time": "2000",
                },
                {
                    "node_name": "审批节点 B",
                    "status": "PENDING",
                    "approver_names": ["Approver B"],
                    "start_time": "3000",
                },
                {
                    "node_name": "审批节点 C",
                    "status": "NOT_STARTED",
                    "approver_names": ["Approver C"],
                },
                {
                    "node_name": "结束",
                    "node_kind": "end",
                    "status": "NOT_STARTED",
                    "approver_names": [],
                },
            ],
        )

        payload = service._generate_feishu_payload(
            alert_record,
            "zh-hans",
        )

        panel = next(
            element
            for element in payload["card"]["body"]["elements"]
            if element.get("tag") == "collapsible_panel"
        )
        assert panel["expanded"] is False
        assert panel["header"]["title"]["content"] == (
            "**审批进度（3/5）**"
        )
        progress_content = panel["elements"][0]["content"]
        assert "✅ **发起**" in progress_content
        assert "🟠 **审批节点 B**" in progress_content
        assert "⚪ **结束**" in progress_content
        assert "**审批人**：Approver B" in progress_content
        assert "**审批人**：待确定" not in progress_content

    def test_approval_progress_time_uses_shanghai_timezone(self):
        service = CloudBillingNotificationService()

        formatted = service._format_approval_progress_time(
            "28800000"
        )

        assert formatted == "1970-01-01 16:00:00"

    def test_approval_progress_uses_semantic_time_labels(self):
        nodes = [
            {
                "node_name": "发起",
                "node_kind": "start",
                "status": "APPROVED",
                "end_time": "28800000",
            },
            {
                "node_name": "审批节点 A",
                "status": "APPROVED",
                "end_time": "28801000",
            },
            {
                "node_name": "审批节点 B",
                "status": "PENDING",
                "start_time": "28802000",
            },
        ]

        panel = (
            CloudBillingNotificationService()
            ._build_feishu_approval_progress_panel(nodes, "zh-hans")
        )
        content = panel["elements"][0]["content"]

        assert "**提交时间**：" in content
        assert "**完成时间**：" in content
        assert "**进入节点时间**：" in content
        assert "**节点时间**：" not in content

    def test_alert_progress_uses_ongoing_approval_for_billing_account(
        self,
        alert_record,
        monkeypatch,
    ):
        """The panel should use the approval tied to the alerted account."""
        alert_record.alert_message = (
            "账号：billing-account-test\n"
            "充值审批：已有充值审批流程正在进行；"
            "当前进度：等待审批；当前审批人：Approver A。"
        )
        approval = RechargeApprovalRecord.objects.create(
            provider=alert_record.provider,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            context_payload={
                "billing_account_id": "billing-account-test"
            },
            request_payload={"recharge_account": "recharge-account-test"},
        )
        expected = [
            {
                "node_name": "发起",
                "node_kind": "start",
                "status": "APPROVED",
            },
            {
                "node_name": "审批节点 A",
                "status": "PENDING",
            },
            {
                "node_name": "结束",
                "node_kind": "end",
                "status": "NOT_STARTED",
                "approver_names": [],
            },
        ]
        captured = []

        def load_progress(record):
            captured.append(record)
            return expected

        monkeypatch.setattr(
            "cloud_billing.services.notification_service."
            "get_recharge_approval_progress",
            load_progress,
        )

        progress = (
            CloudBillingNotificationService()
            ._get_recharge_approval_progress(alert_record)
        )

        assert progress == expected
        assert captured == [approval]

    def test_alert_progress_refreshes_legacy_cached_snapshot(
        self,
        alert_record,
        monkeypatch,
    ):
        """Snapshots without boundary nodes should be refreshed once."""
        alert_record.alert_message = (
            "账号：billing-account-test\n"
            "充值审批：已有充值审批流程正在进行；"
            "当前进度：等待审批；当前审批人：Approver A。"
        )
        approval = RechargeApprovalRecord.objects.create(
            provider=alert_record.provider,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            context_payload={
                "billing_account_id": "billing-account-test",
                "approval_progress": [
                    {
                        "node_name": "审批节点 A",
                        "status": "PENDING",
                    }
                ],
            },
        )
        expected = [
            {
                "node_name": "发起",
                "node_kind": "start",
                "status": "APPROVED",
            },
            {
                "node_name": "审批节点 A",
                "status": "PENDING",
            },
            {
                "node_name": "结束",
                "node_kind": "end",
                "status": "NOT_STARTED",
            },
        ]
        captured = []

        def load_progress(record):
            captured.append(record)
            return expected

        monkeypatch.setattr(
            "cloud_billing.services.notification_service."
            "get_recharge_approval_progress",
            load_progress,
        )

        progress = (
            CloudBillingNotificationService()
            ._get_recharge_approval_progress(alert_record)
        )

        assert progress == expected
        assert captured == [approval]

    def test_alert_progress_prefers_fresh_cached_snapshot(
        self,
        alert_record,
        monkeypatch,
    ):
        """Card rendering should not repeat live API calls when cached."""
        alert_record.alert_message = (
            "账号：billing-account-test\n"
            "充值审批：已有充值审批流程正在进行；"
            "当前进度：等待审批；当前审批人：Approver A。"
        )
        expected = [
            {
                "node_name": "发起",
                "node_kind": "start",
                "status": "APPROVED",
            },
            {
                "node_name": "审批节点 A",
                "status": "PENDING",
            },
            {
                "node_name": "结束",
                "node_kind": "end",
                "status": "NOT_STARTED",
                "approver_names": [],
            },
        ]
        RechargeApprovalRecord.objects.create(
            provider=alert_record.provider,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            context_payload={
                "billing_account_id": "billing-account-test",
                "approval_progress": expected,
                "approval_progress_cached_at": (
                    timezone.now().isoformat()
                ),
            },
        )

        def fail_live_load(record):
            raise AssertionError("live progress should not be loaded")

        monkeypatch.setattr(
            "cloud_billing.services.notification_service."
            "get_recharge_approval_progress",
            fail_live_load,
        )

        progress = (
            CloudBillingNotificationService()
            ._get_recharge_approval_progress(alert_record)
        )

        assert progress == expected

    def test_alert_progress_refreshes_expired_cached_snapshot(
        self,
        alert_record,
        monkeypatch,
    ):
        """A delayed alert must not show an obsolete approval node."""
        alert_record.alert_message = (
            "账号：billing-account-test\n"
            "充值审批：已有充值审批流程正在进行；"
            "当前进度：等待审批；当前审批人：Approver A。"
        )
        stale = [
            {
                "node_name": "发起",
                "node_kind": "start",
                "status": "APPROVED",
            },
            {
                "node_name": "审批节点 A",
                "status": "PENDING",
            },
            {
                "node_name": "结束",
                "node_kind": "end",
                "status": "NOT_STARTED",
            },
        ]
        current = [
            {
                "node_name": "发起",
                "node_kind": "start",
                "status": "APPROVED",
            },
            {
                "node_name": "审批节点 A",
                "status": "APPROVED",
            },
            {
                "node_name": "审批节点 B",
                "status": "PENDING",
            },
            {
                "node_name": "结束",
                "node_kind": "end",
                "status": "NOT_STARTED",
            },
        ]
        approval = RechargeApprovalRecord.objects.create(
            provider=alert_record.provider,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            context_payload={
                "billing_account_id": "billing-account-test",
                "approval_progress": stale,
                "approval_progress_cached_at": (
                    "2000-01-01T00:00:00+00:00"
                ),
            },
        )
        captured = []

        def load_progress(record):
            captured.append(record)
            return current

        monkeypatch.setattr(
            "cloud_billing.services.notification_service."
            "get_recharge_approval_progress",
            load_progress,
        )

        progress = (
            CloudBillingNotificationService()
            ._get_recharge_approval_progress(alert_record)
        )

        assert progress == current
        assert captured == [approval]

    def test_alert_progress_refreshes_boundary_only_snapshot(
        self,
        alert_record,
        monkeypatch,
    ):
        """Synthetic boundary nodes are not a complete approval path."""
        alert_record.alert_message = (
            "账号：billing-account-test\n"
            "充值审批：已有充值审批流程正在进行；"
            "当前进度：等待审批。"
        )
        approval = RechargeApprovalRecord.objects.create(
            provider=alert_record.provider,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            context_payload={
                "billing_account_id": "billing-account-test",
                "approval_progress": [
                    {
                        "node_name": "发起",
                        "node_kind": "start",
                        "status": "APPROVED",
                    },
                    {
                        "node_name": "结束",
                        "node_kind": "end",
                        "status": "NOT_STARTED",
                    },
                ],
                "approval_progress_cached_at": (
                    timezone.now().isoformat()
                ),
            },
        )
        current = [
            {
                "node_name": "审批节点 A",
                "status": "PENDING",
            }
        ]
        captured = []

        def load_progress(record):
            captured.append(record)
            return current

        monkeypatch.setattr(
            "cloud_billing.services.notification_service."
            "get_recharge_approval_progress",
            load_progress,
        )

        progress = (
            CloudBillingNotificationService()
            ._get_recharge_approval_progress(alert_record)
        )

        assert progress == current
        assert captured == [approval]

    def test_generate_wechat_payload_uses_localized_title_prefix(
        self, alert_record
    ):
        service = CloudBillingNotificationService()

        payload = service._generate_wechat_payload(alert_record, "en")

        assert payload["markdown"]["content"].startswith(
            "## Cloud Billing Alert\n\n"
        )

    def test_generate_wechat_payload_rebuilds_body_for_requested_language(
        self, alert_record
    ):
        alert_record.alert_message = "告警类型：余额阈值告警"
        alert_record.current_balance = Decimal("480.00")
        alert_record.balance_threshold = Decimal("500.00")
        alert_record.provider.display_name = "Baidu AI Cloud"
        alert_record.provider.notes = "Top-up soon"
        alert_record.provider.tags = ["production", "core"]

        service = CloudBillingNotificationService()
        payload = service._generate_wechat_payload(alert_record, "en")

        content = payload["markdown"]["content"]
        # Verify message uses English labels and contains key information
        assert "## Cloud Billing Alert" in content
        assert "Baidu AI Cloud" in content
        assert "Top-up soon" in content
        # WeChat messages don't include tags in the payload
        assert payload["msgtype"] == "markdown"

    def test_generate_wechat_payload_includes_recharge_approval_notice(
        self, alert_record
    ):
        alert_record.alert_message = (
            "告警类型：余额阈值告警\n"
            "充值审批："
            "已自动触发充值审批，请关注审批进度"
        )
        alert_record.current_balance = Decimal("480.00")
        alert_record.balance_threshold = Decimal("500.00")

        service = CloudBillingNotificationService()
        payload = service._generate_wechat_payload(alert_record, "zh-hans")

        content = payload["markdown"]["content"]
        assert "充值审批" in content
        assert "已自动触发充值审批，请关注审批进度" in content

    @patch(
        "cloud_billing.services.notification_service."
        "get_webhook_channel_by_uuid"
    )
    def test_send_alert_channel_uuid_not_found(
        self, mock_get_by_uuid, alert_record
    ):
        """
        Test alert with channel_uuid that does not exist or is inactive.
        """
        mock_get_by_uuid.return_value = (None, None)

        service = CloudBillingNotificationService()
        result = service.send_alert(
            alert_record,
            channel_uuid="00000000-0000-0000-0000-000000000000",
        )

        assert result["success"] is False
        err = result["error"].lower()
        assert "not found" in err or "inactive" in err


@pytest.mark.django_db
class TestRechargeApprovalNotificationService:
    """
    Tests for recharge approval notification message content.
    """

    def test_build_recharge_message_includes_actor_and_recharge_details(
        self,
        cloud_provider,
        user,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
            trigger_reason="operations_console_timeline",
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            triggered_by=user,
            triggered_by_username_snapshot=user.username,
            submitted_by=user,
            submitter_identifier="finance@example.com",
            resolved_submitter_user_id="ou_123",
            submitter_user_label="Finance Bot",
            request_payload={
                "recharge_customer_name": "示例云科技有限公司",
                "recharge_account": "acct-188",
                "amount": "188.50",
                "currency": "CNY",
                "payment_company": "示例云科技有限公司",
                "payment_way": "公司支付",
                "payment_type": "仅充值",
                "remit_method": "转账",
                "expected_date": "2026-04-27",
                "payment_note": "余额低于阈值",
                "payee": {
                    "account_name": "示例收款有限公司",
                    "bank_name": "示例银行",
                },
            },
        )

        service = RechargeApprovalNotificationService()
        message = service._build_recharge_message(
            record,
            "submitted",
            "zh-hans",
        )

        assert (
            "**触发方式**: 人工触发（operations_console_timeline）"
            in message
        )
        assert (
            "**审批发起人**: Finance Bot / finance@example.com"
            in message
        )
        assert "**充值账号**: acct-188" in message
        assert "**付款金额**: 188.50 CNY" in message
        assert "  - 户名: 示例收款有限公司" in message

    def test_build_recharge_message_merges_alert_details(
        self,
        cloud_provider,
        alert_record,
    ):
        alert_record.alert_message = (
            "告警类型：预计使用天数告警\n"
            "当前余额：480.00 CNY\n"
            "预计使用天数：6\n"
            "告警阈值：7 天\n"
            "告警说明：预计剩余可用天数低于阈值，请及时充值"
        )
        alert_record.save(update_fields=["alert_message"])
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            alert_record=alert_record,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            trigger_reason="days_remaining_threshold",
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            request_payload={
                "recharge_customer_name": "示例云科技有限公司",
                "recharge_account": "acct-188",
                "amount": 188,
                "currency": "CNY",
                "payment_company": "示例云科技有限公司",
                "payment_way": "公司支付",
                "payment_type": "仅充值",
            },
        )

        service = RechargeApprovalNotificationService()
        message = service._build_recharge_message(
            record,
            "submitted",
            "zh-hans",
        )

        assert "**触发方式**: 告警触发（days_remaining_threshold）" in message
        assert f"**公有云类型**: {cloud_provider.display_name}" in message
        assert "告警信息" in message
        assert "告警类型: 预计使用天数告警" in message
        assert "预计使用天数: 6" in message
        assert "告警阈值: 7 天" in message
        assert "告警说明: 预计剩余可用天数低于阈值，请及时充值" in message

    def test_build_recharge_message_falls_back_to_raw_recharge_info(
        self,
        cloud_provider,
        alert_record,
    ):
        alert_record.alert_message = (
            "告警类型：预计使用天数告警\n"
            "当前余额：407.52 CNY\n"
            "预计使用天数：1598\n"
            "告警阈值：3000\n"
            "告警说明：预计使用天数低于设定阈值，请及时充值"
        )
        alert_record.alert_type = AlertRecord.ALERT_TYPE_DAYS_REMAINING
        alert_record.save(update_fields=["alert_message", "alert_type"])
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            alert_record=alert_record,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            trigger_reason="alert",
            status=RechargeApprovalRecord.STATUS_FAILED,
            status_message=(
                "Script exited 1: Request file is missing required field: "
                "amount"
            ),
            raw_recharge_info=(
                '{"recharge_account": "18017606559", '
                '"recharge_customer_name": "示例云科技有限公司", '
                '"amount": 358, "currency": "CNY", '
                '"payment_company": "示例云科技有限公司", '
                '"payment_way": "公司支付", '
                '"payment_type": "仅充值", '
                '"remit_method": "转账", '
                '"payment_note": "请尽快安排", '
                '"expected_date": "2026-04-25"}'
            ),
            request_payload={},
        )

        service = RechargeApprovalNotificationService()
        message = service._build_recharge_message(
            record,
            "failed",
            "zh-hans",
        )

        assert "**触发方式**: 告警触发（剩余天数不足（当前预计 6 天，阈值 7 天））" in message
        assert "**充值账号**: 18017606559" in message
        assert "**充值客户**: 示例云科技有限公司" in message
        assert "**付款金额**: 358 CNY" in message
        assert "**付款公司**: 示例云科技有限公司" in message
        assert "**支付方式**: 公司支付" in message
        assert "**付款类型**: 仅充值" in message
        assert "**付款方式**: 转账" in message
        assert "**期望到账时间**: 2026-04-25" in message
        assert (
            "**失败原因**: Script exited 1: Request file is missing "
            "required field: amount"
        ) in message

    def test_build_recharge_message_uses_balance_reason_for_balance_alert(
        self,
        cloud_provider,
        alert_record,
    ):
        alert_record.alert_type = AlertRecord.ALERT_TYPE_BALANCE
        alert_record.current_balance = Decimal("407.52")
        alert_record.balance_threshold = Decimal("500.00")
        alert_record.current_days_remaining = None
        alert_record.days_remaining_threshold = None
        alert_record.alert_message = "余额阈值告警"
        alert_record.save(
            update_fields=[
                "alert_type",
                "current_balance",
                "balance_threshold",
                "current_days_remaining",
                "days_remaining_threshold",
                "alert_message",
            ]
        )
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            alert_record=alert_record,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            raw_recharge_info='{"amount": 92, "recharge_account": "acct-1"}',
            request_payload={
                "amount": 92,
                "currency": "CNY",
                "recharge_account": "acct-1",
            },
        )

        service = RechargeApprovalNotificationService()
        message = service._build_recharge_message(
            record,
            "submitted",
            "zh-hans",
        )

        assert (
            "**触发方式**: 告警触发（余额不足（当前余额 407.52，阈值 500.00））"
            in message
        )

    def test_build_recharge_message_localizes_alert_reason_in_english(
        self,
        cloud_provider,
        alert_record,
    ):
        alert_record.alert_type = AlertRecord.ALERT_TYPE_DAYS_REMAINING
        alert_record.current_balance = Decimal("407.52")
        alert_record.balance_threshold = Decimal("3000.00")
        alert_record.current_days_remaining = Decimal("1598")
        alert_record.days_remaining_threshold = Decimal("3000")
        alert_record.alert_message = "Days remaining alert"
        alert_record.save(
            update_fields=[
                "alert_type",
                "current_balance",
                "balance_threshold",
                "current_days_remaining",
                "days_remaining_threshold",
                "alert_message",
            ]
        )
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            alert_record=alert_record,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            request_payload={
                "amount": 358,
                "currency": "CNY",
                "recharge_account": "18017606559",
            },
        )

        service = RechargeApprovalNotificationService()
        message = service._build_recharge_message(
            record,
            "submitted",
            "en",
        )

        assert (
            "**Trigger Source**: Alert Trigger (Days remaining below threshold "
            "(current estimate 1598 days, threshold 3000 days))"
            in message
        )

    def test_build_message_skips_empty_date_and_payee_remark(
        self,
        cloud_provider,
        user,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            triggered_by=user,
            triggered_by_username_snapshot=user.username,
            submitted_by=user,
            submitter_identifier="finance@example.com",
            resolved_submitter_user_id="ou_123",
            submitter_user_label="Finance Bot",
            request_payload={
                "recharge_customer_name": "示例云科技有限公司",
                "recharge_account": "acct-188",
                "amount": "188.50",
                "currency": "CNY",
                "payment_company": "示例云科技有限公司",
                "payment_way": "公司支付",
                "payment_type": "仅充值",
                "remit_method": "转账",
                "remark": (
                    "账户类型：对公账户\n"
                    "户名：示例收款有限公司\n"
                    "账号：0000 0000 0000 0000\n"
                    "银行：示例银行\n"
                    "银行地区：示例省/示例市\n"
                    "支行：示例银行示例支行"
                ),
                "payee": {
                    "account_name": "示例收款有限公司",
                    "bank_name": "示例银行",
                },
            },
        )

        service = RechargeApprovalNotificationService()
        message = service._build_recharge_message(
            record,
            "submitted",
            "zh-hans",
        )

        assert "**期望到账时间**" not in message
        assert "**备注**" not in message
        assert "  - 户名: 示例收款有限公司" in message

    def test_generate_feishu_payload_uses_interactive_card(
        self,
        cloud_provider,
        user,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            triggered_by=user,
            triggered_by_username_snapshot=user.username,
            submitted_by=user,
            submitter_identifier="finance@example.com",
            resolved_submitter_user_id="ou_123",
            submitter_user_label="Finance Bot",
            request_payload={
                "recharge_customer_name": "示例云科技有限公司",
                "recharge_account": "acct-188",
                "amount": "188.50",
                "currency": "CNY",
                "payment_company": "示例云科技有限公司",
                "payment_way": "公司支付",
                "payment_type": "仅充值",
                "remit_method": "转账",
            },
        )

        service = RechargeApprovalNotificationService()
        payload = service._generate_feishu_payload(
            record,
            "submitted",
            "zh-hans",
            current_approvers=[
                "Approver A（审批节点 A）",
                "Approver B（审批节点 B）",
            ],
        )

        assert payload["msg_type"] == "interactive"
        assert payload["card"]["header"]["title"]["content"] == (
            "【充值审批】提交成功"
        )
        elements = payload["card"]["elements"]
        assert len(elements) == 1
        assert elements[0]["tag"] == "div"
        assert elements[0]["text"]["tag"] == "lark_md"
        assert elements[0]["text"]["content"].startswith(
            "**触发方式**: 人工触发"
        )
        assert "\n\n" not in elements[0]["text"]["content"]
        assert "**付款金额**: 188.50 CNY" in elements[0]["text"]["content"]
        expected_approvers = (
            "**当前审批人**: "
            "Approver A（审批节点 A）、Approver B（审批节点 B）"
        )
        assert (
            expected_approvers in elements[0]["text"]["content"]
        )

    def test_submitted_group_card_shows_auto_notice_and_current_approver(
        self,
        alert_record,
    ):
        """Auto approval notice and live approver should share one card."""
        alert_record.alert_message = (
            "告警类型：余额阈值告警\n"
            "充值审批：已自动触发充值审批，"
            "请关注审批进度"
        )
        alert_record.save(update_fields=["alert_message"])
        record = RechargeApprovalRecord.objects.create(
            provider=alert_record.provider,
            alert_record=alert_record,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            request_payload={
                "recharge_account": "acct-188",
                "amount": "188.50",
                "currency": "CNY",
            },
        )

        service = RechargeApprovalNotificationService()
        payload = service._generate_feishu_payload(
            record,
            "submitted",
            "zh-hans",
            current_approvers=["Approver A（审批节点 A）"],
        )

        content = payload["card"]["elements"][0]["text"]["content"]
        assert "已自动触发充值审批，请关注审批进度" in content
        assert "**当前审批人**: Approver A（审批节点 A）" in content

    def test_balance_recovery_group_card_shows_amount_and_live_flow(
        self,
        cloud_provider,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            request_payload={
                "recharge_account": "acct-188",
                "amount": "500.00",
                "currency": "CNY",
            },
            context_payload={
                "notification_message": "旧的提交成功通知",
            },
            fulfillment_status=(
                RechargeApprovalRecord.FULFILLMENT_RECOVERED
            ),
            fulfillment_evidence={
                "signal": "balance_threshold_recovered",
                "baseline_balance": "100.00",
                "observed_balance": "520.00",
                "estimated_recharge_amount": "420.00",
            },
        )

        payload = (
            RechargeApprovalNotificationService()
            ._generate_feishu_payload(
                record,
                "fulfillment_recovered",
                "zh-hans",
                current_approvers=["Approver A（审批节点 A）"],
            )
        )
        content = payload["card"]["elements"][0]["text"]["content"]

        assert payload["card"]["header"]["title"]["content"] == (
            "【充值审批】检测到充值到账"
        )
        assert "**充值前余额**: 100.00 CNY" in content
        assert "**当前余额**: 520.00 CNY" in content
        assert "**推定充值金额**: 420.00 CNY" in content
        assert "**审批流程**: 仍在审批" in content
        assert "**当前审批人**: Approver A（审批节点 A）" in content

        record.status = RechargeApprovalRecord.STATUS_APPROVED
        finished_payload = (
            RechargeApprovalNotificationService()
            ._generate_feishu_payload(
                record,
                "fulfillment_recovered",
                "zh-hans",
            )
        )
        finished_content = finished_payload["card"]["elements"][0][
            "text"
        ]["content"]
        assert "**审批流程**: 已结束" in finished_content

    @patch(
        "cloud_billing.services.notification_service."
        "_get_feishu_access_token",
        return_value="tenant-token",
    )
    @patch(
        "cloud_billing.services.notification_service."
        "urllib.request.urlopen"
    )
    def test_send_submitter_copy_uses_resolved_feishu_user_id(
        self,
        mocked_urlopen,
        mocked_get_token,
        cloud_provider,
    ):
        response = Mock()
        response.read.return_value = json.dumps(
            {
                "code": 0,
                "msg": "success",
                "data": {"message_id": "om_123"},
            }
        ).encode("utf-8")
        mocked_urlopen.return_value.__enter__.return_value = response
        BillingData.objects.create(
            provider=cloud_provider,
            period="2026-07",
            day=date(2026, 7, 13),
            hour=11,
            total_cost=Decimal("112.50"),
            hourly_cost=Decimal("12.50"),
            balance=Decimal("67.50"),
            currency="CNY",
            service_costs={"智谱 AI": "72.50"},
            account_id="acct-188",
        )
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            resolved_submitter_user_id="ou_submitter",
            submitter_user_label="Finance",
            feishu_instance_code="ins_188",
            request_payload={
                "recharge_customer_name": "示例云科技有限公司",
                "recharge_account": "acct-188",
                "amount": "188.50",
                "currency": "CNY",
                "payment_company": "示例云科技有限公司",
                "payment_way": "公司支付",
                "remit_method": "转账",
            },
        )

        result = RechargeApprovalNotificationService().send_submitter_copy(
            record,
            "submitted",
        )

        assert result == {
            "success": True,
            "skipped": False,
            "recipient_user_id": "ou_submitter",
            "message_id": "om_123",
            "error": None,
        }
        mocked_get_token.assert_called_once_with()
        request = mocked_urlopen.call_args.args[0]
        assert request.full_url.endswith(
            "/open-apis/im/v1/messages?receive_id_type=user_id"
        )
        assert request.headers["Authorization"] == "Bearer tenant-token"
        body = json.loads(request.data.decode("utf-8"))
        assert body["receive_id"] == "ou_submitter"
        assert body["msg_type"] == "interactive"
        first_message_uuid = body["uuid"]
        RechargeApprovalNotificationService().send_submitter_copy(
            record,
            "submitted",
        )
        second_request = mocked_urlopen.call_args.args[0]
        second_body = json.loads(second_request.data.decode("utf-8"))
        assert second_body["uuid"] == first_message_uuid
        card = json.loads(body["content"])
        assert card["header"]["title"]["content"] == (
            "【充值审批】提交成功"
        )
        card_text = json.dumps(card, ensure_ascii=False)
        visible_text = json.dumps(
            card["elements"][:-1],
            ensure_ascii=False,
        )
        assert "Tower 平台自动发起了一个审批流程" in visible_text
        assert "充值信息" in card_text
        assert "**充值账号**: acct-188" in card_text
        assert "**审批发起人**: Finance" in visible_text
        assert "ou_submitter" not in visible_text
        assert visible_text.count("示例云科技有限公司") == 1
        assert "**支付方式**: 公司支付 / 转账" in visible_text
        assert "**付款公司**" not in visible_text
        assert "**付款方式**" not in visible_text
        assert "账单概述" in card_text
        assert "67.50 CNY" in card_text
        assert "112.50 CNY" in card_text
        assert "审批实例" in card_text
        assert "查看审批单" in card_text
        assert "最新采集时间" not in visible_text
        assert "触发方式" not in card_text
        assert "收款信息" not in card_text

    @patch(
        "cloud_billing.services.notification_service."
        "_get_feishu_access_token"
    )
    def test_send_submitter_copy_skips_missing_user_id(
        self,
        mocked_get_token,
        cloud_provider,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
        )

        result = RechargeApprovalNotificationService().send_submitter_copy(
            record,
            "submitted",
        )

        assert result["success"] is True
        assert result["skipped"] is True
        assert result["recipient_user_id"] == ""
        mocked_get_token.assert_not_called()

    @patch(
        "cloud_billing.services.notification_service."
        "_get_feishu_access_token",
        return_value="tenant-token",
    )
    @patch(
        "cloud_billing.services.notification_service."
        "urllib.request.urlopen"
    )
    def test_send_submitter_copy_reports_feishu_api_error(
        self,
        mocked_urlopen,
        _mocked_get_token,
        cloud_provider,
    ):
        response = Mock()
        response.read.return_value = json.dumps(
            {"code": 230002, "msg": "bot has no permission"}
        ).encode("utf-8")
        mocked_urlopen.return_value.__enter__.return_value = response
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            resolved_submitter_user_id="ou_submitter",
        )

        result = RechargeApprovalNotificationService().send_submitter_copy(
            record,
            "submitted",
        )

        assert result["success"] is False
        assert result["skipped"] is False
        assert result["recipient_user_id"] == "ou_submitter"
        assert result["message_id"] == ""
        assert result["error"] == (
            "Feishu message API error 230002: bot has no permission"
        )

    @patch(
        "cloud_billing.services.notification_service."
        "_get_feishu_access_token",
        return_value="tenant-token",
    )
    @patch(
        "cloud_billing.services.notification_service."
        "urllib.request.urlopen"
    )
    def test_send_submitter_copy_rejects_response_without_success_code(
        self,
        mocked_urlopen,
        _mocked_get_token,
        cloud_provider,
    ):
        response = Mock()
        response.read.return_value = b"{}"
        mocked_urlopen.return_value.__enter__.return_value = response
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            resolved_submitter_user_id="user-submitter",
        )

        result = RechargeApprovalNotificationService().send_submitter_copy(
            record,
            "submitted",
        )

        assert result["success"] is False
        assert result["message_id"] == ""
        assert "missing success code" in result["error"]

    def test_approver_reminder_content_is_action_oriented(
        self,
        cloud_provider,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            request_payload={
                "recharge_account": "account-188",
                "amount": 500,
                "currency": "CNY",
            },
            resolved_submitter_user_id="user-submitter",
            submitter_user_label="Test Initiator",
            feishu_instance_code="instance-188",
        )
        service = RechargeApprovalNotificationService()

        payload = service._generate_approver_reminder_payload(
            record,
            node_name="财务审批",
        )
        content = payload["card"]["elements"][0]["text"]["content"]
        card_text = json.dumps(payload["card"], ensure_ascii=False)

        assert payload["card"]["header"]["title"]["content"] == (
            "【待审批】云账单充值申请"
        )
        assert "你有一笔云账单充值审批需要处理" in content
        assert "account-188" in content
        assert "500 CNY" in content
        assert "Test Initiator" in content
        assert "财务审批" in card_text
        assert "instance-188" in card_text
        assert "查看审批单" in card_text

    def test_approver_reminder_has_distinct_direct_message_sections(
        self,
        cloud_provider,
    ):
        BillingData.objects.create(
            provider=cloud_provider,
            period="2026-07",
            day=date(2026, 7, 13),
            hour=10,
            total_cost=Decimal("100.00"),
            hourly_cost=Decimal("8.00"),
            balance=Decimal("80.00"),
            currency="CNY",
            service_costs={"智谱 AI": "60.00", "对象存储": "40.00"},
            account_id="account-188",
        )
        BillingData.objects.create(
            provider=cloud_provider,
            period="2026-07",
            day=date(2026, 7, 13),
            hour=11,
            total_cost=Decimal("112.50"),
            hourly_cost=Decimal("12.50"),
            balance=Decimal("67.50"),
            currency="CNY",
            service_costs={"智谱 AI": "72.50", "对象存储": "40.00"},
            account_id="account-188",
        )
        alert = AlertRecord.objects.create(
            provider=cloud_provider,
            alert_type=AlertRecord.ALERT_TYPE_BALANCE,
            current_cost=Decimal("12.50"),
            previous_cost=Decimal("8.00"),
            increase_cost=Decimal("4.50"),
            increase_percent=Decimal("56.25"),
            currency="CNY",
            current_balance=Decimal("67.50"),
            balance_threshold=Decimal("100.00"),
            alert_message="余额不足",
        )
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            alert_record=alert,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            request_payload={
                "recharge_customer_name": "示例云科技有限公司",
                "recharge_account": "account-188",
                "amount": 500,
                "currency": "CNY",
                "payment_company": "示例云科技有限公司",
                "payment_way": "公司支付",
                "remit_method": "转账",
                "expected_date": "2026-07-20",
            },
            context_payload={"billing_account_id": "account-188"},
            submitter_user_label="Test Initiator",
            feishu_instance_code="instance-188",
        )

        payload = (
            RechargeApprovalNotificationService()
            ._generate_approver_reminder_payload(
                record,
                node_name="财务审批",
            )
        )
        card_text = json.dumps(payload["card"], ensure_ascii=False)
        visible_text = json.dumps(
            payload["card"]["elements"][:-1],
            ensure_ascii=False,
        )

        assert "充值信息" in card_text
        assert "示例云科技有限公司" in card_text
        assert visible_text.count("示例云科技有限公司") == 1
        assert "account-188" in card_text
        assert "500 CNY" in card_text
        assert "**支付方式**: 公司支付 / 转账" in visible_text
        assert "**付款公司**" not in visible_text
        assert "**付款方式**" not in visible_text
        assert "2026-07-20" in card_text
        assert "账单概述" in card_text
        assert "当前余额" in card_text
        assert "67.50 CNY" in card_text
        assert "余额阈值" in card_text
        assert "100.00 CNY" in card_text
        assert "近24小时消费" in card_text
        assert "20.50 CNY" in card_text
        assert "本月累计消费" in card_text
        assert "112.50 CNY" in card_text
        assert "最新采集时间" not in visible_text
        assert "智谱 AI" in card_text
        assert "审批实例" in card_text
        assert "财务审批" in card_text
        assert "查看审批单" in card_text
        assert "后续流程" not in card_text

    def test_direct_card_uses_days_remaining_alert_metrics(
        self,
        cloud_provider,
    ):
        BillingData.objects.create(
            provider=cloud_provider,
            period="2026-07",
            day=date(2026, 7, 13),
            hour=11,
            total_cost=Decimal("112.50"),
            hourly_cost=Decimal("12.50"),
            balance=Decimal("67.50"),
            currency="CNY",
            account_id="account-days",
        )
        alert = AlertRecord.objects.create(
            provider=cloud_provider,
            alert_type=AlertRecord.ALERT_TYPE_DAYS_REMAINING,
            current_cost=Decimal("12.50"),
            previous_cost=Decimal("8.00"),
            increase_cost=Decimal("4.50"),
            increase_percent=Decimal("56.25"),
            currency="CNY",
            current_days_remaining=6,
            days_remaining_threshold=7,
            alert_message="剩余天数不足",
        )
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            alert_record=alert,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            request_payload={
                "recharge_account": "account-days",
                "amount": 500,
                "currency": "CNY",
            },
            context_payload={"billing_account_id": "account-days"},
            feishu_instance_code="instance-days",
        )

        payload = (
            RechargeApprovalNotificationService()
            ._generate_approver_reminder_payload(
                record,
                node_name="财务审批",
            )
        )
        card_text = json.dumps(payload["card"], ensure_ascii=False)

        assert "当前剩余天数" in card_text
        assert "6 天" in card_text
        assert "剩余天数阈值" in card_text
        assert "7 天" in card_text
        assert "余额阈值" not in card_text

    def test_approver_escalation_card_shows_balance_urgency(
        self,
        cloud_provider,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            request_payload={
                "recharge_account": "acct-188",
                "amount": 500,
                "currency": "CNY",
            },
            feishu_instance_code="instance-escalation",
        )

        payload = (
            RechargeApprovalNotificationService()
            ._generate_approver_reminder_payload(
                record,
                node_name="财务审批",
                escalation_context={
                    "level": 30,
                    "current_balance": "25.00",
                    "balance_threshold": "100.00",
                    "balance_ratio": "25.00",
                    "currency": "CNY",
                },
            )
        )
        card_text = json.dumps(payload["card"], ensure_ascii=False)

        assert payload["card"]["header"]["title"]["content"] == (
            "【紧急催办】云账单充值审批"
        )
        assert "余额已低于阈值的 30%" in card_text
        assert "当前余额" in card_text
        assert "25.00 CNY" in card_text
        assert "余额阈值" in card_text
        assert "100.00 CNY" in card_text
        assert "余额占比" in card_text
        assert "25.00%" in card_text
        assert "财务审批" in card_text
        assert "查看审批单" in card_text

        warning_payload = (
            RechargeApprovalNotificationService()
            ._generate_approver_reminder_payload(
                record,
                node_name="财务审批",
                escalation_context={
                    "level": 50,
                    "current_balance": "40.00",
                    "balance_threshold": "100.00",
                    "balance_ratio": "40.00",
                    "currency": "CNY",
                },
            )
        )
        warning_text = json.dumps(
            warning_payload["card"],
            ensure_ascii=False,
        )

        assert warning_payload["card"]["header"] == {
            "title": {
                "tag": "plain_text",
                "content": "【余额告急】云账单充值审批",
            },
            "template": "yellow",
        }
        assert "余额已低于阈值的 50%" in warning_text
        assert "40.00%" in warning_text

    def test_approver_reminder_links_to_feishu_approval_instance(
        self,
        cloud_provider,
    ):
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            request_payload={
                "recharge_account": "account-188",
                "amount": 500,
                "currency": "CNY",
            },
            feishu_instance_code="instance-188",
        )

        payload = (
            RechargeApprovalNotificationService()
            ._generate_approver_reminder_payload(
                record,
                node_name="财务审批",
            )
        )
        action = payload["card"]["elements"][-1]
        button = action["actions"][0]

        assert action["tag"] == "action"
        assert button["tag"] == "button"
        assert button["text"]["content"] == "查看审批单"
        assert button["type"] == "primary"
        assert "behaviors" not in button
        open_url = button["multi_url"]
        assert open_url["url"] == (
            "https://applink.feishu.cn/client/mini_program/open?"
            "appId=cli_9cb844403dbb9108&"
            "path=pages%2Fdetail%2Findex%3FinstanceId%3Dinstance-188"
        )
        assert open_url["pc_url"] == (
            "https://applink.feishu.cn/client/mini_program/open?"
            "mode=appCenter&appId=cli_9cb844403dbb9108&"
            "path=pc%2Fpages%2Fin-process%2Findex%3F"
            "instanceId%3Dinstance-188"
        )

    def test_approver_report_does_not_fallback_to_another_account(
        self,
        cloud_provider,
    ):
        BillingData.objects.create(
            provider=cloud_provider,
            period="2026-07",
            day=date(2026, 7, 13),
            hour=11,
            total_cost=Decimal("999.00"),
            hourly_cost=Decimal("99.00"),
            balance=Decimal("888.00"),
            currency="CNY",
            account_id="another-account",
        )
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            request_payload={
                "recharge_account": "target-account",
                "amount": 500,
                "currency": "CNY",
            },
            feishu_instance_code="instance-target",
        )

        payload = (
            RechargeApprovalNotificationService()
            ._generate_approver_reminder_payload(
                record,
                node_name="财务审批",
            )
        )
        card_text = json.dumps(payload["card"], ensure_ascii=False)

        assert "暂无该云账号的使用记录" in card_text
        assert "another-account" not in card_text
        assert "888.00 CNY" not in card_text

    @patch(
        "cloud_billing.services.notification_service."
        "_get_feishu_access_token",
        return_value="tenant-token",
    )
    @patch(
        "cloud_billing.services.notification_service."
        "urllib.request.urlopen"
    )
    def test_approver_reminder_uses_stable_feishu_message_uuid(
        self,
        mocked_urlopen,
        _mocked_get_token,
        cloud_provider,
    ):
        response = Mock()
        response.read.return_value = json.dumps(
            {
                "code": 0,
                "msg": "success",
                "data": {"message_id": "message-188"},
            }
        ).encode("utf-8")
        mocked_urlopen.return_value.__enter__.return_value = response
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            feishu_instance_code="instance-188",
        )
        service = RechargeApprovalNotificationService()

        service.send_approver_reminder(
            record,
            recipient_user_id="user-finance",
            node_name="财务审批",
        )
        first_request = mocked_urlopen.call_args.args[0]
        first_body = json.loads(first_request.data.decode("utf-8"))
        service.send_approver_reminder(
            record,
            recipient_user_id="user-finance",
            node_name="财务审批",
        )
        second_request = mocked_urlopen.call_args.args[0]
        second_body = json.loads(second_request.data.decode("utf-8"))

        assert first_body["uuid"] == second_body["uuid"]
        assert len(first_body["uuid"]) <= 50

    @patch("cloud_billing.services.notification_service.send_notification.run")
    @patch(
        "cloud_billing.services.notification_service.get_webhook_channel_by_uuid"
    )
    def test_send_recharge_notification_sync_uses_run(
        self,
        mocked_get_channel,
        mocked_run,
        cloud_provider,
        user,
    ):
        channel = Mock()
        channel.uuid = "channel-uuid"
        channel.config = {"language": "zh-hans"}
        mocked_get_channel.return_value = (channel, {"provider": "feishu"})
        mocked_run.return_value = {
            "success": True,
            "response": {"ok": True},
            "error": None,
        }

        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
            triggered_by=user,
            triggered_by_username_snapshot=user.username,
            submitted_by=user,
            request_payload={
                "recharge_customer_name": "示例云科技有限公司",
                "recharge_account": "acct-188",
                "amount": "188.50",
                "currency": "CNY",
                "payment_company": "示例云科技有限公司",
                "payment_way": "公司支付",
                "payment_type": "仅充值",
                "remit_method": "转账",
            },
        )

        service = RechargeApprovalNotificationService()
        result = service.send_recharge_notification(
            record,
            "submitted",
            channel_uuid="channel-uuid",
            synchronous=True,
        )

        assert result["success"] is True
        mocked_get_channel.assert_called_once_with("channel-uuid")
        mocked_run.assert_called_once()
        assert mocked_run.call_args.kwargs["notification_type"] == "webhook"
        assert mocked_run.call_args.kwargs["channel_uuid"] == "channel-uuid"
        assert mocked_run.call_args.kwargs["params"]["provider_type"] == "feishu"
