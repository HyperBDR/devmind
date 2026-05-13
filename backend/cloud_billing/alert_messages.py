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
    max_items: int = 10,
) -> list[str]:
    """Format resource cost items as a table.

    Table layout with columns: Resource, Cost, Creator.
    Plain strings (no label:value separator) for table rows,
    so notification service renders them as raw text.
    """
    if is_chinese_language(normalized_language):
        header = (
            localized_text(
                normalized_language,
                "Cost breakdown",
                "费用明细",
            )
            + "："
        )
        col_resource = "资源"
        col_cost = "花费"
        col_creator = "创建者"
    else:
        header = (
            localized_text(
                normalized_language,
                "Cost breakdown",
                "费用明细",
            )
            + ": "
        )
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
            if current_balance is not None:
                lines.append(
                    format_alert_line(
                        localized_text(
                            normalized_language,
                            "Current balance",
                            "当前余额",
                        ),
                        f"{current_balance:.2f} {currency}",
                        language=normalized_language,
                    )
                )
            if resource_cost_items:
                lines.extend(_format_resource_cost_lines(
                    resource_cost_items, currency, normalized_language,
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
                    "Increase amount",
                    "增加金额",
                ),
                f"{increase_cost:.2f} {currency}",
                language=normalized_language,
            )
        )
        lines.append(
            format_alert_line(
                localized_text(
                    normalized_language,
                    "Growth rate",
                    "增长率",
                ),
                f"{increase_percent:.2f}%",
                language=normalized_language,
            )
        )
        if alert_rule.growth_threshold is not None:
            lines.append(
                format_alert_line(
                    localized_text(
                        normalized_language,
                        "Percentage threshold",
                        "百分比阈值",
                    ),
                    f"{alert_rule.growth_threshold:.2f}%",
                    language=normalized_language,
                )
            )
        if alert_rule.growth_amount_threshold is not None:
            lines.append(
                format_alert_line(
                    localized_text(
                        normalized_language,
                        "Amount threshold",
                        "金额阈值",
                    ),
                    f"{alert_rule.growth_amount_threshold:.2f} {currency}",
                    language=normalized_language,
                )
            )
        if current_balance is not None:
            lines.append(
                format_alert_line(
                    localized_text(
                        normalized_language,
                        "Current balance",
                        "当前余额",
                    ),
                    f"{current_balance:.2f} {currency}",
                    language=normalized_language,
                )
            )
        if resource_cost_items:
            lines.extend(_format_resource_cost_lines(
                resource_cost_items, currency, normalized_language,
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
) -> dict:
    """Inner builder — all ``_()`` calls resolve under the active language."""

    effective_alert_type = str(alert_type or "").strip().lower()

    # ── Determine alert type label and trigger ──
    # NOTE: _() must be called on the raw template string BEFORE .format()
    # substitution, otherwise Python evaluates the format first and _()
    # receives an already-interpolated string that won't match any .po entry.
    if effective_alert_type == "balance" or balance_threshold_triggered:
        type_label = _("Balance Alert")
        trigger_icon = "💰"
        if current_balance is not None and alert_rule.balance_threshold:
            trigger_text = _(
                "Balance %(bal).2f %(cur)s"
                " below threshold %(thr).2f %(cur)s"
            ) % {
                "bal": current_balance,
                "thr": alert_rule.balance_threshold,
                "cur": currency,
            }
        else:
            trigger_text = type_label
    elif (
        effective_alert_type == "days_remaining"
        or days_remaining_threshold_triggered
    ):
        type_label = _("Days Remaining Alert")
        trigger_icon = "⏳"
        trigger_text = _(
            "%(days)s days remaining"
            " below threshold %(thr)s"
        ) % {
            "days": current_days_remaining,
            "thr": alert_rule.days_remaining_threshold,
        }
    elif effective_alert_type == "cost" or cost_threshold_triggered:
        type_label = _("Cost Threshold Alert")
        trigger_icon = "📊"
        trigger_text = _(
            "Total cost %(cost).2f %(cur)s"
            " exceeds threshold %(thr).2f %(cur)s"
        ) % {
            "cost": current_cost,
            "thr": alert_rule.cost_threshold,
            "cur": currency,
        }
    else:
        type_label = _("Cost Growth Alert")
        trigger_icon = "📈"
        parts = []
        if increase_percent > 0:
            parts.append(
                _("Growth %(pct).1f%%") % {"pct": increase_percent}
            )
        if alert_rule.growth_threshold is not None:
            parts.append(
                _("threshold %(thr).1f%%")
                % {"thr": alert_rule.growth_threshold}
            )
        joined = _(", ").join(parts)
        trigger_text = joined if joined else type_label

    # ── Structural labels (single source of truth) ──
    labels = {
        "provider":       _("Provider"),
        "account":        _("Account"),
        "notes":          _("Notes"),
        "tags":           _("Tags"),
        "balance":        _("Balance"),
        "cost_breakdown": _("Cost Breakdown"),
        "col_resource":   _("Resource"),
        "col_cost":       _("Cost"),
        "col_owner":      _("Owner"),
        "footer":         _("DevMind Cloud Billing · @all"),
        "sep":            _(": "),
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
    }

    # ── Key metrics ──
    if effective_alert_type in ("growth", "") and not (
        balance_threshold_triggered
        or days_remaining_threshold_triggered
    ):
        sections["metrics"] = [
            {
                "label": _("Current Total"),
                "value": f"{current_cost:.2f}",
                "highlight": False,
            },
            {
                "label": _("Previous Hour"),
                "value": f"{previous_cost:.2f}",
                "highlight": False,
            },
            {
                "label": _("Increase"),
                "value": f"{increase_cost:.2f}",
                "highlight": True,
            },
            {
                "label": _("Growth Rate"),
                "value": f"{increase_percent:.1f}%",
                "highlight": True,
            },
        ]
    elif (
        effective_alert_type == "cost" or cost_threshold_triggered
    ):
        sections["metrics"] = [
            {
                "label": _("Current Total"),
                "value": f"{current_cost:.2f}",
                "highlight": True,
            },
            {
                "label": _("Previous Hour"),
                "value": f"{previous_cost:.2f}",
                "highlight": False,
            },
        ]

    # ── Thresholds ──
    if alert_rule.growth_threshold is not None:
        sections["thresholds"].append({
            "label": _("Growth %"),
            "value": f"{alert_rule.growth_threshold:.1f}%",
        })
    if alert_rule.growth_amount_threshold is not None:
        sections["thresholds"].append({
            "label": _("Amount"),
            "value": (
                f"{alert_rule.growth_amount_threshold:.2f}"
                f" {currency}"
            ),
        })
    if alert_rule.cost_threshold is not None:
        sections["thresholds"].append({
            "label": _("Cost"),
            "value": f"{alert_rule.cost_threshold:.2f} {currency}",
        })
    if alert_rule.balance_threshold is not None:
        sections["thresholds"].append({
            "label": _("Balance"),
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
        resource_cost_items=resource_cost_items,
    )
