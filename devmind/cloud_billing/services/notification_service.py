"""
Notification service for cloud billing alerts.

This service generates notification messages from cloud billing business data
and sends them via agentcore_notifier Celery task (send_webhook_notification).
"""
import logging
from typing import Any, Dict

from django.utils import translation
from django.utils.translation import gettext_lazy as _

from agentcore_notifier.constants import FEISHU_PROVIDERS, Provider
from agentcore_notifier.adapters.django.services.webhook_service import (
    get_default_webhook_channel,
)
from agentcore_notifier.adapters.django.tasks.send import (
    send_webhook_notification,
)

from ..constants import (
    DEFAULT_LANGUAGE,
    FEISHU_MSG_TYPE_POST,
    FEISHU_TAG_AT,
    FEISHU_TAG_TEXT,
    FEISHU_USER_ID_ALL,
    LANGUAGE_EN,
    LANGUAGE_ZH_HANS,
    SOURCE_APP_CLOUD_BILLING,
    SOURCE_TYPE_ALERT,
    WECHAT_MSGTYPE_MARKDOWN,
)
from ..models import AlertRecord

logger = logging.getLogger(__name__)


class CloudBillingNotificationService:
    """
    Service for sending cloud billing notifications.

    This service generates notification messages from cloud billing data
    and sends them using the notifier service.
    """

    def __init__(self):
        """Init notification service (no local webhook; uses task)."""
        pass

    def _generate_feishu_payload(
        self, alert_record: AlertRecord, language: str
    ) -> Dict[str, Any]:
        """
        Generate Feishu webhook payload from alert record.

        Args:
            alert_record: AlertRecord instance
            language: Message language (zh-hans/en)

        Returns:
            Feishu webhook payload dictionary
        """
        provider_name = alert_record.provider.display_name
        current_cost = float(alert_record.current_cost)
        previous_cost = float(alert_record.previous_cost)
        increase_cost = float(alert_record.increase_cost)
        increase_percent = float(alert_record.increase_percent)
        currency = alert_record.currency

        # Map language code to Django translation code
        lang_code = 'zh_Hans' if language == 'zh-hans' else 'en'
        with translation.override(lang_code):
            title = str(_("[Important] Cloud Billing Alert"))
            
            # Check if this is a cost threshold alert
            # (current_cost exceeds threshold) or growth alert
            alert_rule = alert_record.alert_rule
            is_cost_threshold = (
                alert_rule and
                alert_rule.cost_threshold is not None and
                current_cost > float(alert_rule.cost_threshold)
            )
            
            if is_cost_threshold:
                message_template = _(
                    "%(provider_name)s current total cost "
                    "%(current_cost).2f %(currency)s exceeds threshold "
                    "%(threshold).2f %(currency)s\n"
                    "Previous hour cost: %(previous_cost).2f %(currency)s"
                )
                message = str(message_template % {
                    'provider_name': provider_name,
                    'current_cost': current_cost,
                    'currency': currency,
                    'threshold': alert_rule.cost_threshold,
                    'previous_cost': previous_cost,
                })
            else:
                message_template = _(
                    "%(provider_name)s account billing increased by "
                    "%(increase_cost).2f %(currency)s in the last hour, "
                    "growth rate: %(increase_percent).2f%%\n"
                    "Current cost: %(current_cost).2f %(currency)s\n"
                    "Previous hour cost: %(previous_cost).2f %(currency)s"
                )
                message = str(message_template % {
                    'provider_name': provider_name,
                    'increase_cost': increase_cost,
                    'currency': currency,
                    'increase_percent': increase_percent,
                    'current_cost': current_cost,
                    'previous_cost': previous_cost,
                })

        payload = {
            "msg_type": FEISHU_MSG_TYPE_POST,
            "content": {
                "post": {
                    language: {
                        "title": title,
                        "content": [
                            [{
                                "tag": FEISHU_TAG_TEXT,
                                "text": message
                            }, {
                                "tag": FEISHU_TAG_AT,
                                "user_id": FEISHU_USER_ID_ALL
                            }]
                        ]
                    }
                }
            }
        }

        return payload

    def _generate_wechat_payload(
        self, alert_record: AlertRecord, language: str
    ) -> Dict[str, Any]:
        """
        Generate WeChat Work webhook payload from alert record.

        Args:
            alert_record: AlertRecord instance
            language: Message language (zh-hans/en)

        Returns:
            WeChat webhook payload dictionary
        """
        provider_name = alert_record.provider.display_name
        current_cost = float(alert_record.current_cost)
        previous_cost = float(alert_record.previous_cost)
        increase_cost = float(alert_record.increase_cost)
        increase_percent = float(alert_record.increase_percent)
        currency = alert_record.currency

        # Map language code to Django translation code
        lang_code = 'zh_Hans' if language == 'zh-hans' else 'en'
        with translation.override(lang_code):
            title = str(_("## Cloud Billing Alert\n\n"))
            
            # Check if this is a cost threshold alert
            # (current_cost exceeds threshold) or growth alert
            alert_rule = alert_record.alert_rule
            is_cost_threshold = (
                alert_rule and
                alert_rule.cost_threshold is not None and
                current_cost > float(alert_rule.cost_threshold)
            )
            
            if is_cost_threshold:
                content = str(_(
                    "{title}**{provider_name}** current total cost "
                    "**{current_cost:.2f} {currency}** exceeds threshold "
                    "**{threshold:.2f} {currency}**\n\n"
                    "- Previous hour cost: {previous_cost:.2f} {currency}\n\n"
                    "<@all>"
                ).format(
                    title=title,
                    provider_name=provider_name,
                    current_cost=current_cost,
                    currency=currency,
                    threshold=alert_rule.cost_threshold,
                    previous_cost=previous_cost,
                ))
            else:
                content = str(_(
                    "{title}**{provider_name}** account billing "
                    "increased by **{increase_cost:.2f} {currency}** "
                    "in the last hour, growth rate: "
                    "**{increase_percent:.2f}%**\n\n"
                    "- Current cost: {current_cost:.2f} {currency}\n"
                    "- Previous hour cost: {previous_cost:.2f} {currency}\n\n"
                    "<@all>"
                ).format(
                    title=title,
                    provider_name=provider_name,
                    increase_cost=increase_cost,
                    currency=currency,
                    increase_percent=increase_percent,
                    current_cost=current_cost,
                    previous_cost=previous_cost,
                ))

        payload = {
            "msgtype": WECHAT_MSGTYPE_MARKDOWN,
            "markdown": {
                "content": content
            }
        }

        return payload

    def send_alert(self, alert_record: AlertRecord) -> Dict[str, Any]:
        """
        Send alert notification via Celery task (agentcore_notifier).
        Reads active webhook channel from agentcore_notifier
        (NotificationChannel); actual send runs async in worker.
        """
        channel, config = get_default_webhook_channel()
        if not channel or not config:
            return {
                "success": False,
                "response": None,
                "error": "Webhook config not found or not active",
            }

        provider_type = config.get("provider", Provider.FEISHU)
        language = (channel.config or {}).get("language", DEFAULT_LANGUAGE)
        user = alert_record.provider.created_by
        user_id = user.id if user else None

        if provider_type in FEISHU_PROVIDERS:
            payload = self._generate_feishu_payload(alert_record, language)
        elif provider_type == Provider.WECHAT:
            payload = self._generate_wechat_payload(alert_record, language)
        else:
            return {
                "success": False,
                "response": None,
                "error": f"Unsupported webhook provider type: {provider_type}",
            }

        send_webhook_notification.delay(
            payload=payload,
            provider_type=provider_type,
            source_app=SOURCE_APP_CLOUD_BILLING,
            source_type=SOURCE_TYPE_ALERT,
            source_id=str(alert_record.id),
            user_id=user_id,
        )
        return {"success": True, "response": None, "error": None}
