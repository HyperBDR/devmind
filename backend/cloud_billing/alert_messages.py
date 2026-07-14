"""Helpers for generating localized cloud billing alert messages."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Optional

from django.utils import translation
from django.utils.translation import gettext as _

from .constants import DEFAULT_LANGUAGE


def is_chinese_language(language: str) -> bool:
    return str(language or "").lower().startswith("zh")


def _format_resource_cost_lines(
    resource_cost_items: list,
    currency: str,
    normalized_language: str,
    cost_period_label: str,
    max_items: int = 10,
) -> list[str]:
    """Format resource cost items as a table.

    Table layout with columns: Resource, Cost, Creator.
    Plain strings (no label:value separator) for table rows,
    so notification service renders them as raw text.
    """
    cost_breakdown_label = localized_text(
        normalized_language,
        "Cost Breakdown",
        "费用明细",
    )
    header = f"{cost_period_label} {cost_breakdown_label}"
    header += "：" if is_chinese_language(normalized_language) else ": "

    if is_chinese_language(normalized_language):
        col_resource = "资源"
        col_cost = "费用"
        col_creator = "创建者"
    else:
        col_resource = "Resource"
        col_cost = "Cost"
        col_creator = "Creator"

    lines = [header]

    if not resource_cost_items:
        return lines

    has_owner = any(
        item.get("owner", "") for item in resource_cost_items
    )

    if has_owner:
        col_w = 32
        cost_w = 14
        lines.append(
            f"  {col_resource:<{col_w}}"
            f"{col_cost:<{cost_w}}"
            f"{col_creator}"
        )
        lines.append(
            f"  {'─' * col_w}{'─' * cost_w}{'─' * 12}"
        )
    else:
        col_w = 40
        cost_w = 14
        lines.append(
            f"  {col_resource:<{col_w}}{col_cost}"
        )
        lines.append(
            f"  {'─' * col_w}{'─' * cost_w}"
        )

    for item in resource_cost_items[:max_items]:
        item_name = item.get(
            "name", item.get("service_name", "Unknown")
        )
        item_cost = float(item.get("cost", 0))
        owner = item.get("owner", "")
        cost_str = f"{item_cost:.2f} {currency}"

        if has_owner:
            row = (
                f"  {item_name:<{col_w}}"
                f"{cost_str:<{cost_w}}"
                f"{owner}"
            )
        else:
            row = (
                f"  {item_name:<{col_w}}{cost_str}"
            )
        lines.append(row)

    return lines


def localized_text(language: str, english: str, chinese: str) -> str:
    return chinese if is_chinese_language(language) else _(english)


def format_alert_line(
    label: str,
    value: str,
    *,
    language: str,
) -> str:
    separator = "：" if is_chinese_language(language) else ": "
    return f"{label}{separator}{value}"


def extract_provider_notes(provider) -> str:
    direct_notes = (getattr(provider, "notes", "") or "").strip()
    if direct_notes:
        return direct_notes

    config = getattr(provider, "config", {}) or {}
    for key in ("notes", "note", "remark", "remarks", "description"):
        value = (config.get(key) or "").strip() if isinstance(config, dict) else ""
        if value:
            return value
    return ""


def extract_provider_tags(provider) -> list[str]:
    """Return normalized provider tags for alert messages."""
    raw_tags = getattr(provider, "tags", []) or []
    normalized_tags = []
    seen = set()
    for tag in raw_tags:
        value = str(tag or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized_tags.append(value)
    return normalized_tags


def format_provider_tags(tags: list[str], language: str) -> str:
    """Format provider tags for localized alert messages."""
    normalized_tags = [str(tag or "").strip() for tag in tags if str(tag or "").strip()]
    if not normalized_tags:
        return ""
    separator = "、" if is_chinese_language(language) else ", "
    return separator.join(normalized_tags)


def build_recharge_approval_notice(
    language: str,
    *,
    existing_approval: bool = False,
    current_approvers: Optional[list[str]] = None,
) -> str:
    """Return the localized auto recharge approval notice."""
    if existing_approval:
        approvers = [
            str(value or "").strip()
            for value in current_approvers or []
            if str(value or "").strip()
        ]
        approver_text = (
            ("、" if is_chinese_language(language) else ", ").join(
                approvers
            )
            or localized_text(
                language,
                "Pending node information",
                "节点信息同步中",
            )
        )
        return localized_text(
            language,
            (
                "A recharge approval workflow is already in progress. "
                "Current progress: awaiting approval. Current approver: "
                f"{approver_text}."
            ),
            (
                "已有充值审批流程正在进行；当前进度：等待审批；"
                f"当前审批人：{approver_text}。"
            ),
        )
    return localized_text(
        language,
        (
            "The recharge approval workflow has been triggered "
            "automatically. Current progress: creating the approval "
            "request. The current approver and node will be sent after "
            "submission."
        ),
        (
            "已自动触发充值审批；当前进度：正在创建审批单。"
            "提交成功后将同步当前审批人及节点。"
        ),
    )


def extract_recharge_approval_notice(message: str) -> str:
    """Extract persisted auto recharge approval notice from alert text."""
    for raw_line in str(message or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        has_notice = (
            "自动触发充值审批" in line
            or "已有充值审批流程正在进行" in line
            or "recharge approval workflow has been triggered" in line.lower()
            or "recharge approval workflow is already in progress"
            in line.lower()
        )
        if not has_notice:
            continue
        for separator in ("：", ": "):
            if separator in line:
                return line.split(separator, 1)[1].strip()
        return line
    return ""


def extract_account_id_from_message(message: str) -> str:
    for raw_line in str(message or "").splitlines():
        line = raw_line.strip()
        for prefix in ("Account:", "Account：", "账号:", "账号："):
            if line.startswith(prefix):
                return line[len(prefix):].strip()
    return ""


def build_alert_message(
    *,
    provider_name: str,
    provider_notes: str,
    provider_tags: list[str],
    account_id: str,
    current_cost,
    previous_cost,
    increase_cost,
    increase_percent,
    current_balance,
    current_days_remaining,
    currency: str,
    alert_rule,
    cost_threshold_triggered: bool,
    balance_threshold_triggered: bool,
    days_remaining_threshold_triggered: bool,
    language: str,
    alert_type: Optional[str] = None,
    resource_cost_items: Optional[list] = None,
    cost_period: str = "today",
    auto_recharge_approval_triggered: bool = False,
    recharge_approval_notice: Optional[str] = None,
) -> str:
    raw_language = str(language or DEFAULT_LANGUAGE).strip()
    normalized_language = (
        "zh_Hans" if raw_language.lower().startswith("zh") else raw_language.lower()
    )

    with translation.override(normalized_language):
        # Cost period label for resource breakdown
        if cost_period == "today":
            cost_period_label = localized_text(normalized_language, "Today's", "当天")
        else:
            cost_period_label = localized_text(normalized_language, "Month's", "当月")

        lines = [
            format_alert_line(
                localized_text(normalized_language, "Cloud provider", "公有云类型"),
                provider_name,
                language=normalized_language,
            ),
        ]
        if account_id:
            lines.append(
                format_alert_line(
                    localized_text(normalized_language, "Account", "账号"),
                    account_id,
                    language=normalized_language,
                )
            )
        if provider_notes:
            lines.append(
                format_alert_line(
                    localized_text(normalized_language, "Notes", "备注"),
                    provider_notes,
                    language=normalized_language,
                )
            )
        if provider_tags:
            lines.append(
                format_alert_line(
                    "标签" if is_chinese_language(normalized_language) else _("Tags"),
                    format_provider_tags(provider_tags, normalized_language),
                    language=normalized_language,
                )
            )

        effective_alert_type = str(alert_type or "").strip().lower()
        approval_notice = recharge_approval_notice or (
            build_recharge_approval_notice(normalized_language)
            if auto_recharge_approval_triggered
            else ""
        )

        def append_recharge_approval_notice():
            if approval_notice:
                lines.append(
                    format_alert_line(
                        localized_text(
                            normalized_language,
                            "Recharge approval",
                            "充值审批",
                        ),
                        approval_notice,
                        language=normalized_language,
                    )
                )

        if (
            effective_alert_type == "balance"
            or balance_threshold_triggered
        ):
            lines.insert(
                0,
                format_alert_line(
                    localized_text(normalized_language, "Alert type", "告警类型"),
                    localized_text(
                        normalized_language,
                        "Balance threshold alert",
                        "余额阈值告警",
                    ),
                    language=normalized_language,
                ),
            )
            lines.append(
                format_alert_line(
                    localized_text(
                        normalized_language, "Current balance", "当前余额"
                    ),
                    f"{current_balance:.2f} {currency}",
                    language=normalized_language,
                )
            )
            lines.append(
                format_alert_line(
                    localized_text(
                        normalized_language, "Alert threshold", "告警阈值"
                    ),
                    f"{alert_rule.balance_threshold:.2f} {currency}",
                    language=normalized_language,
                )
            )
            lines.append(
                format_alert_line(
                    localized_text(
                        normalized_language,
                        "Alert description",
                        "告警说明",
                    ),
                    localized_text(
                        normalized_language,
                        "Remaining balance is below the configured threshold. "
                        "Please recharge promptly.",
                        "账户剩余余额低于设定阈值，请及时充值",
                    ),
                    language=normalized_language,
                )
            )
            append_recharge_approval_notice()
            if resource_cost_items:
                lines.extend(_format_resource_cost_lines(
                    resource_cost_items, currency, normalized_language,
                    cost_period_label,
                ))
            return "\n".join(lines)

        if (
            effective_alert_type == "days_remaining"
            or days_remaining_threshold_triggered
        ):
            lines.insert(
                0,
                format_alert_line(
                    localized_text(normalized_language, "Alert type", "告警类型"),
                    localized_text(
                        normalized_language,
                        "Estimated days remaining alert",
                        "预计使用天数告警",
                    ),
                    language=normalized_language,
                ),
            )
            lines.append(
                format_alert_line(
                    localized_text(
                        normalized_language, "Current balance", "当前余额"
                    ),
                    f"{current_balance:.2f} {currency}",
                    language=normalized_language,
                )
            )
            lines.append(
                format_alert_line(
                    localized_text(
                        normalized_language,
                        "Estimated days remaining",
                        "预计使用天数",
                    ),
                    str(current_days_remaining),
                    language=normalized_language,
                )
            )
            lines.append(
                format_alert_line(
                    localized_text(
                        normalized_language, "Alert threshold", "告警阈值"
                    ),
                    str(alert_rule.days_remaining_threshold),
                    language=normalized_language,
                )
            )
            lines.append(
                format_alert_line(
                    localized_text(
                        normalized_language,
                        "Alert description",
                        "告警说明",
                    ),
                    localized_text(
                        normalized_language,
                        "Projected remaining days are below the configured "
                        "threshold. Please recharge promptly.",
                        "预计使用天数低于设定阈值，请及时充值",
                    ),
                    language=normalized_language,
                )
            )
            append_recharge_approval_notice()
            if resource_cost_items:
                lines.extend(_format_resource_cost_lines(
                    resource_cost_items, currency, normalized_language,
                    cost_period_label,
                ))
            return "\n".join(lines)

        if (
            effective_alert_type == "cost"
            or cost_threshold_triggered
        ):
            lines.insert(
                0,
                format_alert_line(
                    localized_text(normalized_language, "Alert type", "告警类型"),
                    localized_text(
                        normalized_language,
                        "Cost threshold alert",
                        "成本阈值告警",
                    ),
                    language=normalized_language,
                ),
            )
            # 当前小时累计 + 上一小时在一行
            lines.append(
                f"{localized_text(normalized_language, 'Month total', '当月累计')}"
                f"{'：' if is_chinese_language(normalized_language) else ': '}"
                f"{current_cost:.2f} {currency}"
                f"    "
                f"{localized_text(normalized_language, 'Previous hour', '上一小时')}"
                f"{'：' if is_chinese_language(normalized_language) else ': '}"
                f"{previous_cost:.2f} {currency}"
            )
            # 金额 + 金额阈值在一行
            lines.append(
                f"{localized_text(normalized_language, 'Amount', '金额')}"
                f"{'：' if is_chinese_language(normalized_language) else ': '}"
                f"{current_cost:.2f} {currency}"
                f"    "
                f"{localized_text(normalized_language, 'Amount threshold', '金额阈值')}"
                f"{'：' if is_chinese_language(normalized_language) else ': '}"
                f"{alert_rule.cost_threshold:.2f} {currency}"
            )
            if resource_cost_items:
                lines.extend(_format_resource_cost_lines(
                    resource_cost_items, currency, normalized_language,
                    cost_period_label,
                ))
            lines.append(
                format_alert_line(
                    localized_text(
                        normalized_language,
                        "Alert description",
                        "告警说明",
                    ),
                    localized_text(
                        normalized_language,
                        "Current total cost exceeds the configured threshold",
                        "当前累计成本已超过设定阈值",
                    ),
                    language=normalized_language,
                )
            )
            return "\n".join(lines)

        lines.insert(
            0,
            format_alert_line(
                localized_text(normalized_language, "Alert type", "告警类型"),
                localized_text(
                    normalized_language,
                    "Cost growth alert",
                    "成本增长告警",
                ),
                language=normalized_language,
            ),
        )
        # 当前小时累计 + 上一小时在一行
        lines.append(
            f"{localized_text(normalized_language, 'Month total', '当月累计')}"
            f"{'：' if is_chinese_language(normalized_language) else ': '}"
            f"{current_cost:.2f} {currency}"
            f"    "
            f"{localized_text(normalized_language, 'Previous hour', '上一小时')}"
            f"{'：' if is_chinese_language(normalized_language) else ': '}"
            f"{previous_cost:.2f} {currency}"
        )
        # 金额 + 金额阈值在一行
        amount_label = (
            localized_text(normalized_language, "Increase amount", "增加金额")
        )
        amount_value = f"{increase_cost:.2f} {currency}"
        amount_threshold_line = ""
        if alert_rule.growth_amount_threshold is not None:
            amount_threshold_line = (
                f"    "
                f"{localized_text(normalized_language, 'Amount threshold', '金额阈值')}"
                f"{'：' if is_chinese_language(normalized_language) else ': '}"
                f"{alert_rule.growth_amount_threshold:.2f} {currency}"
            )
        sep = '：' if is_chinese_language(normalized_language) else ': '
        lines.append(f"{amount_label}{sep}{amount_value}{amount_threshold_line}")
        # 增长率 + 百分比阈值在一行（当前值在左，对照值在右）
        if alert_rule.growth_threshold is not None:
            lines.append(
                f"{localized_text(normalized_language, 'Growth rate', '增长率')}"
                f"{'：' if is_chinese_language(normalized_language) else ': '}"
                f"{increase_percent:.2f}%"
                f"    "
                f"{localized_text(normalized_language, 'Percentage threshold', '百分比阈值')}"
                f"{'：' if is_chinese_language(normalized_language) else ': '}"
                f"{alert_rule.growth_threshold:.2f}%"
            )
        else:
            lines.append(
                f"{localized_text(normalized_language, 'Growth rate', '增长率')}"
                f"{'：' if is_chinese_language(normalized_language) else ': '}"
                f"{increase_percent:.2f}%"
            )
        if resource_cost_items:
            lines.extend(_format_resource_cost_lines(
                resource_cost_items, currency, normalized_language,
                cost_period_label,
            ))
        lines.append(
            format_alert_line(
                localized_text(
                    normalized_language,
                    "Alert description",
                    "告警说明",
                ),
                localized_text(
                    normalized_language,
                    "Billing growth exceeds the configured threshold",
                    "账单增长已超过设定阈值",
                ),
                language=normalized_language,
            )
        )
        return "\n".join(lines)


# ── Structured sections for rich rendering ──────────────────


def build_alert_sections(
    *,
    provider_name: str,
    provider_notes: str,
    provider_tags: list[str],
    account_id: str,
    current_cost,
    previous_cost,
    increase_cost,
    increase_percent,
    current_balance,
    current_days_remaining,
    currency: str,
    alert_rule,
    cost_threshold_triggered: bool,
    balance_threshold_triggered: bool,
    days_remaining_threshold_triggered: bool,
    language: str,
    alert_type: Optional[str] = None,
    resource_cost_items: Optional[list] = None,
    cost_period: str = "today",
    auto_recharge_approval_triggered: bool = False,
    recharge_approval_notice: Optional[str] = None,
) -> dict:
    """Return structured alert data for rich rendering.

    Returns a dict with named sections that notification services
    can render as Feishu cards, markdown tables, etc.

    All user-facing text is localized via Django gettext inside a
    ``translation.override`` context manager so callers never need
    to handle i18n themselves.
    """
    raw_language = str(language or DEFAULT_LANGUAGE).strip()
    normalized_language = (
        "zh_Hans"
        if raw_language.lower().startswith("zh")
        else raw_language.lower()
    )

    with translation.override(normalized_language):
        return _build_alert_sections_inner(
            provider_name=provider_name,
            provider_notes=provider_notes,
            provider_tags=provider_tags,
            account_id=account_id,
            current_cost=current_cost,
            previous_cost=previous_cost,
            increase_cost=increase_cost,
            increase_percent=increase_percent,
            current_balance=current_balance,
            current_days_remaining=current_days_remaining,
            currency=currency,
            alert_rule=alert_rule,
            cost_threshold_triggered=cost_threshold_triggered,
            balance_threshold_triggered=balance_threshold_triggered,
            days_remaining_threshold_triggered=days_remaining_threshold_triggered,
            alert_type=alert_type,
            resource_cost_items=resource_cost_items,
            normalized_language=normalized_language,
            cost_period=cost_period,
            auto_recharge_approval_triggered=(
                auto_recharge_approval_triggered
            ),
            recharge_approval_notice=recharge_approval_notice,
        )


def _build_alert_sections_inner(
    *,
    provider_name,
    provider_notes,
    provider_tags,
    account_id,
    current_cost,
    previous_cost,
    increase_cost,
    increase_percent,
    current_balance,
    current_days_remaining,
    currency,
    alert_rule,
    cost_threshold_triggered,
    balance_threshold_triggered,
    days_remaining_threshold_triggered,
    alert_type=None,
    resource_cost_items=None,
    normalized_language="en",
    cost_period: str = "today",
    auto_recharge_approval_triggered: bool = False,
    recharge_approval_notice: Optional[str] = None,
) -> dict:
    """Inner builder — all ``_()`` calls resolve under the active language."""

    effective_alert_type = str(alert_type or "").strip().lower()

    def label(english: str, chinese: str) -> str:
        return localized_text(
            normalized_language,
            english,
            chinese,
        )

    # ── Determine alert type label and trigger ──
    # NOTE: _() must be called on the raw template string BEFORE .format()
    # substitution, otherwise Python evaluates the format first and _()
    # receives an already-interpolated string that won't match any .po entry.
    if effective_alert_type == "balance" or balance_threshold_triggered:
        type_label = _("Balance Alert")
        trigger_icon = "💰"
        if current_balance is not None and alert_rule.balance_threshold:
            trigger_text = label(
                (
                    f"Balance {current_balance:.2f} {currency} below "
                    f"threshold {alert_rule.balance_threshold:.2f} "
                    f"{currency}"
                ),
                (
                    f"余额 {current_balance:.2f} {currency} 低于阈值 "
                    f"{alert_rule.balance_threshold:.2f} {currency}"
                ),
            )
        else:
            trigger_text = label(type_label, "余额阈值告警")
    elif (
        effective_alert_type == "days_remaining"
        or days_remaining_threshold_triggered
    ):
        type_label = _("Days Remaining Alert")
        trigger_icon = "⏳"
        trigger_text = label(
            (
                f"{current_days_remaining} days remaining below "
                f"threshold {alert_rule.days_remaining_threshold}"
            ),
            (
                f"预计剩余 {current_days_remaining} 天，低于阈值 "
                f"{alert_rule.days_remaining_threshold} 天"
            ),
        )
    elif effective_alert_type == "cost" or cost_threshold_triggered:
        type_label = _("Cost Threshold Alert")
        trigger_icon = "📊"
        trigger_text = label(
            (
                f"Total cost {current_cost:.2f} {currency} exceeds "
                f"threshold {alert_rule.cost_threshold:.2f} {currency}"
            ),
            (
                f"总费用 {current_cost:.2f} {currency} 超过阈值 "
                f"{alert_rule.cost_threshold:.2f} {currency}"
            ),
        )
    else:
        type_label = _("Cost Growth Alert")
        trigger_icon = "📈"
        parts = []
        if increase_percent > 0:
            parts.append(
                label(
                    f"Growth {increase_percent:.1f}%",
                    f"增长率 {increase_percent:.1f}%",
                )
            )
        if alert_rule.growth_threshold is not None:
            parts.append(
                label(
                    f"threshold {alert_rule.growth_threshold:.1f}%",
                    f"阈值 {alert_rule.growth_threshold:.1f}%",
                )
            )
        joined = ("、" if is_chinese_language(
            normalized_language
        ) else ", ").join(parts)
        trigger_text = joined if joined else label(
            type_label,
            "费用增长告警",
        )

    # ── Structural labels (single source of truth) ──
    # Determine period-specific labels
    if cost_period == "today":
        cost_breakdown_label = label(
            "Today's Cost Breakdown",
            "当天 费用明细",
        )
        col_cost_label = label("Today's Cost", "当天费用")
    else:
        cost_breakdown_label = label(
            "Month's Cost Breakdown",
            "当月 费用明细",
        )
        col_cost_label = label("Month's Cost", "当月费用")

    labels = {
        "provider": label("Provider", "公有云类型"),
        "account": label("Account", "账号"),
        "notes": label("Notes", "备注"),
        "tags": label("Tags", "标签"),
        "balance_threshold": label(
            "Balance Threshold",
            "余额阈值",
        ),
        "current_balance": label("Current Balance", "当前余额"),
        "cost_breakdown": cost_breakdown_label,
        "col_resource": label("Resource", "资源"),
        "col_cost": col_cost_label,
        "col_owner": label("Owner", "负责人"),
        "footer": label(
            "DevMind Cloud Billing · @all",
            "DevMind 云账单 · @所有人",
        ),
        "sep": "：" if is_chinese_language(
            normalized_language
        ) else ": ",
        "current_hour_cost": label("Current Hour Cost", "当前小时费用"),
        "previous_hour_cost": label("Previous Hour Cost", "上一小时费用"),
        "growth_rate": label("Growth Rate", "增长率"),
        "increase_amount": label("Increase Amount", "增长金额"),
        "growth_percentage_threshold": label(
            "Growth Percentage Threshold",
            "百分比阈值",
        ),
        "amount_threshold": label("Amount Threshold", "金额阈值"),
        "cost_threshold": label("Cost Threshold", "成本阈值"),
        "recharge_approval": localized_text(
            normalized_language,
            "Recharge Approval",
            "充值审批",
        ),
    }

    # ── Build sections ──
    sections = {
        "alert_type": type_label,
        "trigger_icon": trigger_icon,
        "trigger_text": trigger_text,
        "provider": provider_name,
        "account_id": account_id,
        "notes": provider_notes,
        "tags": provider_tags,
        "currency": currency,
        "labels": labels,
        "metrics": [],
        "thresholds": [],
        "resource_costs": resource_cost_items or [],
        "balance": None,
        "recharge_approval_notice": (
            recharge_approval_notice
            or (
                build_recharge_approval_notice(normalized_language)
                if auto_recharge_approval_triggered
                else ""
            )
        ),
    }

    # ── Key metrics ──
    if (effective_alert_type == "growth" or effective_alert_type == "") and not (
        balance_threshold_triggered
        or days_remaining_threshold_triggered
        or cost_threshold_triggered
    ):
        sections["metrics"] = [
            {
                "label": labels["current_hour_cost"],
                "value": f"{current_cost:.2f}",
                "highlight": False,
            },
            {
                "label": labels["previous_hour_cost"],
                "value": f"{previous_cost:.2f}",
                "highlight": False,
            },
            {
                "label": labels["increase_amount"],
                "value": f"{increase_cost:.2f}",
                "highlight": True,
            },
            {
                "label": labels["growth_rate"],
                "value": f"{increase_percent:.1f}%",
                "highlight": True,
            },
        ]
    elif (
        effective_alert_type == "cost" or cost_threshold_triggered
    ):
        sections["metrics"] = [
            {
                "label": labels["current_hour_cost"],
                "value": f"{current_cost:.2f}",
                "highlight": True,
            },
            {
                "label": labels["previous_hour_cost"],
                "value": f"{previous_cost:.2f}",
                "highlight": False,
            },
            {
                "label": labels["growth_rate"],
                "value": f"{increase_percent:.1f}%",
                "highlight": False,
            },
            {
                "label": labels["increase_amount"],
                "value": f"{increase_cost:.2f}",
                "highlight": False,
            },
        ]

    # ── Thresholds ──
    if alert_rule.growth_threshold is not None:
        sections["thresholds"].append({
            "label": labels["growth_percentage_threshold"],
            "value": f"{alert_rule.growth_threshold:.1f}%",
        })
    if alert_rule.growth_amount_threshold is not None:
        sections["thresholds"].append({
            "label": labels["amount_threshold"],
            "value": (
                f"{alert_rule.growth_amount_threshold:.2f}"
                f" {currency}"
            ),
        })
    if alert_rule.cost_threshold is not None:
        sections["thresholds"].append({
            "label": labels["cost_threshold"],
            "value": f"{alert_rule.cost_threshold:.2f} {currency}",
        })
    if alert_rule.balance_threshold is not None:
        sections["thresholds"].append({
            "label": labels["balance_threshold"],
            "value": (
                f"{alert_rule.balance_threshold:.2f} {currency}"
            ),
        })

    # ── Balance ──
    if current_balance is not None:
        sections["balance"] = {
            "value": current_balance,
            "currency": currency,
        }

    return sections


def build_alert_sections_from_record(
    alert_record,
    language: str,
    resource_cost_items: Optional[list] = None,
) -> dict:
    """Build structured alert sections from an AlertRecord."""
    if not resource_cost_items:
        resource_cost_items = getattr(
            alert_record, "resource_cost_details", None
        ) or []
    alert_rule = alert_record.alert_rule or SimpleNamespace(
        cost_threshold=None,
        growth_threshold=None,
        growth_amount_threshold=None,
        balance_threshold=alert_record.balance_threshold,
        days_remaining_threshold=alert_record.days_remaining_threshold,
    )
    current_balance = getattr(alert_record, "current_balance", None)
    alert_type = getattr(alert_record, "alert_type", None)
    balance_threshold = getattr(alert_record, "balance_threshold", None)
    current_days_remaining = getattr(
        alert_record, "current_days_remaining", None
    )
    days_remaining_threshold = getattr(
        alert_record, "days_remaining_threshold", None,
    )
    current_cost = getattr(alert_record, "current_cost", 0)
    recharge_approval_notice = extract_recharge_approval_notice(
        getattr(alert_record, "alert_message", "")
    )

    balance_threshold_triggered = (
        alert_type == "balance"
        or (
            current_balance is not None
            and balance_threshold is not None
            and current_balance < balance_threshold
        )
    )
    cost_threshold = getattr(alert_rule, "cost_threshold", None)
    cost_threshold_triggered = (
        alert_type == "cost"
        or (
            not balance_threshold_triggered
            and current_days_remaining is None
            and cost_threshold is not None
            and current_cost > cost_threshold
        )
    )
    days_remaining_threshold_triggered = (
        alert_type == "days_remaining"
        or (
            not balance_threshold_triggered
            and current_days_remaining is not None
            and days_remaining_threshold is not None
            and current_days_remaining < days_remaining_threshold
        )
    )

    # Get cost_period from record (defaults to "today" if not set)
    cost_period = getattr(alert_record, "cost_period", None) or "today"

    return build_alert_sections(
        provider_name=alert_record.provider.display_name,
        provider_notes=extract_provider_notes(alert_record.provider),
        provider_tags=extract_provider_tags(alert_record.provider),
        account_id=extract_account_id_from_message(
            alert_record.alert_message
        ),
        current_cost=alert_record.current_cost,
        previous_cost=alert_record.previous_cost,
        increase_cost=alert_record.increase_cost,
        increase_percent=alert_record.increase_percent,
        current_balance=current_balance,
        current_days_remaining=current_days_remaining,
        currency=alert_record.currency,
        alert_rule=alert_rule,
        alert_type=alert_type,
        cost_threshold_triggered=cost_threshold_triggered,
        balance_threshold_triggered=balance_threshold_triggered,
        days_remaining_threshold_triggered=days_remaining_threshold_triggered,
        language=language,
        resource_cost_items=resource_cost_items,
        cost_period=cost_period,
        recharge_approval_notice=recharge_approval_notice,
    )


def build_alert_message_from_record(
    alert_record,
    language: str,
    resource_cost_items: Optional[list] = None,
) -> str:
    if not resource_cost_items:
        resource_cost_items = getattr(
            alert_record, "resource_cost_details", None
        ) or []
    alert_rule = alert_record.alert_rule or SimpleNamespace(
        cost_threshold=None,
        growth_threshold=None,
        growth_amount_threshold=None,
        balance_threshold=alert_record.balance_threshold,
        days_remaining_threshold=alert_record.days_remaining_threshold,
    )
    current_balance = getattr(alert_record, "current_balance", None)
    alert_type = getattr(alert_record, "alert_type", None)
    balance_threshold = getattr(alert_record, "balance_threshold", None)
    current_days_remaining = getattr(alert_record, "current_days_remaining", None)
    days_remaining_threshold = getattr(
        alert_record,
        "days_remaining_threshold",
        None,
    )
    current_cost = getattr(alert_record, "current_cost", 0)
    recharge_approval_notice = extract_recharge_approval_notice(
        getattr(alert_record, "alert_message", "")
    )

    balance_threshold_triggered = (
        alert_type == "balance"
        or (
        current_balance is not None
        and balance_threshold is not None
        and current_balance < balance_threshold
        )
    )
    cost_threshold = getattr(alert_rule, "cost_threshold", None)
    cost_threshold_triggered = (
        alert_type == "cost"
        or (
        not balance_threshold_triggered
        and current_days_remaining is None
        and cost_threshold is not None
        and current_cost > cost_threshold
        )
    )
    days_remaining_threshold_triggered = (
        alert_type == "days_remaining"
        or (
        not balance_threshold_triggered
        and current_days_remaining is not None
        and days_remaining_threshold is not None
        and current_days_remaining < days_remaining_threshold
        )
    )

    # Get cost_period from record (defaults to "today" if not set)
    cost_period = getattr(alert_record, "cost_period", None) or "today"

    return build_alert_message(
        provider_name=alert_record.provider.display_name,
        provider_notes=extract_provider_notes(alert_record.provider),
        provider_tags=extract_provider_tags(alert_record.provider),
        account_id=extract_account_id_from_message(alert_record.alert_message),
        current_cost=alert_record.current_cost,
        previous_cost=alert_record.previous_cost,
        increase_cost=alert_record.increase_cost,
        increase_percent=alert_record.increase_percent,
        current_balance=current_balance,
        current_days_remaining=current_days_remaining,
        currency=alert_record.currency,
        alert_rule=alert_rule,
        alert_type=alert_type,
        cost_threshold_triggered=cost_threshold_triggered,
        balance_threshold_triggered=balance_threshold_triggered,
        days_remaining_threshold_triggered=days_remaining_threshold_triggered,
        language=language,
        resource_cost_items=resource_cost_items,
        cost_period=cost_period,
        recharge_approval_notice=recharge_approval_notice,
    )
