"""
Tests for WebhookService.

These tests focus on the generic webhook notification functionality
without business-specific logic.
"""
import pytest
from unittest.mock import Mock, patch

from notifier.services.webhook_service import WebhookService


class TestWebhookService:
    """
    Tests for WebhookService.
    """

    @patch('notifier.services.webhook_service.get_config')
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

    @patch('notifier.services.webhook_service.get_config')
    def test_load_config_not_active(self, mock_get_config):
        """
        Test loading inactive webhook config.
        """
        mock_config = {'is_active': False}
        mock_get_config.return_value = mock_config

        service = WebhookService()
        assert service.webhook_config is None

    @patch('notifier.services.webhook_service.get_config')
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

    @patch('notifier.services.webhook_service.requests.post')
    @patch('notifier.services.webhook_service.WebhookService._load_config')
    def test_send_feishu_success(
        self,
        mock_load_config,
        mock_post
    ):
        """
        Test sending Feishu message successfully.
        """
        mock_config = {
            'is_active': True,
            'url': 'https://open.feishu.cn/open-apis/bot/v2/hook/test',
            'provider': 'feishu',
            'timeout': 10
        }
        mock_load_config.return_value = None
        service = WebhookService()
        service.webhook_config = mock_config

        mock_response = Mock()
        mock_response.json.return_value = {'code': 0}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        payload = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh-hans": {
                        "title": "Test Title",
                        "content": [
                            [{"tag": "text", "text": "Test message"}]
                        ]
                    }
                }
            }
        }

        result = service.send_feishu(payload)
        assert result['success'] is True
        assert result['error'] is None
        mock_post.assert_called_once()

    @patch('notifier.services.webhook_service.requests.post')
    @patch('notifier.services.webhook_service.WebhookService._load_config')
    def test_send_wechat_success(
        self,
        mock_load_config,
        mock_post
    ):
        """
        Test sending WeChat message successfully.
        """
        mock_config = {
            'is_active': True,
            'url': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send',
            'provider': 'wechat',
            'timeout': 10
        }
        mock_load_config.return_value = None
        service = WebhookService()
        service.webhook_config = mock_config

        mock_response = Mock()
        mock_response.json.return_value = {'errcode': 0}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": "## Test\n\nTest message"
            }
        }

        result = service.send_wechat(payload)
        assert result['success'] is True
        assert result['error'] is None
        mock_post.assert_called_once()

    def test_send_with_provider_type(self):
        """
        Test send method with provider type.
        """
        service = WebhookService()
        service.webhook_config = {
            'is_active': True,
            'url': 'https://test.com/webhook',
            'provider': 'feishu'
        }

        payload = {
            "msg_type": "post",
            "content": {"post": {}}
        }

        with patch.object(
            service, 'send_feishu'
        ) as mock_send_feishu:
            mock_send_feishu.return_value = {
                'success': True,
                'response': {},
                'error': None
            }
            result = service.send(payload, provider_type='feishu')
            assert result['success'] is True
            mock_send_feishu.assert_called_once_with(payload)

    def test_send_without_config(self):
        """
        Test send method without webhook config.
        """
        service = WebhookService()
        service.webhook_config = None

        payload = {"msg_type": "post"}
        result = service.send(payload)
        assert result['success'] is False
        assert 'not found' in result['error'].lower()

    def test_send_unsupported_provider(self):
        """
        Test send method with unsupported provider type.
        """
        service = WebhookService()
        service.webhook_config = {
            'is_active': True,
            'url': 'https://test.com/webhook',
            'provider': 'feishu'
        }

        payload = {"msg_type": "post"}
        result = service.send(payload, provider_type='unsupported')
        assert result['success'] is False
        assert 'Unsupported' in result['error']
