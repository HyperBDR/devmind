"""
Webhook service for sending billing alerts.
"""
import logging
from typing import Any, Dict, Optional

import requests

from app_config.utils import get_config

logger = logging.getLogger(__name__)


class WebhookService:
    """
    Service for sending webhook notifications.
    """

    def __init__(self):
        """
        Initialize webhook service.
        """
        self.webhook_config = None
        self._load_config()

    def _load_config(self):
        """
        Load webhook configuration from app_config.
        """
        try:
            config = get_config('webhook_config', default={})
            if isinstance(config, dict) and config.get('is_active', False):
                self.webhook_config = config
            else:
                logger.warning(
                    f"WebhookService._load_config: Webhook config not found "
                    f"or not active (config_key=webhook_config)"
                )
        except Exception as e:
            logger.error(
                f"WebhookService._load_config: Failed to load webhook config "
                f"(config_key=webhook_config, error={str(e)})"
            )

    def get_webhook_config(self) -> Optional[Dict[str, Any]]:
        """
        Get webhook configuration.

        Returns:
            Webhook configuration dictionary or None
        """
        if not self.webhook_config:
            self._load_config()
        return self.webhook_config

    def send_feishu_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send alert to Feishu webhook.

        Args:
            alert_data: Alert data dictionary containing:
                - provider_name: Cloud provider display name
                - current_cost: Current hour cost
                - previous_cost: Previous hour cost
                - increase_cost: Cost increase amount
                - increase_percent: Cost increase percentage
                - currency: Currency code
                - language: Message language (zh-hans/en)

        Returns:
            Dictionary with result: {success: bool, response: dict, error: str}
        """
        if not self.webhook_config:
            return {
                'success': False,
                'response': None,
                'error': 'Webhook config not found or not active'
            }

        webhook_url = self.webhook_config.get('url', '')
        if not webhook_url:
            return {
                'success': False,
                'response': None,
                'error': 'Webhook URL not configured'
            }

        language = alert_data.get(
            'language',
            self.webhook_config.get('language', 'zh-hans')
        )
        provider_name = alert_data.get('provider_name', 'Unknown')
        current_cost = alert_data.get('current_cost', 0)
        previous_cost = alert_data.get('previous_cost', 0)
        increase_cost = alert_data.get('increase_cost', 0)
        increase_percent = alert_data.get('increase_percent', 0)
        currency = alert_data.get('currency', 'USD')

        if language == 'zh-hans':
            title = "[重点关注]云平台账单消费提醒"
            message = (
                f"{provider_name} 账户在过去一小时的消费增长了 "
                f"{increase_cost:.2f} {currency}，"
                f"增长率为 {increase_percent:.2f}%\n"
                f"当前费用: {current_cost:.2f} {currency}\n"
                f"上一小时费用: {previous_cost:.2f} {currency}"
            )
        else:
            title = "[Important] Cloud Billing Alert"
            message = (
                f"{provider_name} account billing increased by "
                f"{increase_cost:.2f} {currency} in the last hour, "
                f"growth rate: {increase_percent:.2f}%\n"
                f"Current cost: {current_cost:.2f} {currency}\n"
                f"Previous hour cost: {previous_cost:.2f} {currency}"
            )

        payload = {
            "msg_type": "post",
            "content": {
                "post": {
                    language: {
                        "title": title,
                        "content": [
                            [{
                                "tag": "text",
                                "text": message
                            }, {
                                "tag": "at",
                                "user_id": "all"
                            }]
                        ]
                    }
                }
            }
        }

        try:
            timeout = self.webhook_config.get('timeout', 10)
            headers = {
                'Content-Type': 'application/json',
                **self.webhook_config.get('headers', {})
            }

            response = requests.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=timeout
            )

            response.raise_for_status()
            response_data = response.json()

            webhook_host = (
                webhook_url.split('/')[2] if '/' in webhook_url else 'unknown'
            )
            logger.info(
                f"WebhookService.send_feishu_alert: Feishu alert sent "
                f"successfully (provider_name={provider_name}, "
                f"webhook_host={webhook_host}, language={language}, "
                f"current_cost={current_cost}, previous_cost={previous_cost}, "
                f"increase_cost={increase_cost}, "
                f"increase_percent={increase_percent:.2f}, "
                f"currency={currency})"
            )
            return {
                'success': True,
                'response': response_data,
                'error': None
            }
        except requests.exceptions.RequestException as e:
            webhook_host = (
                webhook_url.split('/')[2] if '/' in webhook_url else 'unknown'
            )
            logger.error(
                f"WebhookService.send_feishu_alert: Failed to send Feishu "
                f"alert (provider_name={provider_name}, "
                f"webhook_host={webhook_host}, language={language}, "
                f"error={str(e)})"
            )
            return {
                'success': False,
                'response': None,
                'error': str(e)
            }

    def send_wechat_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send alert to WeChat Work webhook.

        Args:
            alert_data: Alert data dictionary

        Returns:
            Dictionary with result: {success: bool, response: dict, error: str}
        """
        if not self.webhook_config:
            return {
                'success': False,
                'response': None,
                'error': 'Webhook config not found or not active'
            }

        webhook_url = self.webhook_config.get('url', '')
        if not webhook_url:
            return {
                'success': False,
                'response': None,
                'error': 'Webhook URL not configured'
            }

        language = alert_data.get(
            'language',
            self.webhook_config.get('language', 'zh-hans')
        )
        provider_name = alert_data.get('provider_name', 'Unknown')
        current_cost = alert_data.get('current_cost', 0)
        previous_cost = alert_data.get('previous_cost', 0)
        increase_cost = alert_data.get('increase_cost', 0)
        increase_percent = alert_data.get('increase_percent', 0)
        currency = alert_data.get('currency', 'USD')

        if language == 'zh-hans':
            content = (
                f"## 云平台账单消费提醒\n\n"
                f"**{provider_name}** 账户在过去一小时的消费增长了 "
                f"**{increase_cost:.2f} {currency}**，"
                f"增长率为 **{increase_percent:.2f}%**\n\n"
                f"- 当前费用: {current_cost:.2f} {currency}\n"
                f"- 上一小时费用: {previous_cost:.2f} {currency}\n\n"
                f"<@all>"
            )
        else:
            content = (
                f"## Cloud Billing Alert\n\n"
                f"**{provider_name}** account billing increased by "
                f"**{increase_cost:.2f} {currency}** in the last hour, "
                f"growth rate: **{increase_percent:.2f}%**\n\n"
                f"- Current cost: {current_cost:.2f} {currency}\n"
                f"- Previous hour cost: {previous_cost:.2f} {currency}\n\n"
                f"<@all>"
            )

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }

        try:
            timeout = self.webhook_config.get('timeout', 10)
            headers = {
                'Content-Type': 'application/json',
                **self.webhook_config.get('headers', {})
            }

            response = requests.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=timeout
            )

            response.raise_for_status()
            response_data = response.json()

            webhook_host = (
                webhook_url.split('/')[2] if '/' in webhook_url else 'unknown'
            )
            logger.info(
                f"WebhookService.send_wechat_alert: WeChat alert sent "
                f"successfully (provider_name={provider_name}, "
                f"webhook_host={webhook_host}, language={language}, "
                f"current_cost={current_cost}, previous_cost={previous_cost}, "
                f"increase_cost={increase_cost}, "
                f"increase_percent={increase_percent:.2f}, "
                f"currency={currency})"
            )
            return {
                'success': True,
                'response': response_data,
                'error': None
            }
        except requests.exceptions.RequestException as e:
            webhook_host = (
                webhook_url.split('/')[2] if '/' in webhook_url else 'unknown'
            )
            logger.error(
                f"WebhookService.send_wechat_alert: Failed to send WeChat "
                f"alert (provider_name={provider_name}, "
                f"webhook_host={webhook_host}, language={language}, "
                f"error={str(e)})"
            )
            return {
                'success': False,
                'response': None,
                'error': str(e)
            }

    def send_alert(self, alert_record) -> Dict[str, Any]:
        """
        Send alert notification based on webhook provider type.

        Args:
            alert_record: AlertRecord instance

        Returns:
            Dictionary with result: {success: bool, response: dict, error: str}
        """
        if not self.webhook_config:
            return {
                'success': False,
                'response': None,
                'error': 'Webhook config not found or not active'
            }

        provider_type = self.webhook_config.get('provider', 'feishu')
        language = self.webhook_config.get('language', 'zh-hans')

        alert_data = {
            'provider_name': alert_record.provider.display_name,
            'current_cost': float(alert_record.current_cost),
            'previous_cost': float(alert_record.previous_cost),
            'increase_cost': float(alert_record.increase_cost),
            'increase_percent': float(alert_record.increase_percent),
            'currency': alert_record.currency,
            'language': language,
        }

        provider_id = alert_record.provider.id
        provider_name = alert_record.provider.name

        if provider_type in ['feishu', 'wecom']:
            logger.info(
                f"WebhookService.send_alert: Sending Feishu alert "
                f"(alert_record_id={alert_record.id}, "
                f"provider_id={provider_id}, provider_name={provider_name}, "
                f"webhook_provider={provider_type}, language={language})"
            )
            return self.send_feishu_alert(alert_data)
        elif provider_type == 'wechat':
            logger.info(
                f"WebhookService.send_alert: Sending WeChat alert "
                f"(alert_record_id={alert_record.id}, "
                f"provider_id={provider_id}, provider_name={provider_name}, "
                f"webhook_provider={provider_type}, language={language})"
            )
            return self.send_wechat_alert(alert_data)
        else:
            logger.warning(
                f"WebhookService.send_alert: Unsupported webhook provider "
                f"type (alert_record_id={alert_record.id}, "
                f"provider_id={provider_id}, provider_name={provider_name}, "
                f"webhook_provider={provider_type})"
            )
            return {
                'success': False,
                'response': None,
                'error': (
                    f'Unsupported webhook provider type: {provider_type}'
                )
            }
