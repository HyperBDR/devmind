"""Build daily cost report messages from dashboard data.

Consumes the same dict produced by build_dashboard_overview() and
renders it into plain-text / markdown suitable for email, Feishu,
and WeChat delivery.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _fmt_amount(
    value: float,
    currency: str = "CNY",
    is_zh: bool = True,
) -> str:
    if abs(value) >= 1_000_000:
        unit = "万" if is_zh else "M"
        divisor = 10_000 if is_zh else 1_000_000
        return f"{value / divisor:.1f}{unit} {currency}"
    return f"{value:,.2f} {currency}"


def _risk_icon(risk: str) -> str:
    return {
        "high": "[!]",
        "medium": "[~]",
        "low": "",
    }.get(risk, "")


def build_daily_report(
    overview: Dict[str, Any],
    report_date: str,
    language: str = "zh",
) -> str:
    """Build a plain-text daily cost report.

    Args:
        overview: Output of build_dashboard_overview()
        report_date: YYYY-MM-DD string for the report header
        language: "zh" or "en"

    Returns:
        Multi-line report string
    """
    is_zh = str(language or "").lower().startswith("zh")
    lines: List[str] = []

    # ── Header ──
    if is_zh:
        lines.append(f"云平台费用日报 — {report_date}")
        lines.append("=" * 44)
    else:
        lines.append(f"Cloud Cost Daily Report — {report_date}")
        lines.append("=" * 44)

    # ── Monthly summary ──
    summary = overview.get("summary", {})
    if is_zh:
        lines.append("")
        lines.append("本月概览")
        lines.append("-" * 44)
        lines.append(
            f"  累计消费    {_fmt_amount(summary.get('current_consumed', 0), is_zh=True)}"
        )
        lines.append(
            f"  日均消费    {_fmt_amount(summary.get('daily_average', 0), is_zh=True)}"
        )
        lines.append(
            f"  峰值消费    {_fmt_amount(summary.get('peak_cost', 0), is_zh=True)}"
            f"  ({summary.get('peak_date', '-')})"
        )
        lines.append(
            f"  预估月费    {_fmt_amount(summary.get('estimated_total', 0), is_zh=True)}"
        )
        lines.append(
            f"  统计天数    {summary.get('collected_days', 0)} 天"
        )
    else:
        lines.append("")
        lines.append("Monthly Summary")
        lines.append("-" * 44)
        lines.append(
            f"  Consumed      {_fmt_amount(summary.get('current_consumed', 0), is_zh=False)}"
        )
        lines.append(
            f"  Daily Avg     {_fmt_amount(summary.get('daily_average', 0), is_zh=False)}"
        )
        lines.append(
            f"  Peak          {_fmt_amount(summary.get('peak_cost', 0), is_zh=False)}"
            f"  ({summary.get('peak_date', '-')})"
        )
        lines.append(
            f"  Estimated     {_fmt_amount(summary.get('estimated_total', 0), is_zh=False)}"
        )

    # ── Week trend (last 7 days) ──
    week = summary.get("trend_ranges", {}).get("week", [])
    if week:
        lines.append("")
        if is_zh:
            lines.append("近 7 天趋势")
        else:
            lines.append("7-Day Trend")
        lines.append("-" * 44)
        for pt in week[-7:]:
            date = pt.get("date", "?")
            total = pt.get("total", 0)
            bar = _mini_bar(total, summary.get("daily_average", 1))
            lines.append(f"  {date}  {_fmt_amount(total, is_zh=is_zh):>18s}  {bar}")

    # ── Accounts ranking ──
    accounts = overview.get("accounts", [])
    if accounts:
        sorted_accounts = sorted(
            accounts, key=lambda a: a.get("cost", 0), reverse=True
        )
        lines.append("")
        if is_zh:
            lines.append("账号消费排名")
        else:
            lines.append("Account Ranking")
        lines.append("-" * 44)
        for i, acc in enumerate(sorted_accounts, 1):
            name = acc.get("name", "?")
            cost = acc.get("cost", 0)
            currency = acc.get("cost_currency", "CNY")
            risk = acc.get("risk", "")
            days = acc.get("days_remaining")
            notes = acc.get("notes", "")
            tags = acc.get("tags", [])
            pct = acc.get("percentage", 0)

            label_parts = [name]
            if notes:
                label_parts.append(f"({notes})")
            elif tags:
                label_parts.append(f"({', '.join(tags)})")
            label = " ".join(label_parts)

            risk_mark = _risk_icon(risk)
            line = (
                f"  {i}. {label:30s}"
                f"  {_fmt_amount(cost, currency, is_zh=is_zh):>20s}"
                f"  {pct:5.1f}%"
            )
            if risk_mark:
                line += f"  {risk_mark}"
            if days is not None:
                if is_zh:
                    line += f"  剩余{days}天"
                else:
                    line += f"  {days}d left"
            lines.append(line)

        # ── Per-account service breakdown (top 3 per account) ──
        lines.append("")
        if is_zh:
            lines.append("各账号 Top 3 服务")
        else:
            lines.append("Top 3 Services per Account")
        lines.append("-" * 44)
        for acc in sorted_accounts:
            name = acc.get("name", "?")
            detail = acc.get("detail", {})
            breakdown = detail.get("service_breakdown", [])
            if not breakdown:
                continue
            lines.append(f"  [{name}]")
            for svc in breakdown[:3]:
                svc_name = svc.get("name", "?")
                svc_val = svc.get("value", 0)
                svc_pct = svc.get("percentage", 0)
                cur = detail.get(
                    "service_breakdown_currency", "CNY"
                )
                lines.append(
                    f"    {svc_name:28s}"
                    f"  {_fmt_amount(svc_val, cur, is_zh=is_zh):>18s}"
                    f"  {svc_pct:5.1f}%"
                )

    # ── Financial health ──
    health = overview.get("financial_health", {})
    total_funds = health.get("total_funds", 0)
    total_days = health.get("total_days")
    bottleneck = health.get("bottleneck", "")
    alerts = health.get("recharge_alerts", [])

    needs_recharge = [
        a for a in alerts
        if a.get("days_remaining") is not None
        and a["days_remaining"] <= 14
    ]

    if needs_recharge:
        lines.append("")
        if is_zh:
            lines.append("余额预警")
        else:
            lines.append("Balance Alerts")
        lines.append("-" * 44)
        for a in needs_recharge:
            name = a.get("name", "?")
            days = a.get("days_remaining", "?")
            rec = a.get("recommended_recharge", 0)
            cur = a.get("recommendation_currency", "CNY")
            if is_zh:
                lines.append(
                    f"  {name}  剩余 {days} 天"
                    f"  建议充值 {_fmt_amount(rec, cur, is_zh=True)}"
                )
            else:
                lines.append(
                    f"  {name}  {days} days left"
                    f"  recharge {_fmt_amount(rec, cur, is_zh=False)}"
                )

    # ── Exchange rate ──
    rate = overview.get("exchange_rate")
    rate_label = overview.get("rate_source_label", "")
    if rate:
        lines.append("")
        if is_zh:
            lines.append(f"  汇率: 1 USD = {rate:.4f} CNY ({rate_label})")
        else:
            lines.append(f"  Rate: 1 USD = {rate:.4f} CNY ({rate_label})")

    lines.append("")
    lines.append("=" * 44)

    return "\n".join(lines)


def _mini_bar(value: float, reference: float) -> str:
    """Return a tiny ASCII bar proportional to value/reference."""
    if reference <= 0:
        return ""
    ratio = min(value / reference, 2.0)
    blocks = max(1, int(ratio * 8))
    return "█" * blocks
