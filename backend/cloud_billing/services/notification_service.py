"""
Notification service for cloud billing alerts.

This service generates notification messages from cloud billing business data
and sends them via agentcore_notifier unified task (send_notification).
Channel selection (webhook/email by UUID or default) is handled by notifier.
Recharge approval copies to their Feishu initiators use the Feishu IM API.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
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
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils import translation
from django.utils.translation import gettext as _

from cloud_billing.alert_messages import (
    build_alert_message_from_record,
    build_alert_sections_from_record,
    extract_account_id_from_message,
    extract_recharge_approval_notice,
)
from cloud_billing.constants import (
    DEFAULT_LANGUAGE,
    SOURCE_APP_CLOUD_BILLING,
    SOURCE_TYPE_ALERT,
    SOURCE_TYPE_RECHARGE_APPROVAL,
    WECHAT_MSGTYPE_MARKDOWN,
)
from cloud_billing.models import (
    AlertRecord,
    BillingData,
    RechargeApprovalRecord,
)
from cloud_billing.services.recharge_approval import (
    PENDING_FEISHU_TASK_STATUSES,
    _get_feishu_access_token,
    find_ongoing_recharge_approval_for_account,
    get_recharge_approval_progress,
    parse_recharge_info,
)

logger = logging.getLogger(__name__)

FEISHU_USER_MESSAGE_URL = (
    "https://open.feishu.cn/open-apis/im/v1/messages"
    "?receive_id_type=user_id"
)
FEISHU_APPROVAL_APPLINK_URL = (
    "https://applink.feishu.cn/client/mini_program/open"
)
FEISHU_APPROVAL_APP_ID = "cli_9cb844403dbb9108"
FEISHU_DISPLAY_TIME_ZONE = dt_timezone(timedelta(hours=8))
APPROVAL_PROGRESS_CACHE_TTL = timedelta(seconds=60)


def _feishu_cost_table(
    items: list,
    currency: str,
    labels: dict,
) -> list:
    """Build Feishu column_set elements for cost breakdown table.

    Returns a title markdown element + header row + data rows.
    Columns: Resource, Cost, Owner (always shown, "-" if empty).
    ``labels`` is the ``sections["labels"]`` dict from
    ``build_alert_sections`` — all strings are pre-localized.
    """
    rows = []

    # Title
    rows.append(
        {
            "tag": "markdown",
            "content": f"**📋 {labels['cost_breakdown']}**",
        }
    )

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
            "elements": [
                {
                    "tag": "markdown",
                    "content": f"**{col}**",
                }
            ],
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
                "elements": [
                    {
                        "tag": "markdown",
                        "content": str(text),
                    }
                ],
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

    def _format_recharge_approval_notice(
        self,
        notice: str,
        label: str,
        separator: str,
    ) -> str:
        """Format approval progress as readable markdown lines."""
        notice = str(notice or "").strip()
        if not notice:
            return ""
        if "；" in notice:
            parts = [
                part.strip()
                for part in notice.split("；")
                if part.strip()
            ]
        elif " Current progress:" in notice:
            summary, progress = notice.split(
                " Current progress:",
                1,
            )
            parts = [summary.strip(), f"Current progress:{progress}"]
        else:
            parts = [notice]

        lines = [f"**{label}**{separator}{parts[0]}"]
        for part in parts[1:]:
            key, value = self._split_label_value(part)
            if value:
                lines.append(f"**{key}**{separator}{value}")
            else:
                lines.append(part)
        return "\n".join(lines)

    def _get_recharge_approval_progress(
        self,
        alert_record: AlertRecord,
    ) -> list[dict[str, Any]]:
        """Return approval nodes associated with an alert, when available."""
        notice = extract_recharge_approval_notice(
            getattr(alert_record, "alert_message", "")
        )
        normalized_notice = notice.lower()
        if (
            "已有充值审批流程正在进行" not in notice
            and "already in progress" not in normalized_notice
        ):
            return []
        account_id = extract_account_id_from_message(
            getattr(alert_record, "alert_message", "")
        )
        if not account_id:
            return []
        approval = find_ongoing_recharge_approval_for_account(
            provider=alert_record.provider,
            recharge_account=account_id,
        )
        if approval is None:
            return []
        cached_progress = (
            approval.context_payload or {}
        ).get("approval_progress")
        if isinstance(cached_progress, list) and cached_progress:
            cached_nodes = [
                node
                for node in cached_progress
                if isinstance(node, dict)
            ]
            cached_node_kinds = {
                str(node.get("node_kind") or "").strip()
                for node in cached_nodes
            }
            has_active_node = any(
                str(node.get("node_kind") or "").strip()
                not in {"start", "end"}
                and str(node.get("status") or "").strip().upper()
                in PENDING_FEISHU_TASK_STATUSES
                for node in cached_nodes
            )
            cached_at = parse_datetime(
                str(
                    (approval.context_payload or {}).get(
                        "approval_progress_cached_at"
                    )
                    or ""
                )
            )
            cache_is_fresh = False
            if cached_at is not None:
                if timezone.is_naive(cached_at):
                    cached_at = timezone.make_aware(cached_at)
                cache_age = timezone.now() - cached_at
                cache_is_fresh = (
                    timedelta(0)
                    <= cache_age
                    <= APPROVAL_PROGRESS_CACHE_TTL
                )
            if (
                {"start", "end"} <= cached_node_kinds
                and has_active_node
                and cache_is_fresh
            ):
                return cached_nodes
        try:
            return get_recharge_approval_progress(approval)
        except Exception:
            logger.warning(
                "Could not load recharge approval progress "
                "(alert_record_id=%s, approval_record_id=%s)",
                getattr(alert_record, "id", None),
                approval.id,
                exc_info=True,
            )
            return []

    def _format_approval_progress_time(self, raw_time: Any) -> str:
        """Format a Feishu millisecond timestamp in China Standard Time."""
        text = str(raw_time or "").strip()
        if not text or not text.isdigit() or int(text) <= 0:
            return ""
        value = datetime.fromtimestamp(
            int(text) / 1000,
            tz=dt_timezone.utc,
        )
        return value.astimezone(FEISHU_DISPLAY_TIME_ZONE).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    def _build_feishu_approval_progress_panel(
        self,
        nodes: list[dict[str, Any]],
        language: str,
    ) -> Optional[dict[str, Any]]:
        """Build a read-only, collapsed approval progress panel."""
        normalized_nodes = [
            node for node in nodes if isinstance(node, dict)
        ]
        if not normalized_nodes:
            return None

        chinese = self._is_chinese_language(language)
        status_labels = {
            "APPROVED": ("已通过", "Approved"),
            "DONE": ("已完成", "Completed"),
            "PENDING": ("等待审批", "Awaiting approval"),
            "APPROVING": ("等待审批", "Awaiting approval"),
            "IN_PROGRESS": ("处理中", "In progress"),
            "REJECTED": ("已拒绝", "Rejected"),
            "CANCELED": ("已撤回", "Cancelled"),
            "TRANSFERRED": ("已转交", "Transferred"),
            "NOT_STARTED": ("尚未开始", "Not started"),
        }
        status_icons = {
            "APPROVED": "✅",
            "DONE": "✅",
            "PENDING": "🟠",
            "APPROVING": "🟠",
            "IN_PROGRESS": "🟠",
            "REJECTED": "❌",
            "CANCELED": "❌",
            "TRANSFERRED": "↪️",
            "NOT_STARTED": "⚪",
        }
        active_statuses = {"PENDING", "APPROVING", "IN_PROGRESS"}
        current_position = sum(
            1
            for node in normalized_nodes
            if str(node.get("status") or "").upper()
            in {
                "APPROVED",
                "DONE",
                "REJECTED",
                "CANCELED",
                "TRANSFERRED",
                *active_statuses,
            }
        )
        current_position = max(1, current_position)
        title = (
            f"审批进度（{current_position}/{len(normalized_nodes)}）"
            if chinese
            else (
                "Approval progress "
                f"({current_position}/{len(normalized_nodes)})"
            )
        )

        progress_lines = []
        for node in normalized_nodes:
            node_kind = str(node.get("node_kind") or "").strip()
            status = str(
                node.get("status") or "NOT_STARTED"
            ).strip().upper()
            status_pair = status_labels.get(
                status,
                (status or "未知", status or "Unknown"),
            )
            status_text = status_pair[0] if chinese else status_pair[1]
            icon = status_icons.get(status, "⚪")
            node_name = str(
                node.get("node_name") or "待审批"
            ).strip()
            if node_kind == "start":
                node_name = "发起" if chinese else "Submitted"
                if status in {"APPROVED", "DONE"}:
                    status_text = "已发起" if chinese else "Submitted"
            elif node_kind == "end":
                node_name = "结束" if chinese else "End"
                end_status_labels = {
                    "NOT_STARTED": ("尚未结束", "Not finished"),
                    "APPROVED": ("已结束", "Finished"),
                    "DONE": ("已结束", "Finished"),
                    "REJECTED": (
                        "已结束（拒绝）",
                        "Finished (rejected)",
                    ),
                    "CANCELED": (
                        "已结束（撤回）",
                        "Finished (cancelled)",
                    ),
                }
                end_status_pair = end_status_labels.get(status)
                if end_status_pair:
                    status_text = (
                        end_status_pair[0]
                        if chinese
                        else end_status_pair[1]
                    )
            approver_names = [
                str(name or "").strip()
                for name in node.get("approver_names") or []
                if str(name or "").strip()
            ]
            approver_text = (
                ("、" if chinese else ", ").join(approver_names)
                or ("待确定" if chinese else "To be determined")
            )
            time_text = self._format_approval_progress_time(
                node.get("end_time") or node.get("start_time")
            )
            if node_kind == "start":
                time_label = "提交时间" if chinese else "Submitted at"
            elif node_kind == "end":
                time_label = "结束时间" if chinese else "Finished at"
            elif status in active_statuses:
                time_label = (
                    "进入节点时间" if chinese else "Entered node at"
                )
            elif status != "NOT_STARTED":
                time_label = "完成时间" if chinese else "Completed at"
            else:
                time_label = ""
            if chinese:
                details = []
                if node_kind == "start" and approver_names:
                    details.append(f"**发起人**：{approver_text}")
                elif node_kind != "end":
                    details.append(f"**审批人**：{approver_text}")
                details.append(f"**状态**：{status_text}")
                if time_text and time_label:
                    details.append(f"**{time_label}**：{time_text}")
            else:
                details = []
                if node_kind == "start" and approver_names:
                    details.append(f"**Initiator**: {approver_text}")
                elif node_kind != "end":
                    details.append(f"**Approver**: {approver_text}")
                details.append(f"**Status**: {status_text}")
                if time_text and time_label:
                    details.append(f"**{time_label}**: {time_text}")
            progress_lines.append(
                "\n".join([f"{icon} **{node_name}**", *details])
            )

        # Source: https://open.feishu.cn/document/feishu-cards/
        # card-components/containers/collapsible-panel
        return {
            "tag": "collapsible_panel",
            "expanded": False,
            "header": {
                "title": {
                    "tag": "markdown",
                    "content": f"**{title}**",
                },
                "vertical_align": "center",
                "icon": {
                    "tag": "standard_icon",
                    "token": "down-small-ccm_outlined",
                    "size": "16px 16px",
                },
                "icon_position": "right",
                "icon_expanded_angle": -180,
            },
            "border": {
                "color": "grey",
                "corner_radius": "5px",
            },
            "vertical_spacing": "8px",
            "padding": "8px 8px 8px 8px",
            "elements": [
                {
                    "tag": "markdown",
                    "content": "\n\n".join(progress_lines),
                }
            ],
        }

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

        Uses a JSON 2.0 card so the approval progress panel can collapse.
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
        elements.append(
            {
                "tag": "markdown",
                "content": (
                    f"{trigger_icon} "
                    f"<font color='orange'>"
                    f"**{trigger_text}**</font>"
                ),
            }
        )

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
            elements.append(
                {
                    "tag": "markdown",
                    "content": "\n".join(info_parts),
                }
            )

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
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": f"{label}\n{val_md}",
                        }
                    ],
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
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": f"{label}\n{val_md}",
                        }
                    ],
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
            elements.append(
                {
                    "tag": "markdown",
                    "content": (
                        f"**{L['current_balance']}**{sep}"
                        f"{bal:.2f} {bal_cur}"
                    ),
                }
            )

        approval_notice = sections.get("recharge_approval_notice")
        if approval_notice:
            elements.append(
                {
                    "tag": "markdown",
                    "content": self._format_recharge_approval_notice(
                        approval_notice,
                        L["recharge_approval"],
                        sep,
                    ),
                }
            )
            progress_panel = (
                self._build_feishu_approval_progress_panel(
                    self._get_recharge_approval_progress(alert_record),
                    language,
                )
            )
            if progress_panel:
                elements.append(progress_panel)

        # ── 7. Footer + @all ──
        elements.append(
            {
                "tag": "markdown",
                "content": (
                    f"<font color='grey'>{L['footer']}</font> "
                    "<at id=all></at>"
                ),
            }
        )

        payload = {
            "msg_type": "interactive",
            "card": {
                "schema": "2.0",
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
                "body": {
                    "elements": elements,
                },
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

        approval_notice = sections.get("recharge_approval_notice")
        if approval_notice:
            rows.append("")
            rows.append(
                self._format_recharge_approval_notice(
                    approval_notice,
                    L["recharge_approval"],
                    sep,
                )
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

        approval_notice = sections.get("recharge_approval_notice")
        if approval_notice:
            rows.append("")
            rows.append(
                self._format_recharge_approval_notice(
                    approval_notice,
                    L["recharge_approval"],
                    sep,
                )
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
    via configured channels and direct copies to their Feishu initiators.
    """

    # Notification type → (Chinese title, English title)
    NOTIFICATION_TYPE_LABELS = {
        "submitted": ("【充值审批】提交成功", "[Recharge Approval] Submission Successful"),
        "approved": ("【充值审批】审批通过", "[Recharge Approval] Approval Passed"),
        "rejected": ("【充值审批】审批被拒绝", "[Recharge Approval] Approval Rejected"),
        "canceled": ("【充值审批】审批已撤回", "[Recharge Approval] Approval Cancelled"),
        "failed": ("【充值审批】提交失败", "[Recharge Approval] Submission Failed"),
        "fulfillment_recovered": (
            "【充值审批】检测到充值到账",
            "[Recharge Approval] Recharge Detected",
        ),
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
        user_id = str(record.resolved_submitter_user_id or "").strip()
        for value in (label, identifier or user_id):
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

    def _build_recovery_detail_lines(
        self,
        record: RechargeApprovalRecord,
        language: str,
        currency: str,
    ) -> list[str]:
        evidence = dict(record.fulfillment_evidence or {})
        signal_details = evidence.get("signal_details") or {}
        balance_details = signal_details.get(
            "balance_threshold_recovered",
            {},
        )
        if not balance_details:
            balance_details = evidence
        baseline = balance_details.get("baseline_balance")
        observed = balance_details.get("observed_balance")
        estimated = (
            evidence.get("estimated_recharge_amount")
            or balance_details.get("estimated_recharge_amount")
        )
        is_ongoing = record.status in {
            RechargeApprovalRecord.STATUS_PENDING,
            RechargeApprovalRecord.STATUS_SUBMITTED,
        }
        flow_status = (
            "仍在审批"
            if is_ongoing and self._is_chinese_language(language)
            else "Still in approval"
            if is_ongoing
            else "已结束"
            if self._is_chinese_language(language)
            else "Finished"
        )
        lines = []
        for label_key, value in (
            ("balance_before_recharge", baseline),
            ("current_balance", observed),
            ("estimated_recharge_amount", estimated),
        ):
            if value not in (None, ""):
                lines.append(
                    f"**{self._get_field_label(label_key, language)}**: "
                    f"{self._format_recharge_amount(value, currency)}"
                )
        lines.append(
            f"**{self._get_field_label('approval_flow', language)}**: "
            f"{flow_status}"
        )
        return lines

    def _build_recharge_message(
        self,
        record: RechargeApprovalRecord,
        notification_type: str,
        language: str,
        current_approvers: Optional[list[str]] = None,
    ) -> str:
        """
        Build a plain-text notification message from a RechargeApprovalRecord.

        If the record's context_payload contains a pre-formatted notification_message
        (generated by the agent), return it directly. Otherwise, build from fields.
        """
        approver_names = []
        for value in current_approvers or []:
            name = str(value or "").strip()
            if name and name not in approver_names:
                approver_names.append(name)
        approver_separator = (
            "、" if self._is_chinese_language(language) else ", "
        )
        current_approver_text = approver_separator.join(approver_names)

        # Agent-generated notification message takes precedence
        agent_msg = str(
            record.context_payload.get("notification_message", "")
        ).strip()
        if agent_msg and notification_type != "fulfillment_recovered":
            if current_approver_text:
                current_approver_label = self._get_field_label(
                    "current_approver",
                    language,
                )
                return (
                    f"{agent_msg}\n**{current_approver_label}**: "
                    f"{current_approver_text}"
                )
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
        instance_code = str(record.feishu_instance_code or "").strip()
        if instance_code:
            instance_label = self._get_field_label(
                "instance_code",
                language,
            )
            lines.append(
                f"{fmt_label(instance_label)}"
                f"{separator}{instance_code}"
            )
        if current_approver_text:
            current_approver_label = self._get_field_label(
                "current_approver",
                language,
            )
            lines.append(
                f"{fmt_label(current_approver_label)}"
                f"{separator}{current_approver_text}"
            )
        if notification_type == "fulfillment_recovered":
            lines.extend(
                self._build_recovery_detail_lines(
                    record,
                    language,
                    currency,
                )
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
            "instance_code": ("审批实例号", "Approval Instance ID"),
            "current_approver": ("当前审批人", "Current Approver"),
            "approval_status": ("审批状态", "Approval Status"),
            "failure_reason": ("失败原因", "Failure Reason"),
            "balance_before_recharge": (
                "充值前余额",
                "Balance Before Recharge",
            ),
            "estimated_recharge_amount": (
                "推定充值金额",
                "Estimated Recharge Amount",
            ),
            "approval_flow": ("审批流程", "Approval Flow"),
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
        current_approvers: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        title = self._get_label(
            notification_type, language, self.NOTIFICATION_TYPE_LABELS
        )
        message = self._build_recharge_message(
            record,
            notification_type,
            language,
            current_approvers=current_approvers,
        )
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

    def _get_direct_recharge_payload(
        self,
        record: RechargeApprovalRecord,
    ) -> Dict[str, Any]:
        payload = dict(record.request_payload or {})
        if not payload and record.raw_recharge_info:
            try:
                payload = parse_recharge_info(record.raw_recharge_info)
            except Exception:
                payload = {}
        return payload

    def _build_direct_recharge_lines(
        self,
        record: RechargeApprovalRecord,
        payload: Dict[str, Any],
    ) -> list:
        provider_name = str(
            record.provider.display_name or record.provider.name or "—"
        ).strip()
        recharge_account = self._stringify_display_value(
            payload.get("recharge_account")
        )
        amount = self._format_recharge_amount(
            payload.get("amount"),
            str(payload.get("currency") or "CNY"),
        )
        initiator = str(record.submitter_user_label or "").strip()
        if not initiator:
            initiator = str(record.submitter_identifier or "").strip()
        if not initiator:
            initiator = (
                "系统自动提交"
                if record.trigger_source
                == RechargeApprovalRecord.TRIGGER_SOURCE_ALERT
                else "—"
            )
        recharge_customer = str(
            payload.get("recharge_customer_name") or ""
        ).strip()
        payment_company = str(
            payload.get("payment_company") or ""
        ).strip()
        recharge_lines = [
            "**💰 充值信息**",
            f"**公有云类型**: {provider_name}",
        ]
        if recharge_customer:
            recharge_lines.append(
                f"**充值客户**: {recharge_customer}"
            )
        recharge_lines.extend(
            [
                f"**充值账号**: {recharge_account}",
                f"**付款金额**: {amount}",
            ]
        )
        if payment_company and payment_company != recharge_customer:
            recharge_lines.append(f"**付款公司**: {payment_company}")
        payment_methods = []
        for value in (
            payload.get("payment_way"),
            payload.get("remit_method"),
        ):
            value_text = str(value or "").strip()
            if value_text and value_text not in payment_methods:
                payment_methods.append(value_text)
        if payment_methods:
            recharge_lines.append(
                f"**支付方式**: {' / '.join(payment_methods)}"
            )
        expected_date = str(payload.get("expected_date") or "").strip()
        if expected_date:
            recharge_lines.append(
                f"**期望到账时间**: {expected_date}"
            )
        recharge_lines.append(f"**审批发起人**: {initiator}")
        return recharge_lines

    def _build_direct_approval_elements(
        self,
        record: RechargeApprovalRecord,
        *,
        current_node: str = "",
        status_label: str = "",
        status_message: str = "",
    ) -> list:
        approval_lines = []
        if current_node:
            approval_lines.append(
                f"**当前审批节点**: {current_node}"
            )
        if status_label:
            approval_lines.append(f"**审批状态**: {status_label}")
        if status_message:
            approval_lines.append(f"**状态说明**: {status_message}")
        approval_lines.append(
            "点击下方“查看审批单”按钮"
            "打开审批实例详情。"
        )
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**🔗 审批实例**",
                },
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "\n".join(approval_lines),
                },
            },
        ]
        detail_action = self._build_approval_detail_action(
            record.feishu_instance_code
        )
        if detail_action:
            elements.append(detail_action)
        return elements

    def _generate_approver_reminder_payload(
        self,
        record: RechargeApprovalRecord,
        *,
        node_name: str,
        escalation_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a direct message for one pending Feishu approver."""
        payload = self._get_direct_recharge_payload(record)
        current_node = self._stringify_display_value(node_name)
        usage_report = self._build_account_usage_report(record, payload)
        recharge_lines = [
            "**你有一笔云账单充值审批需要处理**",
            *self._build_direct_recharge_lines(record, payload),
        ]
        escalation = dict(escalation_context or {})
        level = escalation.get("level")
        elements = []
        if level in {30, 50}:
            currency = str(
                escalation.get("currency") or "CNY"
            ).strip()
            current_balance = self._format_recharge_amount(
                escalation.get("current_balance"),
                currency,
            )
            balance_threshold = self._format_recharge_amount(
                escalation.get("balance_threshold"),
                currency,
            )
            balance_ratio = str(
                escalation.get("balance_ratio") or ""
            ).strip()
            elements.extend(
                [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": "\n".join(
                                [
                                    (
                                        "**余额已低于阈值的 "
                                        f"{level}%，请尽快审批。**"
                                    ),
                                    f"**当前余额**: {current_balance}",
                                    f"**余额阈值**: {balance_threshold}",
                                    f"**余额占比**: {balance_ratio}%",
                                ]
                            ),
                        },
                    },
                    {"tag": "hr"},
                ]
            )
        elements.extend([
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "\n".join(recharge_lines),
                },
            },
            {"tag": "hr"},
        ])
        elements.extend(self._build_usage_report_elements(usage_report))
        elements.append({"tag": "hr"})
        elements.extend(
            self._build_direct_approval_elements(
                record,
                current_node=current_node,
            )
        )
        title = "【待审批】云账单充值申请"
        template = "orange"
        if level == 50:
            title = "【余额告急】云账单充值审批"
            template = "yellow"
        elif level == 30:
            title = "【紧急催办】云账单充值审批"
            template = "red"
        return {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title,
                    },
                    "template": template,
                },
                "elements": elements,
            },
        }

    def _generate_submitter_copy_payload(
        self,
        record: RechargeApprovalRecord,
        notification_type: str,
    ) -> Dict[str, Any]:
        """Build a direct status card for the approval submitter."""
        payload = self._get_direct_recharge_payload(record)
        usage_report = self._build_account_usage_report(record, payload)
        title = self._get_label(
            notification_type,
            DEFAULT_LANGUAGE,
            self.NOTIFICATION_TYPE_LABELS,
        )
        status_label = self._get_label(
            notification_type,
            DEFAULT_LANGUAGE,
            self.STATUS_LABELS,
        )
        status_message = ""
        if notification_type in {"failed", "rejected", "canceled"}:
            status_message = str(record.status_message or "").strip()
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "\n".join(
                        [
                            (
                                "**Tower 平台自动发起了一个"
                                "审批流程。**"
                            ),
                            *self._build_direct_recharge_lines(
                                record,
                                payload,
                            ),
                        ]
                    ),
                },
            },
            {"tag": "hr"},
        ]
        elements.extend(self._build_usage_report_elements(usage_report))
        elements.append({"tag": "hr"})
        elements.extend(
            self._build_direct_approval_elements(
                record,
                status_label=status_label,
                status_message=status_message,
            )
        )
        return {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title,
                    },
                    "template": "blue",
                },
                "elements": elements,
            },
        }

    def _build_account_usage_report(
        self,
        record: RechargeApprovalRecord,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a compact report from the account's latest billing rows."""
        context = dict(record.context_payload or {})
        account_id = str(
            context.get("billing_account_id")
            or payload.get("recharge_account")
            or ""
        ).strip()
        currency = str(payload.get("currency") or "CNY").strip() or "CNY"
        alert = record.alert_record
        report = {
            "account_id": account_id,
            "has_data": False,
            "currency": currency,
            "alert_type": (
                alert.alert_type
                if alert is not None
                else context.get("alert_type")
            ),
            "current_days_remaining": (
                alert.current_days_remaining
                if (
                    alert is not None
                    and alert.current_days_remaining is not None
                )
                else context.get("current_days_remaining")
            ),
            "days_remaining_threshold": (
                alert.days_remaining_threshold
                if (
                    alert is not None
                    and alert.days_remaining_threshold is not None
                )
                else context.get("days_remaining_threshold")
            ),
        }
        if not account_id:
            return report

        rows = list(
            BillingData.objects.filter(
                provider=record.provider,
                account_id=account_id,
                collected_at__gte=timezone.now() - timedelta(hours=24),
            ).order_by(
                "-day",
                "-hour",
                "-collected_at",
            )[:24]
        )
        if not rows:
            return report

        latest = rows[0]
        report["has_data"] = True
        report["currency"] = str(latest.currency or currency).strip()
        report["monthly_cost"] = latest.total_cost
        report["recent_cost"] = sum(
            (
                row.hourly_cost
                for row in rows
                if row.hourly_cost is not None
            ),
            Decimal("0"),
        )
        balance_row = next(
            (row for row in rows if row.balance is not None),
            None,
        )
        report["current_balance"] = (
            balance_row.balance if balance_row is not None else None
        )
        report["balance_threshold"] = self._get_balance_threshold(record)
        report["top_services"] = self._get_top_service_costs(
            latest.service_costs
        )
        return report

    def _get_balance_threshold(
        self,
        record: RechargeApprovalRecord,
    ) -> Optional[Decimal]:
        alert = record.alert_record
        value = (
            alert.balance_threshold
            if alert is not None and alert.balance_threshold is not None
            else (record.context_payload or {}).get("balance_threshold")
        )
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None

    def _get_top_service_costs(
        self,
        service_costs: Any,
    ) -> list:
        if not isinstance(service_costs, dict):
            return []
        normalized = []
        for name, value in service_costs.items():
            try:
                cost = Decimal(str(value))
            except Exception:
                continue
            normalized.append((str(name or "—").strip() or "—", cost))
        normalized.sort(key=lambda item: item[1], reverse=True)
        return normalized[:3]

    def _format_usage_amount(
        self,
        value: Any,
        currency: str,
    ) -> str:
        if value in (None, ""):
            return "—"
        try:
            amount = Decimal(str(value))
        except Exception:
            return self._stringify_display_value(value)
        return f"{amount:,.2f} {currency}"

    def _build_usage_metric_column(
        self,
        label: str,
        value: str,
    ) -> Dict[str, Any]:
        return {
            "tag": "column",
            "width": "weighted",
            "weight": 1,
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**{label}**\n{value}",
                    },
                }
            ],
        }

    def _build_usage_report_elements(
        self,
        report: Dict[str, Any],
    ) -> list:
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**📊 账单概述**",
                },
            }
        ]
        uses_days_remaining = report.get("alert_type") == (
            AlertRecord.ALERT_TYPE_DAYS_REMAINING
        )
        trigger_metrics = None
        if uses_days_remaining:
            current_days = report.get("current_days_remaining")
            threshold_days = report.get("days_remaining_threshold")
            trigger_metrics = (
                (
                    "当前剩余天数",
                    (
                        f"{current_days} 天"
                        if current_days not in (None, "")
                        else "—"
                    ),
                ),
                (
                    "剩余天数阈值",
                    (
                        f"{threshold_days} 天"
                        if threshold_days not in (None, "")
                        else "—"
                    ),
                ),
            )
        if not report.get("has_data"):
            elements.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "暂无该云账号的使用记录。",
                    },
                }
            )
            if trigger_metrics:
                elements.append(
                    {
                        "tag": "column_set",
                        "flex_mode": "stretch",
                        "background_style": "grey",
                        "columns": [
                            self._build_usage_metric_column(
                                label,
                                value,
                            )
                            for label, value in trigger_metrics
                        ],
                    }
                )
            return elements

        currency = str(report.get("currency") or "CNY")
        metric_rows = [
            trigger_metrics or (
                (
                    "当前余额",
                    self._format_usage_amount(
                        report.get("current_balance"),
                        currency,
                    ),
                ),
                (
                    "余额阈值",
                    self._format_usage_amount(
                        report.get("balance_threshold"),
                        currency,
                    ),
                ),
            ),
            (
                (
                    "近24小时消费",
                    self._format_usage_amount(
                        report.get("recent_cost"),
                        currency,
                    ),
                ),
                (
                    "本月累计消费",
                    self._format_usage_amount(
                        report.get("monthly_cost"),
                        currency,
                    ),
                ),
            ),
        ]
        for metrics in metric_rows:
            elements.append(
                {
                    "tag": "column_set",
                    "flex_mode": "stretch",
                    "background_style": "grey",
                    "columns": [
                        self._build_usage_metric_column(label, value)
                        for label, value in metrics
                    ],
                }
            )

        top_services = report.get("top_services") or []
        if top_services:
            service_text = "、".join(
                f"{name} {self._format_usage_amount(cost, currency)}"
                for name, cost in top_services
            )
            elements.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**主要服务消费**: {service_text}"
                        ),
                    },
                }
            )
        return elements

    def _build_approval_detail_action(
        self,
        instance_code: Any,
    ) -> Optional[Dict[str, Any]]:
        instance_code = str(instance_code or "").strip()
        if not instance_code:
            return None
        mobile_url = (
            f"{FEISHU_APPROVAL_APPLINK_URL}?"
            + urllib.parse.urlencode(
                {
                    "appId": FEISHU_APPROVAL_APP_ID,
                    "path": (
                        "pages/detail/index?"
                        f"instanceId={instance_code}"
                    ),
                }
            )
        )
        pc_url = (
            f"{FEISHU_APPROVAL_APPLINK_URL}?"
            + urllib.parse.urlencode(
                {
                    "mode": "appCenter",
                    "appId": FEISHU_APPROVAL_APP_ID,
                    "path": (
                        "pc/pages/in-process/index?"
                        f"instanceId={instance_code}"
                    ),
                }
            )
        )
        return {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {
                        "tag": "plain_text",
                        "content": "查看审批单",
                    },
                    "type": "primary",
                    "multi_url": {
                        "url": mobile_url,
                        "android_url": mobile_url,
                        "ios_url": mobile_url,
                        "pc_url": pc_url,
                    },
                }
            ],
        }

    def _send_feishu_user_card(
        self,
        record: RechargeApprovalRecord,
        *,
        recipient_user_id: str,
        payload: Dict[str, Any],
        log_label: str,
        message_uuid: str = "",
    ) -> Dict[str, Any]:
        """Send one interactive card to a Feishu user_id."""
        token = _get_feishu_access_token()
        if not token:
            return {
                "success": False,
                "skipped": False,
                "recipient_user_id": recipient_user_id,
                "message_id": "",
                "error": "Feishu tenant access token is unavailable",
            }
        request_body = {
            "receive_id": recipient_user_id,
            "msg_type": payload["msg_type"],
            "content": json.dumps(payload["card"], ensure_ascii=False),
        }
        if message_uuid:
            request_body["uuid"] = message_uuid
        request = urllib.request.Request(
            url=FEISHU_USER_MESSAGE_URL,
            data=json.dumps(
                request_body,
                ensure_ascii=False,
            ).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                response_data = json.loads(
                    response.read().decode("utf-8")
                )
        except urllib.error.HTTPError as exc:
            error = f"Feishu message API HTTP error: {exc.code}"
            logger.warning(
                "%s (record_id=%s, recipient_user_id=%s)",
                error,
                record.id,
                recipient_user_id,
            )
            return {
                "success": False,
                "skipped": False,
                "recipient_user_id": recipient_user_id,
                "message_id": "",
                "error": error,
            }
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            error = f"Feishu message API request failed: {exc}"
            logger.warning(
                "%s (record_id=%s, recipient_user_id=%s)",
                error,
                record.id,
                recipient_user_id,
            )
            return {
                "success": False,
                "skipped": False,
                "recipient_user_id": recipient_user_id,
                "message_id": "",
                "error": error,
            }
        code = response_data.get("code")
        if code != 0:
            if code is None:
                error = "Feishu message API response missing success code"
            else:
                error = (
                    f"Feishu message API error {code}: "
                    f"{response_data.get('msg', '')}"
                )
            logger.warning(
                "%s (record_id=%s, recipient_user_id=%s)",
                error,
                record.id,
                recipient_user_id,
            )
            return {
                "success": False,
                "skipped": False,
                "recipient_user_id": recipient_user_id,
                "message_id": "",
                "error": error,
            }
        message_id = str(
            (response_data.get("data") or {}).get("message_id") or ""
        ).strip()
        if not message_id:
            return {
                "success": False,
                "skipped": False,
                "recipient_user_id": recipient_user_id,
                "message_id": "",
                "error": "Feishu message API response missing message_id",
            }
        logger.info(
            "%s (record_id=%s, recipient_user_id=%s, message_id=%s)",
            log_label,
            record.id,
            recipient_user_id,
            message_id,
        )
        return {
            "success": True,
            "skipped": False,
            "recipient_user_id": recipient_user_id,
            "message_id": message_id,
            "error": None,
        }

    def send_approver_reminder(
        self,
        record: RechargeApprovalRecord,
        *,
        recipient_user_id: str,
        node_name: str,
        escalation_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Notify one current approver through Feishu direct message."""
        recipient_user_id = str(recipient_user_id or "").strip()
        if not recipient_user_id:
            return {
                "success": False,
                "skipped": True,
                "recipient_user_id": "",
                "message_id": "",
                "error": "Approver user_id is unavailable",
            }
        payload = self._generate_approver_reminder_payload(
            record,
            node_name=node_name,
            escalation_context=escalation_context,
        )
        level = (escalation_context or {}).get("level")
        notification_key = (
            f"balance_{level}" if level in {30, 50} else "pending"
        )
        message_uuid = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                (
                    "devmind:recharge-approver:"
                    f"{record.id}:{recipient_user_id}:"
                    f"{notification_key}"
                ),
            )
        )
        return self._send_feishu_user_card(
            record,
            recipient_user_id=recipient_user_id,
            payload=payload,
            log_label="Recharge approval reminder sent to Feishu approver",
            message_uuid=message_uuid,
        )

    def send_submitter_copy(
        self,
        record: RechargeApprovalRecord,
        notification_type: str,
    ) -> Dict[str, Any]:
        """Send an approval notification card to its Feishu initiator."""
        recipient_user_id = str(
            record.resolved_submitter_user_id or ""
        ).strip()
        if not recipient_user_id:
            logger.info(
                "Recharge approval submitter copy skipped: no resolved "
                "Feishu user_id (record_id=%s)",
                record.id,
            )
            return {
                "success": True,
                "skipped": True,
                "recipient_user_id": "",
                "message_id": "",
                "error": None,
            }

        payload = self._generate_submitter_copy_payload(
            record,
            notification_type,
        )
        message_uuid = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                (
                    "devmind:recharge-submitter:"
                    f"{record.id}:{notification_type}"
                ),
            )
        )
        return self._send_feishu_user_card(
            record,
            recipient_user_id=recipient_user_id,
            payload=payload,
            log_label="Recharge approval copied to Feishu submitter",
            message_uuid=message_uuid,
        )

    def _generate_wechat_payload(
        self,
        record: RechargeApprovalRecord,
        notification_type: str,
        language: str,
        current_approvers: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        title = self._get_label(
            notification_type, language, self.NOTIFICATION_TYPE_LABELS
        )
        message = self._build_recharge_message(
            record,
            notification_type,
            language,
            current_approvers=current_approvers,
        )
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
        current_approvers: Optional[list[str]] = None,
    ) -> tuple[str, str]:
        title = self._get_label(
            notification_type, language, self.NOTIFICATION_TYPE_LABELS
        )
        message = self._build_recharge_message(
            record,
            notification_type,
            language,
            current_approvers=current_approvers,
        )
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
        current_approvers: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        """
        Send recharge approval notification via webhook or email.

        Args:
            record: RechargeApprovalRecord instance
            notification_type: one of submitted / approved / rejected / canceled / failed
            channel_uuid: explicit channel UUID (overrides provider config)
            channel_type: 'webhook' or 'email' (required when channel_uuid is set)
            current_approvers: readable names for live pending approvers
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
                current_approvers=current_approvers,
            )
        return self._send_recharge_webhook(
            record,
            notification_type,
            effective_uuid,
            synchronous=synchronous,
            current_approvers=current_approvers,
        )

    def _send_recharge_webhook(
        self,
        record: RechargeApprovalRecord,
        notification_type: str,
        channel_uuid: Optional[str] = None,
        synchronous: bool = False,
        current_approvers: Optional[list[str]] = None,
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
                record,
                notification_type,
                language,
                current_approvers=current_approvers,
            )
        elif provider_type == Provider.WECHAT:
            payload = self._generate_wechat_payload(
                record,
                notification_type,
                language,
                current_approvers=current_approvers,
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
        current_approvers: Optional[list[str]] = None,
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
            record,
            notification_type,
            language,
            current_approvers=current_approvers,
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
