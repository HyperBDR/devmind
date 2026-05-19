"""
Notification service for cloud billing alerts.

This service generates notification messages from cloud billing business data
and sends them via agentcore_notifier unified task (send_notification).
Channel selection (webhook/email by UUID or default) is handled by notifier.
"""
import logging
from decimal import Decimal
from typing import Any, Dict, Optional
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
from django.utils import translation
from django.utils.translation import gettext as _

from cloud_billing.alert_messages import (
    build_alert_message_from_record,
    build_alert_sections_from_record,
)
from cloud_billing.constants import (
    DEFAULT_LANGUAGE,
    SOURCE_APP_CLOUD_BILLING,
    SOURCE_TYPE_ALERT,
    SOURCE_TYPE_RECHARGE_APPROVAL,
    WECHAT_MSGTYPE_MARKDOWN,
)
from cloud_billing.models import AlertRecord, RechargeApprovalRecord
from cloud_billing.services.recharge_approval import parse_recharge_info

logger = logging.getLogger(__name__)


def _feishu_cost_table(
    items: list,
    currency: str,
    labels: dict,
) -> list:
    """Build Feishu column_set elements for cost breakdown table.

    Returns a title div + header row (blue bg) + data rows.
    Columns: Resource, Cost, Owner (always shown, "-" if empty).
    ``labels`` is the ``sections["labels"]`` dict from
    ``build_alert_sections`` — all strings are pre-localized.
    """
    rows = []

    # Title
    rows.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": f"**📋 {labels['cost_breakdown']}**",
        },
    })

    # Header row
    cols = [
        labels["col_resource"],
        labels["col_cost"],
        labels["col_owner"],
    ]
    widths = ["weighted", "weighted", "weighted"]
    weights = [4, 3, 2]

    header_columns = []
    for i, col in enumerate(cols):
        header_columns.append({
            "tag": "column",
            "width": widths[i],
            "weight": weights[i],
            "elements": [{
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{col}**",
                },
            }],
        })
    rows.append({
        "tag": "column_set",
        "flex_mode": "none",
        "background_style": "blue",
        "columns": header_columns,
    })

    # Data rows (alternating grey/white)
    for idx, it in enumerate(items):
        name = it.get("name", "?")
        cost = float(it.get("cost", 0))
        owner = it.get("owner", "") or "-"
        row_cols = [
            name,
            f"{cost:.2f} {currency}",
            owner,
        ]

        bg = "grey" if idx % 2 == 0 else "default"
        columns = []
        for i, text in enumerate(row_cols):
            columns.append({
                "tag": "column",
                "width": widths[i],
                "weight": weights[i],
                "elements": [{
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": str(text),
                    },
                }],
            })
        rows.append({
            "tag": "column_set",
            "flex_mode": "none",
            "background_style": bg,
            "columns": columns,
        })

    return rows


class CloudBillingNotificationService:
    """
    Service for sending cloud billing notifications.

    This service generates notification messages from cloud billing data
    and sends them using the notifier service.
    """

    def __init__(self):
        """Init notification service (no local webhook; uses task)."""
        pass

    def _split_label_value(self, line: str) -> tuple[str, str]:
        """Split a `label:value` line into parts for channel-specific styling."""
        if "：" in line:
            label, value = line.split("：", 1)
            label = label.strip().strip("*")
            return label, value.strip()
        if ":" in line:
            label, value = line.split(":", 1)
            label = label.strip().strip("*")
            return label, value.strip()
        return line.strip(), ""

    def _is_chinese_language(self, language: str) -> bool:
        return str(language or DEFAULT_LANGUAGE).lower().startswith("zh")

    def _get_alert_title(self, language: str, channel: str) -> str:
        normalized_language = str(language or DEFAULT_LANGUAGE).lower()
        if self._is_chinese_language(normalized_language):
            title_map = {
                "feishu": "[重点关注]云平台账单消费提醒",
                "wechat": "## 云平台账单消费提醒\n\n",
                "email_subject": "云平台账单消费提醒",
                "email_body": "## 云平台账单消费提醒\n\n",
            }
        else:
            with translation.override(normalized_language):
                title_map = {
                    "feishu": _("[Important] Cloud Billing Alert"),
                    "wechat": _("## Cloud Billing Alert\n\n"),
                    "email_subject": _("Cloud Billing Alert"),
                    "email_body": _("## Cloud Billing Alert\n\n"),
                }
        normalized_channel = str(channel or "").lower()
        if normalized_channel not in title_map:
            raise ValueError(f"Unsupported alert title channel: {channel}")
        return title_map[normalized_channel]

    def _get_alert_body(
        self, alert_record: AlertRecord, language: str
    ) -> str:
        return build_alert_message_from_record(alert_record, language)

    def _generate_feishu_payload(
        self, alert_record: AlertRecord, language: str
    ) -> Dict[str, Any]:
        """Generate Feishu interactive card payload.

        Uses color-coded header, font-colored metrics, column_set
        table, and note component for a polished card layout.
        """
        sections = build_alert_sections_from_record(
            alert_record, language
        )
        L = sections["labels"]
        sep = L["sep"]
        currency = sections.get("currency", "CNY")
        alert_type = sections.get("alert_type", "")

        # Header color by severity
        if "Balance" in alert_type:
            header_template = "red"
        elif "Days" in alert_type:
            header_template = "orange"
        elif "Growth" in alert_type:
            header_template = "orange"
        else:
            header_template = "blue"

        elements = []

        # ── 1. Trigger reason (highlighted) ──
        trigger_icon = sections.get("trigger_icon", "")
        trigger_text = sections.get("trigger_text", "")
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"{trigger_icon} "
                    f"<font color='orange'>"
                    f"**{trigger_text}**</font>"
                ),
            },
        })

        # ── 2. Account info ──
        info_parts = []
        for key, label_key in [
            ("provider", "provider"),
            ("account_id", "account"),
            ("notes", "notes"),
        ]:
            if sections.get(key):
                info_parts.append(
                    f"**{L[label_key]}**{sep}{sections[key]}"
                )
        if sections.get("tags"):
            tag_str = "、".join(sections["tags"])
            info_parts.append(
                f"**{L['tags']}**{sep}{tag_str}"
            )
        if info_parts:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "\n".join(info_parts),
                },
            })

        elements.append({"tag": "hr"})

        # ── 3. Only show triggered metrics (noise reduction) ──
        # Determine which alert type is triggered
        metrics = sections.get("metrics", [])
        thresholds = sections.get("thresholds", [])

        def find_metric(*labels):
            for lbl in labels:
                for m in metrics:
                    if m["label"] == lbl:
                        return m
            return None

        def find_threshold(*labels):
            for lbl in labels:
                for t in thresholds:
                    if t["label"] == lbl:
                        return t
            return None

        def add_metric_row(metric, threshold):
            """Add a row with metric and threshold, threshold is red if triggered."""
            if not metric and not threshold:
                return
            pair_columns = []
            if metric:
                val = metric["value"]
                label = metric["label"]
                unit = f" {currency}" if not str(val).endswith("%") else ""
                is_triggered = metric.get("highlight")
                val_md = f"<font color='red'>**{val}{unit}**</font>" if is_triggered else f"**{val}{unit}**"
                pair_columns.append({
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "vertical_align": "center",
                    "elements": [{
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": f"{label}\n{val_md}"},
                    }],
                })
            if threshold:
                val = threshold["value"]
                label = threshold["label"]
                is_triggered = metric and metric.get("highlight")
                val_md = f"<font color='red'>**{val}**</font>" if is_triggered else f"**{val}**"
                pair_columns.append({
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "vertical_align": "center",
                    "elements": [{
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": f"{label}\n{val_md}"},
                    }],
                })
            if pair_columns:
                elements.append({
                    "tag": "column_set",
                    "flex_mode": "stretch",
                    "background_style": "grey",
                    "columns": pair_columns,
                })

        # Determine which alert type is triggered and show relevant metrics
        # Only show metrics/thresholds relevant to the current alert type
        # Use translated label names from L (labels are already translated by Django)
        cost_threshold = find_threshold(L["cost_threshold"])
        current_metric = find_metric(L["current_hour_cost"])
        growth_metric = find_metric(L["growth_rate"])
        pct_threshold = find_threshold(L["growth_percentage_threshold"])
        increase_metric = find_metric(L["increase_amount"])
        amount_threshold = find_threshold(L["amount_threshold"])

        if "Balance" in alert_type:
            # Balance alert: no additional metrics row needed, balance shown separately
            pass
        elif "Days" in alert_type:
            # Days remaining alert: no additional metrics row needed, shown in trigger
            pass
        elif "Cost Threshold" in alert_type or "Cost" in alert_type:
            # Cost threshold alert: show current total + cost threshold
            add_metric_row(current_metric, cost_threshold)
        else:
            # Growth alert: show growth rate + pct threshold AND increase + amount threshold
            if growth_metric:
                add_metric_row(growth_metric, pct_threshold)
            if increase_metric:
                add_metric_row(increase_metric, amount_threshold)

        # ── 5. Cost breakdown table ──
        resource_costs = sections.get("resource_costs", [])
        if resource_costs:
            elements.append({"tag": "hr"})
            elements.extend(
                _feishu_cost_table(
                    resource_costs[:10],
                    currency,
                    L,
                )
            )

        # ── 6. Balance ──
        balance_info = sections.get("balance")
        if balance_info:
            bal = balance_info["value"]
            bal_cur = balance_info["currency"]
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{L['current_balance']}**{sep}{bal:.2f} {bal_cur}",
                },
            })

        # ── 7. Footer note + @all ──
        elements.append({
            "tag": "note",
            "elements": [
                {
                    "tag": "plain_text",
                    "content": L["footer"],
                },
                {
                    "tag": "lark_md",
                    "content": "<at id=all></at>",
                },
            ],
        })

        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": self._get_alert_title(
                            language, "feishu"
                        ),
                    },
                    "template": header_template,
                },
                "elements": elements,
            },
        }

        return payload

    def _generate_wechat_payload(
        self, alert_record: AlertRecord, language: str
    ) -> Dict[str, Any]:
        """Generate WeChat Work webhook payload with enhanced layout."""
        sections = build_alert_sections_from_record(
            alert_record, language
        )
        L = sections["labels"]
        sep = L["sep"]
        currency = sections.get("currency", "CNY")

        rows = []

        # Trigger
        rows.append(
            f"> {sections.get('trigger_icon', '')}"
            f" **{sections.get('trigger_text', '')}**"
        )
        rows.append("")

        # Account info
        for key, label_key in [
            ("provider", "provider"),
            ("account_id", "account"),
            ("notes", "notes"),
        ]:
            if sections.get(key):
                rows.append(
                    f"**{L[label_key]}**{sep}{sections[key]}"
                )

        # Metrics
        metrics = sections.get("metrics", [])
        if metrics:
            rows.append("")
            for m in metrics:
                val = m["value"]
                bold = "**" if m.get("highlight") else ""
                unit = "" if "%" in str(val) else f" {currency}"
                rows.append(
                    f"  {m['label']}{sep}{bold}{val}{unit}{bold}"
                )

        # Thresholds
        thresholds = sections.get("thresholds", [])
        if thresholds:
            rows.append("")
            rows.append(" | ".join(
                f"{t['label']}{sep}{t['value']}"
                for t in thresholds
            ))

        # Cost breakdown
        resource_costs = sections.get("resource_costs", [])
        if resource_costs:
            rows.append("")
            rows.append(f"**{L['cost_breakdown']}**{sep}")
            rows.append(
                f"| {L['col_resource']} | {L['col_cost']} | {L['col_owner']} |"
            )
            rows.append("| --- | ---: | --- |")
            for it in resource_costs[:10]:
                name = it.get("name", "?")
                cost = float(it.get("cost", 0))
                owner = it.get("owner", "") or "-"
                rows.append(
                    f"| {name} | {cost:.2f} {currency} "
                    f"| {owner} |"
                )

        # Balance
        balance_info = sections.get("balance")
        if balance_info:
            rows.append("")
            rows.append(
                f"**{L['current_balance']}**{sep}"
                f"{balance_info['value']:.2f} {balance_info['currency']}"
            )

        rows.append("")
        rows.append("<@all>")

        content = (
            self._get_alert_title(language, "wechat")
            + "\n".join(rows)
        )

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
        """Generate email subject and markdown body."""
        subject = self._get_alert_title(language, "email_subject")
        sections = build_alert_sections_from_record(
            alert_record, language
        )
        L = sections["labels"]
        sep = L["sep"]
        currency = sections.get("currency", "CNY")

        rows = []

        # Trigger
        rows.append(
            f"> {sections.get('trigger_icon', '')}"
            f" **{sections.get('trigger_text', '')}**"
        )
        rows.append("")

        # Account info
        for key, label_key in [
            ("provider", "provider"),
            ("account_id", "account"),
            ("notes", "notes"),
        ]:
            if sections.get(key):
                rows.append(
                    f"**{L[label_key]}**{sep}{sections[key]}"
                )

        # Metrics
        metrics = sections.get("metrics", [])
        if metrics:
            rows.append("")
            for m in metrics:
                val = m["value"]
                bold = "**" if m.get("highlight") else ""
                unit = "" if "%" in str(val) else f" {currency}"
                rows.append(
                    f"  {m['label']}{sep}{bold}{val}{unit}{bold}"
                )

        # Thresholds
        thresholds = sections.get("thresholds", [])
        if thresholds:
            rows.append("")
            rows.append(" | ".join(
                f"{t['label']}{sep}{t['value']}"
                for t in thresholds
            ))

        # Cost breakdown
        resource_costs = sections.get("resource_costs", [])
        if resource_costs:
            rows.append("")
            rows.append(f"**{L['cost_breakdown']}**{sep}")
            rows.append(
                f"| {L['col_resource']} | {L['col_cost']} | {L['col_owner']} |"
            )
            rows.append("| --- | ---: | --- |")
            for it in resource_costs[:10]:
                name = it.get("name", "?")
                cost = float(it.get("cost", 0))
                owner = it.get("owner", "") or "-"
                rows.append(
                    f"| {name} | {cost:.2f} {currency} "
                    f"| {owner} |"
                )

        # Balance
        balance_info = sections.get("balance")
        if balance_info:
            rows.append("")
            rows.append(
                f"**{L['current_balance']}**{sep}"
                f"{balance_info['value']:.2f} {balance_info['currency']}"
            )

        body = (
            self._get_alert_title(language, "email_body")
            + "\n".join(rows)
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


# ---------------------------------------------------------------------------
# RechargeApprovalNotificationService
# ---------------------------------------------------------------------------


class RechargeApprovalNotificationService:
    """
    Service for sending recharge approval notifications.

    Handles submitted/final-status notifications for recharge approval records
    via the same agentcore_notifier channel infrastructure used by alerts.
    """

    # Notification type → (Chinese title, English title)
    NOTIFICATION_TYPE_LABELS = {
        "submitted": ("【充值审批】提交成功", "[Recharge Approval] Submission Successful"),
        "approved": ("【充值审批】审批通过", "[Recharge Approval] Approval Passed"),
        "rejected": ("【充值审批】审批被拒绝", "[Recharge Approval] Approval Rejected"),
        "canceled": ("【充值审批】审批已撤回", "[Recharge Approval] Approval Cancelled"),
        "failed": ("【充值审批】提交失败", "[Recharge Approval] Submission Failed"),
    }

    STATUS_LABELS = {
        "approved": ("已通过", "Approved"),
        "rejected": ("已拒绝", "Rejected"),
        "canceled": ("已撤回", "Cancelled"),
        "failed": ("提交失败", "Submission Failed"),
        "submitted": ("已提交", "Submitted"),
    }

    TRIGGER_SOURCE_LABELS = {
        "manual": ("人工触发", "Manual Trigger"),
        "alert": ("告警触发", "Alert Trigger"),
    }

    def _is_chinese_language(self, language: str) -> bool:
        return str(language or DEFAULT_LANGUAGE).lower().startswith("zh")

    def _get_label(
        self, key: str, language: str, choice_map: dict[str, tuple[str, str]]
    ) -> str:
        labels = choice_map.get(key, (key, key))
        return labels[0] if self._is_chinese_language(language) else labels[1]

    def _split_label_value(self, line: str) -> tuple[str, str]:
        if "：" in line:
            label, value = line.split("：", 1)
            return label.strip(), value.strip()
        if ":" in line:
            label, value = line.split(":", 1)
            return label.strip(), value.strip()
        return line.strip(), ""

    def _reformat_line(self, line: str) -> str:
        """Reformat a raw 'key：value' or 'key: value' line to 'key: value'."""
        label, value = self._split_label_value(line)
        return f"{label}: {value}" if value else f"{label}"

    def _stringify_display_value(self, value: Any) -> str:
        text = str(value or "").strip()
        return text or "—"

    def _format_recharge_amount(self, amount: Any, currency: str) -> str:
        if amount in (None, ""):
            return "—"
        currency = str(currency or "CNY").strip() or "CNY"
        if isinstance(amount, (int, float)):
            return f"{amount:,} {currency}"
        try:
            numeric_amount = Decimal(str(amount))
        except Exception:
            amount_text = str(amount).strip()
            return amount_text if currency in amount_text else f"{amount_text} {currency}"
        return f"{numeric_amount:,} {currency}"

    def _build_submitter_label(self, record: RechargeApprovalRecord) -> str:
        parts = []
        label = str(record.submitter_user_label or "").strip()
        identifier = str(record.submitter_identifier or "").strip()
        for value in (label, identifier):
            if value and value not in parts:
                parts.append(value)
        if parts:
            return " / ".join(parts)
        if record.trigger_source == RechargeApprovalRecord.TRIGGER_SOURCE_ALERT:
            return "系统自动提交"
        return "—"

    def _build_trigger_reason_label(
        self,
        record: RechargeApprovalRecord,
        language: str,
    ) -> str:
        if record.trigger_source != RechargeApprovalRecord.TRIGGER_SOURCE_ALERT:
            reason = str(
                record.trigger_reason or record.context_payload.get("trigger_reason") or ""
            ).strip()
            return reason or "—"

        alert_record = record.alert_record
        if alert_record is not None:
            if alert_record.alert_type == alert_record.ALERT_TYPE_BALANCE:
                balance = self._stringify_display_value(alert_record.current_balance)
                threshold = self._stringify_display_value(
                    alert_record.balance_threshold
                )
                if self._is_chinese_language(language):
                    return f"余额不足（当前余额 {balance}，阈值 {threshold}）"
                return (
                    "Balance below threshold "
                    f"(current balance {balance}, threshold {threshold})"
                )
            if alert_record.alert_type == alert_record.ALERT_TYPE_DAYS_REMAINING:
                days_remaining = self._stringify_display_value(
                    alert_record.current_days_remaining
                )
                threshold_days = self._stringify_display_value(
                    alert_record.days_remaining_threshold
                )
                if self._is_chinese_language(language):
                    return (
                        f"剩余天数不足（当前预计 {days_remaining} 天，"
                        f"阈值 {threshold_days} 天）"
                    )
                return (
                    "Days remaining below threshold "
                    f"(current estimate {days_remaining} days, "
                    f"threshold {threshold_days} days)"
                )

        reason = str(
            record.trigger_reason or record.context_payload.get("trigger_reason") or ""
        ).strip()
        if reason and reason != record.trigger_source:
            return reason
        return "告警触发"

    def _build_triggered_by_label(self, record: RechargeApprovalRecord) -> str:
        triggered_by = (
            record.triggered_by.username
            if getattr(record, "triggered_by_id", None)
            else ""
        )
        label = (
            triggered_by
            or record.triggered_by_username_snapshot
            or record.context_payload.get("triggered_by")
            or "—"
        )
        if label == "—" and record.trigger_source == RechargeApprovalRecord.TRIGGER_SOURCE_ALERT:
            return "系统自动触发"
        return label

    def _build_alert_detail_lines(
        self,
        record: RechargeApprovalRecord,
        language: str,
    ) -> list[str]:
        alert_record = record.alert_record
        if alert_record is None:
            return []

        separator = ": "
        lines = [
            self._get_field_label("alert_details", language),
        ]
        alert_message = str(alert_record.alert_message or "").strip()
        if alert_message:
            lines.extend(
                self._reformat_line(line.strip())
                for line in alert_message.splitlines()
                if line.strip()
            )
            return lines

        alert_type = str(alert_record.alert_type or "").strip()
        if alert_type:
            lines.append(
                f"{self._get_field_label('alert_type', language)}{separator}{alert_type}"
            )
        if alert_record.current_balance is not None:
            lines.append(
                f"{self._get_field_label('current_balance', language)}{separator}"
                f"{alert_record.current_balance:.2f} {alert_record.currency}"
            )
        if alert_record.balance_threshold is not None:
            lines.append(
                f"{self._get_field_label('balance_threshold', language)}{separator}"
                f"{alert_record.balance_threshold:.2f} {alert_record.currency}"
            )
        if alert_record.current_days_remaining is not None:
            lines.append(
                f"{self._get_field_label('current_days_remaining', language)}{separator}"
                f"{alert_record.current_days_remaining}"
            )
        if alert_record.days_remaining_threshold is not None:
            lines.append(
                f"{self._get_field_label('days_remaining_threshold', language)}{separator}"
                f"{alert_record.days_remaining_threshold}"
            )
        return lines

    def _build_recharge_message(
        self,
        record: RechargeApprovalRecord,
        notification_type: str,
        language: str,
    ) -> str:
        """
        Build a plain-text notification message from a RechargeApprovalRecord.

        If the record's context_payload contains a pre-formatted notification_message
        (generated by the agent), return it directly. Otherwise, build from fields.
        """
        # Agent-generated notification message takes precedence
        agent_msg = str(
            record.context_payload.get("notification_message", "")
        ).strip()
        if agent_msg:
            return agent_msg
        separator = ": "

        def build_display_payload() -> dict[str, Any]:
            payload: dict[str, Any] = {}
            if record.raw_recharge_info:
                try:
                    parsed = parse_recharge_info(record.raw_recharge_info)
                except Exception:
                    parsed = {}
                if isinstance(parsed, dict):
                    payload.update(parsed)
            if isinstance(record.request_payload, dict):
                for key, value in record.request_payload.items():
                    if value in (None, "", {}):
                        continue
                    if key == "payee" and isinstance(value, dict):
                        existing_payee = payload.get("payee")
                        if isinstance(existing_payee, dict):
                            payload["payee"] = {**existing_payee, **value}
                        else:
                            payload["payee"] = value
                        continue
                    payload[key] = value
            if isinstance(record.context_payload, dict):
                for key in (
                    "recharge_account",
                    "recharge_customer_name",
                    "payment_company",
                    "payment_way",
                    "payment_type",
                    "remit_method",
                    "amount",
                    "currency",
                    "expected_date",
                    "payment_note",
                    "remark",
                    "payee",
                ):
                    value = record.context_payload.get(key)
                    if value in (None, "", {}):
                        continue
                    if key == "payee" and isinstance(value, dict):
                        existing_payee = payload.get("payee")
                        if isinstance(existing_payee, dict):
                            payload["payee"] = {**existing_payee, **value}
                        else:
                            payload["payee"] = value
                        continue
                    if not payload.get(key):
                        payload[key] = value
            return payload

        def fmt_label(label: str) -> str:
            label_text = str(label or "").strip()
            return f"**{label_text}**" if label_text else ""

        def remark_is_payee_details_only(text: Any) -> bool:
            remark_text = str(text or "").strip()
            if not remark_text:
                return True
            allowed_keys = {
                "账户类型",
                "收款账户类型",
                "户名",
                "账号",
                "银行",
                "银行地区",
                "支行",
            }
            lines = [line.strip() for line in remark_text.splitlines() if line.strip()]
            if not lines:
                return True
            for line in lines:
                if "：" not in line:
                    return False
                key, _value = line.split("：", 1)
                if key.strip() not in allowed_keys:
                    return False
            return True

        def collect_receipt_info_lines(
            payee: Any, remark_text: Any
        ) -> list[str]:
            receipt_lines: list[str] = []
            seen_labels: set[str] = set()

            def add_line(label: str, value: Any) -> None:
                label_text = str(label or "").strip()
                value_text = self._stringify_display_value(value)
                if (
                    not label_text
                    or value_text == "—"
                    or label_text in seen_labels
                ):
                    return
                seen_labels.add(label_text)
                receipt_lines.append(f"  - {label_text}: {value_text}")

            if isinstance(payee, dict):
                add_line("账户类型", payee.get("type"))
                add_line("户名", payee.get("account_name"))
                add_line("账号", payee.get("account_number"))
                add_line("银行", payee.get("bank_name"))
                add_line("银行地区", payee.get("bank_region"))
                add_line("支行", payee.get("bank_branch"))

            if receipt_lines:
                return receipt_lines

            remark_payload = str(remark_text or "").strip()
            if not remark_payload or not remark_is_payee_details_only(
                remark_payload
            ):
                return receipt_lines

            label_map = {
                "账户类型": "账户类型",
                "收款账户类型": "账户类型",
                "账户类型": "账户类型",
                "户名": "户名",
                "账号": "账号",
                "银行": "银行",
                "银行地区": "银行地区",
                "银行所在地区": "银行地区",
                "支行": "支行",
                "银行支行": "支行",
            }
            for line in remark_payload.splitlines():
                raw_line = line.strip()
                if not raw_line or "：" not in raw_line:
                    continue
                key, value = raw_line.split("：", 1)
                label = label_map.get(key.strip())
                if label:
                    add_line(label, value.strip())
            return receipt_lines

        triggered_by = self._build_triggered_by_label(record)
        submitter = self._build_submitter_label(record)
        trigger_source = self._get_label(
            record.trigger_source,
            language,
            self.TRIGGER_SOURCE_LABELS,
        )
        trigger_reason = self._build_trigger_reason_label(record, language)
        if self._is_chinese_language(language):
            open_paren, close_paren = "（", "）"
            trigger_context = (
                f"{trigger_source}{open_paren}{trigger_reason}{close_paren}"
                if trigger_reason and trigger_reason != "—"
                else trigger_source
            )
        else:
            open_paren, close_paren = "(", ")"
            trigger_context = (
                f"{trigger_source} {open_paren}{trigger_reason}{close_paren}"
                if trigger_reason and trigger_reason != "—"
                else trigger_source
            )

        # Provider info
        provider_name = record.provider.display_name or "—"

        # Recharge details from request_payload
        payload = build_display_payload()
        recharge_account = self._stringify_display_value(
            payload.get("recharge_account")
        )
        recharge_customer = self._stringify_display_value(
            payload.get("recharge_customer_name")
        )
        amount = payload.get("amount")
        currency = str(payload.get("currency") or "CNY")
        amount_str = self._format_recharge_amount(amount, currency)

        payment_type = self._stringify_display_value(payload.get("payment_type"))
        payment_way = self._stringify_display_value(payload.get("payment_way"))
        remit_method = self._stringify_display_value(payload.get("remit_method"))
        payment_company = self._stringify_display_value(
            payload.get("payment_company")
        )
        expected_date = str(payload.get("expected_date") or "").strip()
        payment_note = str(payload.get("payment_note") or "").strip()
        remark = payload.get("remark")
        receipt_info_lines = collect_receipt_info_lines(
            payload.get("payee"), remark
        )

        # Status label
        status_label = self._get_label(record.status, language, self.STATUS_LABELS)
        # Error/failure reason
        failure_reason = ""
        if notification_type == "failed":
            failure_reason = record.status_message or "—"
        elif notification_type == "rejected":
            # Include status_message as rejection reason if present
            sm = str(record.status_message or "").strip()
            if sm:
                failure_reason = sm

        # Title is handled separately by each channel generator; do not include it in rows.
        lines = [
            f"{fmt_label(self._get_field_label('trigger_source', language))}{separator}{trigger_context}",
            f"{fmt_label(self._get_field_label('triggered_by', language))}{separator}{triggered_by}",
            f"{fmt_label(self._get_field_label('submitter', language))}{separator}{submitter}",
        ]
        lines.extend([
            f"{fmt_label(self._get_field_label('cloud_provider', language))}{separator}{provider_name}",
            f"{fmt_label(self._get_field_label('recharge_account', language))}{separator}{recharge_account}",
            f"{fmt_label(self._get_field_label('customer_name', language))}{separator}{recharge_customer}",
            f"{fmt_label(self._get_field_label('amount', language))}{separator}{amount_str}",
            f"{fmt_label(self._get_field_label('payment_company', language))}{separator}{payment_company}",
            f"{fmt_label(self._get_field_label('payment_way', language))}{separator}{payment_way}",
            f"{fmt_label(self._get_field_label('payment_type', language))}{separator}{payment_type}",
            f"{fmt_label(self._get_field_label('remit_method', language))}{separator}{remit_method}",
        ])
        if expected_date:
            lines.append(
                f"{fmt_label(self._get_field_label('expected_date', language))}{separator}{expected_date}"
            )
        if receipt_info_lines:
            lines.append(fmt_label("收款信息"))
            lines.extend(receipt_info_lines)
        else:
            if payment_note:
                lines.append(
                    f"{fmt_label(self._get_field_label('remark', language))}{separator}{payment_note}"
                )
            elif remark and not remark_is_payee_details_only(remark):
                lines.append(
                    f"{fmt_label(self._get_field_label('remark', language))}{separator}{str(remark).strip()}"
                )
        lines.append(
            f"{fmt_label(self._get_field_label('approval_status', language))}{separator}{status_label}"
        )
        if failure_reason:
            lines.append(
                f"{fmt_label(self._get_field_label('failure_reason', language))}{separator}{failure_reason}"
            )
        lines.extend(self._build_alert_detail_lines(record, language))

        return "\n".join(lines)

    def _get_field_label(self, field_key: str, language: str) -> str:
        labels = {
            "triggered_by": ("触发人", "Triggered By"),
            "trigger_source": ("触发方式", "Trigger Source"),
            "submitter": ("审批发起人", "Approval Initiator"),
            "trigger_reason": ("触发原因", "Trigger Reason"),
            "alert_details": ("告警信息", "Alert Details"),
            "alert_type": ("告警类型", "Alert Type"),
            "current_balance": ("当前余额", "Current Balance"),
            "balance_threshold": ("余额阈值", "Balance Threshold"),
            "current_days_remaining": ("预计剩余天数", "Estimated Days Remaining"),
            "days_remaining_threshold": ("剩余天数阈值", "Days Remaining Threshold"),
            "cloud_provider": ("公有云类型", "Cloud Provider"),
            "recharge_account": ("充值账号", "Recharge Account"),
            "customer_name": ("充值客户", "Customer"),
            "amount": ("付款金额", "Amount"),
            "payment_company": ("付款公司", "Payment Company"),
            "payment_way": ("支付方式", "Payment Way"),
            "payment_type": ("付款类型", "Payment Type"),
            "remit_method": ("付款方式", "Remit Method"),
            "expected_date": ("期望到账时间", "Expected Arrival Date"),
            "payee_account_name": ("收款户名", "Payee Account Name"),
            "payee_bank_name": ("收款银行", "Payee Bank"),
            "approval_status": ("审批状态", "Approval Status"),
            "failure_reason": ("失败原因", "Failure Reason"),
            "remark": ("备注", "Remark"),
        }
        pair = labels.get(field_key, (field_key, field_key))
        return pair[0] if self._is_chinese_language(language) else pair[1]

    def _normalize_language(self, language: str) -> str:
        """Normalize language code to Feishu API format: zh_cn / en_us."""
        raw = str(language or DEFAULT_LANGUAGE).strip()
        normalized = (
            "zh_cn" if raw.lower().startswith("zh") else
            "en_us" if raw.lower().startswith("en") else
            raw
        )
        return normalized

    def _generate_feishu_payload(
        self,
        record: RechargeApprovalRecord,
        notification_type: str,
        language: str,
    ) -> Dict[str, Any]:
        title = self._get_label(
            notification_type, language, self.NOTIFICATION_TYPE_LABELS
        )
        message = self._build_recharge_message(record, notification_type, language)
        content = "\n".join(
            line.strip() for line in message.splitlines() if line.strip()
        )
        return {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True,
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title,
                    },
                    "template": "blue",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": content,
                        },
                    }
                ],
            },
        }

    def _generate_wechat_payload(
        self,
        record: RechargeApprovalRecord,
        notification_type: str,
        language: str,
    ) -> Dict[str, Any]:
        title = self._get_label(
            notification_type, language, self.NOTIFICATION_TYPE_LABELS
        )
        message = self._build_recharge_message(record, notification_type, language)
        rows = []
        for line in message.splitlines():
            if not line.strip():
                continue
            label, value = self._split_label_value(line)
            if value:
                rows.append(f"**{label}**: {value}")
            else:
                rows.append(f"**{label}**" if label else line)
        content = f"## {title}\n" + "\n".join(rows) + "\n\n<@all>"
        return {"msgtype": WECHAT_MSGTYPE_MARKDOWN, "markdown": {"content": content}}

    def _generate_email_subject_and_body(
        self,
        record: RechargeApprovalRecord,
        notification_type: str,
        language: str,
    ) -> tuple[str, str]:
        title = self._get_label(
            notification_type, language, self.NOTIFICATION_TYPE_LABELS
        )
        message = self._build_recharge_message(record, notification_type, language)
        body_lines = []
        for line in message.splitlines():
            if not line.strip():
                body_lines.append("")
                continue
            label, value = self._split_label_value(line)
            body_lines.append(f"**{label}**: {value}" if value else f"**{label}**")
        body = "\n".join(body_lines)
        return title, body

    def _get_channel_config(
        self, record: RechargeApprovalRecord
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Resolve (channel_uuid, channel_type) from provider.config['notification'].
        Returns (channel_uuid, channel_type) or (None, None).
        """
        notification = (record.provider.config or {}).get("notification")
        if not isinstance(notification, dict):
            return None, None
        cu = str(notification.get("channel_uuid") or "").strip()
        ntype = notification.get("type")
        channel_type = None
        if ntype in ("webhook", "email"):
            channel_type = ntype
        return cu or None, channel_type

    def send_recharge_notification(
        self,
        record: RechargeApprovalRecord,
        notification_type: str,
        channel_uuid: Optional[str] = None,
        channel_type: Optional[str] = None,
        synchronous: bool = False,
    ) -> Dict[str, Any]:
        """
        Send recharge approval notification via webhook or email.

        Args:
            record: RechargeApprovalRecord instance
            notification_type: one of submitted / approved / rejected / canceled / failed
            channel_uuid: explicit channel UUID (overrides provider config)
            channel_type: 'webhook' or 'email' (required when channel_uuid is set)
        """
        # Resolve channel from provider config if not explicitly provided
        cfg_uuid, cfg_type = self._get_channel_config(record)
        effective_uuid = channel_uuid or cfg_uuid
        effective_type = channel_type or cfg_type or "webhook"

        if effective_type == "email":
            return self._send_recharge_email(
                record,
                notification_type,
                effective_uuid,
                synchronous=synchronous,
            )
        return self._send_recharge_webhook(
            record,
            notification_type,
            effective_uuid,
            synchronous=synchronous,
        )

    def _send_recharge_webhook(
        self,
        record: RechargeApprovalRecord,
        notification_type: str,
        channel_uuid: Optional[str] = None,
        synchronous: bool = False,
    ) -> Dict[str, Any]:
        # Only pass channel_uuid when it has a real value; otherwise
        # get_webhook_channel_by_uuid(None) raises ValueError(UUID("None")).
        # Passing None means "use default" for the underlying service.
        if channel_uuid:
            channel, config = get_webhook_channel_by_uuid(channel_uuid)
        else:
            channel, config = get_default_webhook_channel()

        if not channel or not config:
            return {
                "success": False,
                "response": None,
                "error": (
                    "Webhook channel not found or inactive"
                    if channel_uuid
                    else "No default webhook channel configured"
                ),
            }

        provider_type = config.get("provider", Provider.FEISHU)
        language = (channel.config or {}).get("language", DEFAULT_LANGUAGE)
        user = record.provider.created_by
        user_id = user.id if user else None

        if provider_type in FEISHU_PROVIDERS:
            payload = self._generate_feishu_payload(
                record, notification_type, language
            )
        elif provider_type == Provider.WECHAT:
            payload = self._generate_wechat_payload(
                record, notification_type, language
            )
        else:
            return {
                "success": False,
                "response": None,
                "error": f"Unsupported webhook provider type: {provider_type}",
            }

        dispatch = send_notification.run if synchronous else send_notification.delay
        result = dispatch(
            notification_type=NOTIFICATION_TYPE_WEBHOOK,
            source_app=SOURCE_APP_CLOUD_BILLING,
            source_type=SOURCE_TYPE_RECHARGE_APPROVAL,
            source_id=str(record.id),
            user_id=user_id,
            channel_uuid=str(channel.uuid),
            params={"payload": payload, "provider_type": provider_type},
        )
        logger.info(
            f"RechargeApprovalNotificationService: webhook notification dispatched "
            f"(record_id={record.id}, notification_type={notification_type}, "
            f"channel_uuid={channel.uuid}, provider_type={provider_type}, "
            f"sync={synchronous})"
        )
        if synchronous and isinstance(result, dict):
            return result
        return {"success": True, "response": None, "error": None}

    def _send_recharge_email(
        self,
        record: RechargeApprovalRecord,
        notification_type: str,
        channel_uuid: Optional[str],
        synchronous: bool = False,
    ) -> Dict[str, Any]:
        if not channel_uuid:
            return {
                "success": False,
                "response": None,
                "error": "Email channel_uuid is required",
            }
        channel, config = get_email_channel_by_uuid(channel_uuid)
        if not channel or not config:
            return {
                "success": False,
                "response": None,
                "error": "Email channel not found or inactive",
            }

        raw = channel.config or {}
        provider_config = record.provider.config or {}
        notification_cfg = provider_config.get("notification") or {}
        email_to = notification_cfg.get("email_to")
        if email_to is not None:
            if isinstance(email_to, list):
                to_addresses = [a.strip() for a in email_to if (a or "").strip()]
            elif isinstance(email_to, str) and email_to.strip():
                to_addresses = [
                    a.strip()
                    for a in email_to.replace(",", " ").split()
                    if a.strip()
                ]
            else:
                to_addresses = []
        else:
            to_list = raw.get("default_to") or raw.get("to")
            if isinstance(to_list, list):
                to_addresses = [a.strip() for a in to_list if (a or "").strip()]
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
            record, notification_type, language
        )
        user = record.provider.created_by
        user_id = user.id if user else None

        dispatch = send_notification.run if synchronous else send_notification.delay
        result = dispatch(
            notification_type=NOTIFICATION_TYPE_EMAIL,
            source_app=SOURCE_APP_CLOUD_BILLING,
            source_type=SOURCE_TYPE_RECHARGE_APPROVAL,
            source_id=str(record.id),
            user_id=user_id,
            channel_uuid=channel_uuid,
            params={"subject": subject, "body": body, "to": to_addresses},
        )
        logger.info(
            f"RechargeApprovalNotificationService: email notification dispatched "
            f"(record_id={record.id}, notification_type={notification_type}, "
            f"channel_uuid={channel_uuid}, to={to_addresses}, sync={synchronous})"
        )
        if synchronous and isinstance(result, dict):
            return result
        return {"success": True, "response": None, "error": None}
