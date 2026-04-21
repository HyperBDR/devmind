"""Helpers for generating localized cloud billing alert messages."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Optional

from django.utils import translation
from django.utils.translation import gettext as _

from .constants import DEFAULT_LANGUAGE


def is_chinese_language(language: str) -> bool:
    return str(language or "").lower().startswith("zh")


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
) -> str:
    raw_language = str(language or DEFAULT_LANGUAGE).strip()
    normalized_language = (
        "zh_Hans" if raw_language.lower().startswith("zh") else raw_language.lower()
    )

    with translation.override(normalized_language):
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
            lines.append(
                format_alert_line(
                    localized_text(
                        normalized_language,
                        "Current total cost",
                        "当前累计成本",
                    ),
                    f"{current_cost:.2f} {currency}",
                    language=normalized_language,
                )
            )
            lines.append(
                format_alert_line(
                    localized_text(
                        normalized_language, "Alert threshold", "告警阈值"
                    ),
                    f"{alert_rule.cost_threshold:.2f} {currency}",
                    language=normalized_language,
                )
            )
            lines.append(
                format_alert_line(
                    localized_text(
                        normalized_language,
                        "Previous hour cost",
                        "上一小时成本",
                    ),
                    f"{previous_cost:.2f} {currency}",
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
                _("Alert type"),
                _("Cost growth alert"),
                language=normalized_language,
            ),
        )
        lines.append(
            format_alert_line(
                _("Current total cost"),
                f"{current_cost:.2f} {currency}",
                language=normalized_language,
            )
        )
        lines.append(
            format_alert_line(
                _("Previous hour cost"),
                f"{previous_cost:.2f} {currency}",
                language=normalized_language,
            )
        )
        lines.append(
            format_alert_line(
                _("Increase amount"),
                f"{increase_cost:.2f} {currency}",
                language=normalized_language,
            )
        )
        lines.append(
            format_alert_line(
                _("Growth rate"),
                f"{increase_percent:.2f}%",
                language=normalized_language,
            )
        )
        if alert_rule.growth_threshold is not None:
            lines.append(
                format_alert_line(
                    _("Percentage threshold"),
                    f"{alert_rule.growth_threshold:.2f}%",
                    language=normalized_language,
                )
            )
        if alert_rule.growth_amount_threshold is not None:
            lines.append(
                format_alert_line(
                    _("Amount threshold"),
                    f"{alert_rule.growth_amount_threshold:.2f} {currency}",
                    language=normalized_language,
                )
            )
        lines.append(
            format_alert_line(
                _("Alert description"),
                _("Billing growth exceeds the configured threshold"),
                language=normalized_language,
            )
        )
        return "\n".join(lines)


def build_alert_message_from_record(alert_record, language: str) -> str:
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
    )
