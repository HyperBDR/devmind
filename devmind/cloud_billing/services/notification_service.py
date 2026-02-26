"""
Notification service for cloud billing alerts.

This service generates notification messages from cloud billing business data
and sends them via agentcore_notifier unified task (send_notification).
Channel selection (webhook/email by UUID or default) is handled by notifier.
"""
import logging
from typing import Any, Dict, Optional

from django.utils import translation
from django.utils.translation import gettext_lazy as _

from agentcore_notifier.adapters.django.services.email_service import (
    get_default_email_channel,
    get_email_channel_by_uuid,
)
from agentcore_notifier.adapters.django.services.webhook_service import (
    get_default_webhook_channel,
    get_webhook_channel_by_uuid,
)
from agentcore_notifier.adapters.django.tasks.send import (
    NOTIFICATION_TYPE_EMAIL,
    NOTIFICATION_TYPE_WEBHOOK,
    send_notification,
)
from agentcore_notifier.constants import FEISHU_PROVIDERS, Provider

from cloud_billing.constants import (
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
from cloud_billing.models import AlertRecord

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

    def _generate_email_subject_and_body(
        self, alert_record: AlertRecord, language: str
    ) -> tuple:
        """
        Generate plain text subject and body for email from alert record.
        Returns (subject, body).
        """
        provider_name = alert_record.provider.display_name
        current_cost = float(alert_record.current_cost)
        previous_cost = float(alert_record.previous_cost)
        increase_cost = float(alert_record.increase_cost)
        increase_percent = float(alert_record.increase_percent)
        currency = alert_record.currency
        lang_code = "zh_Hans" if language == "zh-hans" else "en"
        with translation.override(lang_code):
            subject = str(_("[Important] Cloud Billing Alert"))
            alert_rule = alert_record.alert_rule
            is_cost_threshold = (
                alert_rule
                and alert_rule.cost_threshold is not None
                and current_cost > float(alert_rule.cost_threshold)
            )
            if is_cost_threshold:
                body_template = _(
                    "%(provider_name)s current total cost "
                    "%(current_cost).2f %(currency)s exceeds threshold "
                    "%(threshold).2f %(currency)s\n"
                    "Previous hour cost: %(previous_cost).2f %(currency)s"
                )
                body = str(
                    body_template
                    % {
                        "provider_name": provider_name,
                        "current_cost": current_cost,
                        "currency": currency,
                        "threshold": alert_rule.cost_threshold,
                        "previous_cost": previous_cost,
                    }
                )
            else:
                body_template = _(
                    "%(provider_name)s account billing increased by "
                    "%(increase_cost).2f %(currency)s in the last hour, "
                    "growth rate: %(increase_percent).2f%%\n"
                    "Current cost: %(current_cost).2f %(currency)s\n"
                    "Previous hour cost: %(previous_cost).2f %(currency)s"
                )
                body = str(
                    body_template
                    % {
                        "provider_name": provider_name,
                        "increase_cost": increase_cost,
                        "currency": currency,
                        "increase_percent": increase_percent,
                        "current_cost": current_cost,
                        "previous_cost": previous_cost,
                    }
                )
        return subject, body

    def send_alert(
        self,
        alert_record: AlertRecord,
        channel_uuid: Optional[str] = None,
        channel_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send alert notification via Celery task (agentcore_notifier).
        When channel_type and channel_uuid are set, use that channel (webhook
        or email). When only channel_uuid is set, treat as webhook. When both
        omitted, use notifier default (webhook).
        """
        if channel_type == "email":
            if not channel_uuid:
                return {
                    "success": False,
                    "response": None,
                    "error": (
                        "Email channel_uuid is required when "
                        "notification type is email"
                    ),
                }
            return self._send_alert_email(alert_record, channel_uuid)
        return self._send_alert_webhook(alert_record, channel_uuid)

    def _send_alert_email(
        self, alert_record: AlertRecord, channel_uuid: str
    ) -> Dict[str, Any]:
        """Send alert via email channel."""
        channel, config = get_email_channel_by_uuid(channel_uuid)
        if not channel or not config:
            return {
                "success": False,
                "response": None,
                "error": "Email channel not found or inactive",
            }
        raw = channel.config or {}
        provider_config = alert_record.provider.config or {}
        notification = provider_config.get("notification") or {}
        email_to = notification.get("email_to")
        if email_to is not None:
            if isinstance(email_to, list):
                to_addresses = [
                    a.strip() for a in email_to if (a or "").strip()
                ]
            elif isinstance(email_to, str) and email_to.strip():
                to_addresses = [
                    a.strip()
                    for a in email_to.replace(",", " ").split()
                    if a.strip()
                ]
            else:
                to_addresses = []
        else:
            raw = channel.config or {}
            to_list = raw.get("default_to") or raw.get("to")
            if isinstance(to_list, list):
                to_addresses = [
                    a.strip() for a in to_list if (a or "").strip()
                ]
            elif isinstance(to_list, str) and to_list.strip():
                to_addresses = [to_list.strip()]
            else:
                to_addresses = []
        if not to_addresses:
            return {
                "success": False,
                "response": None,
                "error": (
                    "No recipients: set email_to in notification config or "
                    "default_to on the email channel"
                ),
            }
        language = raw.get("language", DEFAULT_LANGUAGE)
        subject, body = self._generate_email_subject_and_body(
            alert_record, language
        )
        user = alert_record.provider.created_by
        user_id = user.id if user else None
        send_notification.delay(
            notification_type=NOTIFICATION_TYPE_EMAIL,
            source_app=SOURCE_APP_CLOUD_BILLING,
            source_type=SOURCE_TYPE_ALERT,
            source_id=str(alert_record.id),
            user_id=user_id,
            channel_uuid=channel_uuid,
            params={
                "subject": subject,
                "body": body,
                "to": to_addresses,
            },
        )
        return {"success": True, "response": None, "error": None}

    def _send_alert_webhook(
        self,
        alert_record: AlertRecord,
        channel_uuid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send alert via webhook (default or by uuid)."""
        if channel_uuid:
            channel, config = get_webhook_channel_by_uuid(channel_uuid)
        else:
            channel, config = get_default_webhook_channel()

        if not channel or not config:
            return {
                "success": False,
                "response": None,
                "error": (
                    "Channel not found or inactive for channel_uuid"
                    if channel_uuid
                    else "Webhook config not found or not active"
                ),
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

        send_notification.delay(
            notification_type=NOTIFICATION_TYPE_WEBHOOK,
            source_app=SOURCE_APP_CLOUD_BILLING,
            source_type=SOURCE_TYPE_ALERT,
            source_id=str(alert_record.id),
            user_id=user_id,
            channel_uuid=str(channel.uuid),
            params={
                "payload": payload,
                "provider_type": provider_type,
            },
        )
        return {"success": True, "response": None, "error": None}
