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
        """
        mock_provider_instance = Mock()
        mock_factory.create_provider.return_value = mock_provider_instance

        service = ProviderService()
        result = service.create_provider(
            'aws',
            {'access_key': 'test', 'secret_key': 'test'}
        )

        assert result == mock_provider_instance
        mock_factory.create_provider.assert_called_once_with(
            'aws',
            {'access_key': 'test', 'secret_key': 'test'}
        )

    @patch('cloud_billing.services.provider_service.ProviderFactory')
    def test_create_provider_import_error(self, mock_factory):
        """
        Test handling ImportError when provider factory is not available.
        """
        mock_factory.create_provider.side_effect = ImportError(
            'No module named cloud_billings'
        )

        service = ProviderService()
        with pytest.raises(ValueError, match='Unsupported provider type'):
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
        """
        mock_provider = Mock()
        mock_provider.validate_credentials.return_value = True
        mock_provider.get_account_id.return_value = '123456789012'
        mock_create_provider.return_value = mock_provider

        service = ProviderService()
        result = service.validate_credentials(
            'aws',
            {'access_key': 'test', 'secret_key': 'test'}
        )

        assert result['valid'] is True
        assert result['account_id'] == '123456789012'
        assert 'Credentials are valid' in result['message']

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
            {'access_key': 'invalid', 'secret_key': 'invalid'}
        )

        assert result['valid'] is False
        assert result['account_id'] == ''
        assert 'Invalid credentials' in result['message']

    @patch('cloud_billing.services.provider_service.ProviderService.create_provider')
    def test_validate_credentials_exception(self, mock_create_provider):
        """
        Test handling exceptions during credential validation.
        """
        mock_create_provider.side_effect = Exception('Connection error')

        service = ProviderService()
        result = service.validate_credentials('aws', {})

        assert result['valid'] is False
        assert 'Connection error' in result['message']

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
        'cloud_billing.services.notification_service.WebhookService'
    )
    def test_send_alert_feishu(
        self,
        mock_webhook_service_class,
        alert_record
    ):
        """
        Test sending alert via Feishu.
        """
        mock_webhook_service = Mock()
        mock_webhook_service_class.return_value = mock_webhook_service
        mock_webhook_service.get_webhook_config.return_value = {
            'is_active': True,
            'provider': 'feishu',
            'language': 'zh-hans'
        }
        mock_webhook_service.send.return_value = {
            'success': True,
            'response': {},
            'error': None
        }

        service = CloudBillingNotificationService()
        result = service.send_alert(alert_record)

        assert result['success'] is True
        mock_webhook_service.send.assert_called_once()
        call_args = mock_webhook_service.send.call_args
        assert call_args[0][1] == 'feishu'
        payload = call_args[0][0]
        # Verify Feishu payload format
        assert payload['msg_type'] == 'post'
        assert 'content' in payload
        assert 'post' in payload['content']

    @patch(
        'cloud_billing.services.notification_service.WebhookService'
    )
    def test_send_alert_wechat(
        self,
        mock_webhook_service_class,
        alert_record
    ):
        """
        Test sending alert via WeChat.
        """
        mock_webhook_service = Mock()
        mock_webhook_service_class.return_value = mock_webhook_service
        mock_webhook_service.get_webhook_config.return_value = {
            'is_active': True,
            'provider': 'wechat',
            'language': 'zh-hans'
        }
        mock_webhook_service.send.return_value = {
            'success': True,
            'response': {},
            'error': None
        }

        service = CloudBillingNotificationService()
        result = service.send_alert(alert_record)

        assert result['success'] is True
        mock_webhook_service.send.assert_called_once()
        call_args = mock_webhook_service.send.call_args
        assert call_args[0][1] == 'wechat'
        payload = call_args[0][0]
        # Verify WeChat payload format
        assert payload['msgtype'] == 'markdown'
        assert 'markdown' in payload
        assert 'content' in payload['markdown']

    @patch(
        'cloud_billing.services.notification_service.WebhookService'
    )
    def test_send_alert_no_config(
        self,
        mock_webhook_service_class,
        alert_record
    ):
        """
        Test sending alert without webhook config.
        """
        mock_webhook_service = Mock()
        mock_webhook_service_class.return_value = mock_webhook_service
        mock_webhook_service.get_webhook_config.return_value = None

        service = CloudBillingNotificationService()
        result = service.send_alert(alert_record)

        assert result['success'] is False
        assert 'not found' in result['error'].lower()
