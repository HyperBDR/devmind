"""
Webhook service for sending notifications.

This service provides generic webhook notification capabilities.
It only handles sending formatted messages and does not contain
any business-specific message generation logic.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import requests

from app_config.utils import get_config

from ..constants import (
    Channel,
    CONFIG_KEY_WEBHOOK,
    DEFAULT_PROVIDER_TYPE,
    DEFAULT_SOURCE_APP,
    DEFAULT_TIMEOUT,
    FEISHU_PROVIDERS,
    Provider,
    Status,
)
from ..models import NotificationRecord

logger = logging.getLogger(__name__)


class WebhookService:
    """
    Service for sending webhook notifications.

    This service only handles sending formatted messages to webhook endpoints.
    Message content generation should be done by the calling business module.
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
            config = get_config(CONFIG_KEY_WEBHOOK, default={})
            if isinstance(config, dict) and config.get('is_active', False):
                self.webhook_config = config
            else:
                logger.warning(
                    f"WebhookService._load_config: Webhook config not found "
                    f"or not active (config_key={CONFIG_KEY_WEBHOOK})"
                )
        except Exception as e:
            logger.error(
                f"WebhookService._load_config: Failed to load webhook config "
                f"(config_key={CONFIG_KEY_WEBHOOK}, error={str(e)})"
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

    def send_feishu(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send message to Feishu webhook.

        Args:
            payload: Feishu webhook payload dictionary.
                Expected format:
                {
                    "msg_type": "post",
                    "content": {
                        "post": {
                            "zh-hans": {
                                "title": "Title",
                                "content": [[{"tag": "text", "text": "..."}]]
                            }
                        }
                    }
                }

        Returns:
            Dictionary with result:
            {success: bool, response: dict, error: str}
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

        try:
            timeout = self.webhook_config.get('timeout', DEFAULT_TIMEOUT)
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
                webhook_url.split('/')[2]
                if '/' in webhook_url else DEFAULT_SOURCE_APP
            )
            logger.info(
                f"WebhookService.send_feishu: Feishu message sent "
                f"successfully (webhook_host={webhook_host})"
            )
            return {
                'success': True,
                'response': response_data,
                'error': None
            }
        except requests.exceptions.RequestException as e:
            webhook_host = (
                webhook_url.split('/')[2]
                if '/' in webhook_url else DEFAULT_SOURCE_APP
            )
            logger.error(
                f"WebhookService.send_feishu: Failed to send Feishu message "
                f"(webhook_host={webhook_host}, error={str(e)})"
            )
            return {
                'success': False,
                'response': None,
                'error': str(e)
            }

    def send_wechat(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send message to WeChat Work webhook.

        Args:
            payload: WeChat webhook payload dictionary.
                Expected format:
                {
                    "msgtype": "markdown",
                    "markdown": {
                        "content": "## Title\n\nContent..."
                    }
                }

        Returns:
            Dictionary with result:
            {success: bool, response: dict, error: str}
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

        try:
            timeout = self.webhook_config.get('timeout', DEFAULT_TIMEOUT)
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
                webhook_url.split('/')[2]
                if '/' in webhook_url else DEFAULT_SOURCE_APP
            )
            logger.info(
                f"WebhookService.send_wechat: WeChat message sent "
                f"successfully (webhook_host={webhook_host})"
            )
            return {
                'success': True,
                'response': response_data,
                'error': None
            }
        except requests.exceptions.RequestException as e:
            webhook_host = (
                webhook_url.split('/')[2]
                if '/' in webhook_url else DEFAULT_SOURCE_APP
            )
            logger.error(
                f"WebhookService.send_wechat: Failed to send WeChat message "
                f"(webhook_host={webhook_host}, error={str(e)})"
            )
            return {
                'success': False,
                'response': None,
                'error': str(e)
            }

    def _record_notification(
        self,
        provider_type: str,
        payload: Dict[str, Any],
        result: Dict[str, Any],
        source_app: Optional[str] = None,
        source_type: Optional[str] = None,
        source_id: Optional[str] = None,
        user: Optional[Any] = None
    ) -> Optional[Any]:
        """
        Record notification sending result.

        Args:
            provider_type: Notification provider type
            payload: Notification payload
            result: Sending result dictionary
            source_app: Source application name
            source_type: Source type
            source_id: Source identifier
            user: User instance who should receive the notification

        Returns:
            NotificationRecord instance or None if recording failed
        """
        try:
            webhook_url = (
                self.webhook_config.get('url', '')
                if self.webhook_config else ''
            )

            status = (
                Status.SUCCESS
                if result.get('success')
                else Status.FAILED
            )

            # Build metadata based on channel type
            metadata = {}
            if (
                provider_type in FEISHU_PROVIDERS or
                provider_type == Provider.WECHAT
            ):
                headers = (
                    self.webhook_config.get('headers', {})
                    if self.webhook_config else {}
                )
                metadata = {
                    'url': webhook_url,
                    'headers': headers
                }

            notification_record = NotificationRecord.objects.create(
                provider_type=provider_type,
                channel=Channel.WEBHOOK,
                user=user,
                source_app=source_app or DEFAULT_SOURCE_APP,
                source_type=source_type or '',
                source_id=source_id or '',
                payload=payload,
                status=status,
                response=result.get('response'),
                error_message=result.get('error', ''),
                metadata=metadata,
                sent_at=(
                    datetime.now()
                    if status == Status.SUCCESS
                    else None
                )
            )

            logger.debug(
                f"WebhookService._record_notification: Notification recorded "
                f"(record_id={notification_record.id}, status={status})"
            )
            return notification_record
        except Exception as e:
            logger.warning(
                f"WebhookService._record_notification: Failed to record "
                f"notification (error={str(e)})"
            )
            return None

    def send(
        self,
        payload: Dict[str, Any],
        provider_type: Optional[str] = None,
        source_app: Optional[str] = None,
        source_type: Optional[str] = None,
        source_id: Optional[str] = None,
        user: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Send notification based on webhook provider type.

        Args:
            payload: Formatted webhook payload dictionary.
                Format depends on provider_type.
            provider_type: Webhook provider type (feishu/wecom/wechat).
                If None, uses provider from config.
            source_app: Source application name for recording
            source_type: Source type for recording
            source_id: Source identifier for recording
            user: User instance who should receive the notification

        Returns:
            Dictionary with result:
            {success: bool, response: dict, error: str, record_id: int}
        """
        if not self.webhook_config:
            result = {
                'success': False,
                'response': None,
                'error': 'Webhook config not found or not active'
            }
            if source_app:
                self._record_notification(
                    DEFAULT_SOURCE_APP, payload, result,
                    source_app, source_type, source_id, user
                )
            return result

        if provider_type is None:
            provider_type = self.webhook_config.get(
                'provider', DEFAULT_PROVIDER_TYPE
            )

        if provider_type in FEISHU_PROVIDERS:
            logger.info(
                f"WebhookService.send: Sending via Feishu "
                f"(webhook_provider={provider_type})"
            )
            result = self.send_feishu(payload)
        elif provider_type == Provider.WECHAT:
            logger.info(
                f"WebhookService.send: Sending via WeChat "
                f"(webhook_provider={provider_type})"
            )
            result = self.send_wechat(payload)
        else:
            logger.warning(
                f"WebhookService.send: Unsupported webhook provider "
                f"type (webhook_provider={provider_type})"
            )
            result = {
                'success': False,
                'response': None,
                'error': (
                    f'Unsupported webhook provider type: {provider_type}'
                )
            }

        # Record notification if source information is provided
        if source_app:
            record = self._record_notification(
                provider_type, payload, result,
                source_app, source_type, source_id, user
            )
            if record:
                result['record_id'] = record.id

        return result
