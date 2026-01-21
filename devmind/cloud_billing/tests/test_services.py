"""
Tests for cloud billing services.
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from cloud_billing.services.provider_service import ProviderService
from cloud_billing.services.webhook_service import WebhookService
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
class TestWebhookService:
    """
    Tests for WebhookService.
    """

    @patch('cloud_billing.services.webhook_service.get_config')
    def test_load_config_success(self, mock_get_config):
        """
        Test loading webhook config successfully.
        """
        mock_config = {
            'is_active': True,
            'url': 'https://open.feishu.cn/open-apis/bot/v2/hook/test',
            'provider': 'feishu',
            'language': 'zh-hans'
        }
        mock_get_config.return_value = mock_config

        service = WebhookService()
        assert service.webhook_config == mock_config

    @patch('cloud_billing.services.webhook_service.get_config')
    def test_load_config_not_active(self, mock_get_config):
        """
        Test loading inactive webhook config.
        """
        mock_config = {'is_active': False}
        mock_get_config.return_value = mock_config

        service = WebhookService()
        assert service.webhook_config is None

    @patch('cloud_billing.services.webhook_service.get_config')
    def test_get_webhook_config(self, mock_get_config):
        """
        Test getting webhook config.
        """
        mock_config = {
            'is_active': True,
            'url': 'https://open.feishu.cn/open-apis/bot/v2/hook/test'
        }
        mock_get_config.return_value = mock_config

        service = WebhookService()
        result = service.get_webhook_config()
        assert result == mock_config

    @patch('cloud_billing.services.webhook_service.requests.post')
    @patch('cloud_billing.services.webhook_service.WebhookService._load_config')
    def test_send_feishu_alert_success(
        self,
        mock_load_config,
        mock_post
    ):
        """
        Test sending Feishu alert successfully.
        """
        mock_config = {
            'is_active': True,
            'url': 'https://open.feishu.cn/open-apis/bot/v2/hook/test',
            'language': 'zh-hans',
            'timeout': 10
        }
        mock_load_config.return_value = None

        mock_response = Mock()
        mock_response.json.return_value = {'code': 0}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        service = WebhookService()
        service.webhook_config = mock_config

        alert_data = {
            'provider_name': 'Test AWS',
            'current_cost': 100.50,
            'previous_cost': 80.00,
            'increase_cost': 20.50,
            'increase_percent': 25.63,
            'currency': 'USD',
            'language': 'zh-hans'
        }

        result = service.send_feishu_alert(alert_data)
        assert result['success'] is True
        assert 'response' in result

    @patch('cloud_billing.services.webhook_service.WebhookService._load_config')
    def test_send_feishu_alert_no_config(self, mock_load_config):
        """
        Test sending Feishu alert without config.
        """
        service = WebhookService()
        service.webhook_config = None

        alert_data = {
            'provider_name': 'Test AWS',
            'current_cost': 100.50,
            'previous_cost': 80.00,
            'increase_cost': 20.50,
            'increase_percent': 25.63,
            'currency': 'USD'
        }

        result = service.send_feishu_alert(alert_data)
        assert result['success'] is False
        assert 'error' in result

    @patch('cloud_billing.services.webhook_service.requests.post')
    def test_send_wechat_alert_success(self, mock_post):
        """
        Test sending WeChat alert successfully.
        """
        mock_config = {
            'is_active': True,
            'url': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test',
            'language': 'zh-hans',
            'timeout': 10
        }

        mock_response = Mock()
        mock_response.json.return_value = {'errcode': 0}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        service = WebhookService()
        service.webhook_config = mock_config

        alert_data = {
            'provider_name': 'Test AWS',
            'current_cost': 100.50,
            'previous_cost': 80.00,
            'increase_cost': 20.50,
            'increase_percent': 25.63,
            'currency': 'USD',
            'language': 'zh-hans'
        }

        result = service.send_wechat_alert(alert_data)
        assert result['success'] is True

    @patch('cloud_billing.services.webhook_service.WebhookService.send_feishu_alert')
    def test_send_alert_feishu(
        self,
        mock_send_feishu,
        alert_record
    ):
        """
        Test sending alert via Feishu.
        """
        mock_config = {
            'is_active': True,
            'provider': 'feishu',
            'language': 'zh-hans'
        }
        mock_send_feishu.return_value = {'success': True}

        service = WebhookService()
        service.webhook_config = mock_config

        result = service.send_alert(alert_record)
        assert result['success'] is True
        mock_send_feishu.assert_called_once()

    @patch('cloud_billing.services.webhook_service.WebhookService.send_wechat_alert')
    def test_send_alert_wechat(
        self,
        mock_send_wechat,
        alert_record
    ):
        """
        Test sending alert via WeChat.
        """
        mock_config = {
            'is_active': True,
            'provider': 'wechat',
            'language': 'zh-hans'
        }
        mock_send_wechat.return_value = {'success': True}

        service = WebhookService()
        service.webhook_config = mock_config

        result = service.send_alert(alert_record)
        assert result['success'] is True
        mock_send_wechat.assert_called_once()

    def test_send_alert_unsupported_provider(self, alert_record):
        """
        Test sending alert with unsupported provider type.
        """
        mock_config = {
            'is_active': True,
            'provider': 'unsupported',
            'language': 'zh-hans'
        }

        service = WebhookService()
        service.webhook_config = mock_config

        result = service.send_alert(alert_record)
        assert result['success'] is False
        assert 'Unsupported' in result['error']
