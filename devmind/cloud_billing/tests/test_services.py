"""
Tests for cloud billing services.
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from cloud_billing.services.notification_service import (
    CloudBillingNotificationService
)
from cloud_billing.services.provider_service import ProviderService
from cloud_billing.models import CloudProvider, AlertRecord


@pytest.mark.django_db
class TestProviderService:
    """
    Tests for ProviderService.
    """

    @patch('cloud_billing.services.provider_service.ProviderFactory')
    def test_create_provider_success(self, mock_factory):
        """
        Test creating a provider successfully.
        Service normalizes config (e.g. api_key/api_secret for aws).
        """
        mock_provider_instance = Mock()
        mock_factory.create_provider.return_value = mock_provider_instance

        service = ProviderService()
        result = service.create_provider(
            'aws',
            {'api_key': 'test', 'api_secret': 'test'}
        )

        assert result == mock_provider_instance
        mock_factory.create_provider.assert_called_once_with(
            'aws',
            {'api_key': 'test', 'api_secret': 'test'}
        )

    @patch('cloud_billing.services.provider_service.ProviderFactory')
    def test_create_provider_import_error(self, mock_factory):
        """
        Test that ImportError from factory is propagated.
        """
        mock_factory.create_provider.side_effect = ImportError(
            'No module named cloud_billings'
        )

        service = ProviderService()
        with pytest.raises(ImportError, match='cloud_billings'):
            service.create_provider('aws', {})

    @patch('cloud_billing.services.provider_service.BillingService')
    def test_get_billing_info_success(self, mock_billing_service):
        """
        Test getting billing info successfully.
        """
        mock_instance = Mock()
        mock_instance.get_billing_info.return_value = {
            'status': 'success',
            'data': {
                'total_cost': 100.50,
                'currency': 'USD',
                'service_costs': {'ec2': 50.00}
            }
        }
        mock_billing_service.return_value = mock_instance

        service = ProviderService()
        result = service.get_billing_info(
            'aws',
            {'access_key': 'test', 'secret_key': 'test'},
            period='2025-01'
        )

        assert result['status'] == 'success'
        assert 'data' in result

    @patch('cloud_billing.services.provider_service.BillingService')
    def test_get_billing_info_error(self, mock_billing_service):
        """
        Test handling errors when getting billing info.
        """
        mock_billing_service.side_effect = Exception('API Error')

        service = ProviderService()
        with pytest.raises(Exception):
            service.get_billing_info('aws', {}, period='2025-01')

    @patch('cloud_billing.services.provider_service.ProviderService.create_provider')
    def test_validate_credentials_success(self, mock_create_provider):
        """
        Test validating credentials successfully.
        Implementation returns valid, error_code, account_id (no message).
        """
        mock_provider = Mock()
        mock_provider.validate_credentials.return_value = True
        mock_provider.get_account_id.return_value = '123456789012'
        mock_create_provider.return_value = mock_provider

        service = ProviderService()
        result = service.validate_credentials(
            'aws',
            {'api_key': 'test', 'api_secret': 'test'}
        )

        assert result['valid'] is True
        assert result['account_id'] == '123456789012'
        assert result.get('error_code') is None

    @patch('cloud_billing.services.provider_service.ProviderService.create_provider')
    def test_validate_credentials_invalid(self, mock_create_provider):
        """
        Test validating invalid credentials.
        """
        mock_provider = Mock()
        mock_provider.validate_credentials.return_value = False
        mock_create_provider.return_value = mock_provider

        service = ProviderService()
        result = service.validate_credentials(
            'aws',
            {'api_key': 'invalid', 'api_secret': 'invalid'}
        )

        assert result['valid'] is False
        assert result['account_id'] == ''
        assert result.get('error_code') == 'validation_failed'

    @patch('cloud_billing.services.provider_service.ProviderService.create_provider')
    def test_validate_credentials_exception(self, mock_create_provider):
        """
        Test handling exceptions during credential validation.
        Exception path returns error_code (e.g. network_error).
        """
        mock_create_provider.side_effect = Exception('Connection error')

        service = ProviderService()
        result = service.validate_credentials('aws', {})

        assert result['valid'] is False
        assert result.get('error_code') == 'network_error'

    @patch('cloud_billing.services.provider_service.ProviderService.create_provider')
    def test_get_account_id_success(self, mock_create_provider):
        """
        Test getting account ID successfully.
        """
        mock_provider = Mock()
        mock_provider.get_account_id.return_value = '123456789012'
        mock_create_provider.return_value = mock_provider

        service = ProviderService()
        result = service.get_account_id(
            'aws',
            {'access_key': 'test', 'secret_key': 'test'}
        )

        assert result == '123456789012'

    @patch('cloud_billing.services.provider_service.ProviderService.create_provider')
    def test_get_account_id_error(self, mock_create_provider):
        """
        Test handling errors when getting account ID.
        """
        mock_provider = Mock()
        mock_provider.get_account_id.side_effect = Exception('API Error')
        mock_create_provider.return_value = mock_provider

        service = ProviderService()
        with pytest.raises(Exception):
            service.get_account_id('aws', {})


@pytest.mark.django_db
class TestCloudBillingNotificationService:
    """
    Tests for CloudBillingNotificationService.

    These tests focus on the business logic of converting
    cloud billing data to notification format.
    """

    @patch(
        'cloud_billing.services.notification_service.send_notification'
    )
    @patch(
        'cloud_billing.services.notification_service.get_webhook_channel_by_uuid'
    )
    def test_send_alert_feishu(
        self,
        mock_get_by_uuid,
        mock_send_task,
        alert_record
    ):
        """
        Test sending alert via Feishu (enqueues unified send_notification with webhook params).
        """
        from uuid import uuid4
        ch_uuid = uuid4()
        mock_channel = type('Channel', (), {
            'uuid': ch_uuid,
            'config': {'language': 'zh-hans'},
        })()
        mock_config = {'is_active': True, 'provider': 'feishu'}
        mock_get_by_uuid.return_value = (mock_channel, mock_config)

        service = CloudBillingNotificationService()
        result = service.send_alert(alert_record, channel_uuid=str(ch_uuid))

        assert result['success'] is True
        mock_send_task.delay.assert_called_once()
        call_kwargs = mock_send_task.delay.call_args[1]
        assert call_kwargs['notification_type'] == 'webhook'
        assert call_kwargs['channel_uuid'] == str(ch_uuid)
        params = call_kwargs['params']
        assert params['provider_type'] == 'feishu'
        payload = params['payload']
        assert payload['msg_type'] == 'post'
        assert 'content' in payload
        assert 'post' in payload['content']
        assert call_kwargs['source_app'] == 'cloud_billing'
        assert call_kwargs['source_type'] == 'alert'
        assert str(alert_record.id) == call_kwargs['source_id']

    @patch(
        'cloud_billing.services.notification_service.send_notification'
    )
    @patch(
        'cloud_billing.services.notification_service.get_webhook_channel_by_uuid'
    )
    def test_send_alert_wechat(
        self,
        mock_get_by_uuid,
        mock_send_task,
        alert_record
    ):
        """
        Test sending alert via WeChat (enqueues unified send_notification with webhook params).
        """
        from uuid import uuid4
        ch_uuid = uuid4()
        mock_channel = type('Channel', (), {
            'uuid': ch_uuid,
            'config': {'language': 'zh-hans'},
        })()
        mock_config = {'is_active': True, 'provider': 'wechat'}
        mock_get_by_uuid.return_value = (mock_channel, mock_config)

        service = CloudBillingNotificationService()
        result = service.send_alert(alert_record, channel_uuid=str(ch_uuid))

        assert result['success'] is True
        mock_send_task.delay.assert_called_once()
        call_kwargs = mock_send_task.delay.call_args[1]
        assert call_kwargs['notification_type'] == 'webhook'
        assert call_kwargs['channel_uuid'] == str(ch_uuid)
        params = call_kwargs['params']
        assert params['provider_type'] == 'wechat'
        payload = params['payload']
        assert payload['msgtype'] == 'markdown'
        assert 'markdown' in payload
        assert 'content' in payload['markdown']

    @patch(
        'cloud_billing.services.notification_service.send_notification'
    )
    @patch(
        'cloud_billing.services.notification_service.get_default_webhook_channel'
    )
    def test_send_alert_uses_default_when_channel_uuid_is_none(
        self,
        mock_get_default,
        mock_send_task,
        alert_record,
    ):
        """
        When channel_uuid is None, use notifier default (get_default_webhook_channel).
        Unified task is called with channel_uuid=None; notifier resolves default.
        """
        mock_channel = type('Channel', (), {
            'uuid': __import__('uuid').uuid4(),
            'config': {'language': 'zh-hans'},
        })()
        mock_config = {'is_active': True, 'provider': 'feishu'}
        mock_get_default.return_value = (mock_channel, mock_config)

        service = CloudBillingNotificationService()
        result = service.send_alert(alert_record, channel_uuid=None)

        assert result['success'] is True
        mock_send_task.delay.assert_called_once()
        call_kwargs = mock_send_task.delay.call_args[1]
        assert call_kwargs['notification_type'] == 'webhook'
        assert call_kwargs['channel_uuid'] == str(mock_channel.uuid)
        assert call_kwargs['params']['provider_type'] == 'feishu'

    @patch(
        'cloud_billing.services.notification_service.send_notification'
    )
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
            channel_type='email',
        )
        assert result['success'] is False
        assert 'channel_uuid is required' in result['error']
        mock_send_task.delay.assert_not_called()

    @patch(
        'cloud_billing.services.notification_service.get_default_webhook_channel'
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

        assert result['success'] is False
        assert 'not found' in result['error'].lower() or 'not active' in result['error'].lower()

    @patch(
        'cloud_billing.services.notification_service.send_notification'
    )
    @patch(
        'cloud_billing.services.notification_service.get_webhook_channel_by_uuid'
    )
    def test_send_alert_with_channel_uuid(
        self,
        mock_get_by_uuid,
        mock_send_task,
        alert_record
    ):
        """
        Test sending alert with channel_uuid; unified task receives channel_uuid and params.
        """
        from uuid import uuid4
        ch_uuid = uuid4()
        mock_channel = type('Channel', (), {
            'id': 1,
            'uuid': ch_uuid,
            'config': {'language': 'zh-hans'},
        })()
        mock_config = {'is_active': True, 'provider': 'feishu'}
        mock_get_by_uuid.return_value = (mock_channel, mock_config)

        service = CloudBillingNotificationService()
        result = service.send_alert(alert_record, channel_uuid=str(ch_uuid))

        assert result['success'] is True
        mock_send_task.delay.assert_called_once()
        call_kwargs = mock_send_task.delay.call_args[1]
        assert call_kwargs['notification_type'] == 'webhook'
        assert call_kwargs['channel_uuid'] == str(ch_uuid)
        assert call_kwargs['params']['provider_type'] == 'feishu'

    @patch(
        'cloud_billing.services.notification_service.get_webhook_channel_by_uuid'
    )
    def test_send_alert_channel_uuid_not_found(
        self,
        mock_get_by_uuid,
        alert_record
    ):
        """
        Test sending alert with channel_uuid that does not exist or is inactive.
        """
        mock_get_by_uuid.return_value = (None, None)

        service = CloudBillingNotificationService()
        result = service.send_alert(
            alert_record,
            channel_uuid='00000000-0000-0000-0000-000000000000',
        )

        assert result['success'] is False
        assert 'not found' in result['error'].lower() or 'inactive' in result['error'].lower()
