"""Build and enqueue durable notifications from completed analyses."""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from agione_ops.models import NotificationDelivery, NotificationIssue

logger = logging.getLogger(__name__)


def _parse_time(value):
    try:
        return datetime.fromisoformat(str(value)).astimezone(
            ZoneInfo("Asia/Shanghai")
        )
    except (TypeError, ValueError):
        return None


def _display_range(current, days):
    end = _parse_time(current.get("window_end"))
    start = _parse_time(current.get("current_start"))
    if end is None:
        return "-"
    start = start or end - timedelta(days=days)
    last_day = end - timedelta(microseconds=1)
    return (
        f"{start.month} 月 {start.day} 日—"
        f"{last_day.month} 月 {last_day.day} 日"
    )


def _display_collected(value):
    parsed = _parse_time(value)
    if parsed is None:
        return "-"
    return (
        f"{parsed.month} 月 {parsed.day} 日 "
        f"{parsed.strftime('%H:%M')}，北京时间"
    )


def _display_event_range(current):
    start = _parse_time(current.get("event_start"))
    end = _parse_time(current.get("window_end"))
    if start is None or end is None or start >= end:
        return "-"
    minutes = max(1, round((end - start).total_seconds() / 60))
    if start.date() == end.date():
        period = (
            f"{start.month} 月 {start.day} 日 "
            f"{start.strftime('%H:%M')}—{end.strftime('%H:%M')}"
        )
    else:
        period = (
            f"{start.month} 月 {start.day} 日 {start.strftime('%H:%M')}—"
            f"{end.month} 月 {end.day} 日 {end.strftime('%H:%M')}"
        )
    return f"{period}（{minutes} 分钟），北京时间"


def _identity(item):
    customer_id = str(item.get("customer_id", "-"))
    customer_name = str(item.get("customer_name") or customer_id)
    if customer_name == customer_id:
        return f"租户 ID {customer_id}"
    return f"{customer_name}（ID：{customer_id}）"


def _notification_groups(findings):
    groups = [
        (
            "continuous_failure",
            "持续调用失败",
            [
                x
                for x in findings
                if "continuous_failure" in x.get("reasons", [])
            ],
        ),
        (
            "balance_failure",
            "余额不足失败",
            [
                x
                for x in findings
                if "balance_failure" in x.get("reasons", [])
                and "continuous_failure" not in x.get("reasons", [])
            ],
        ),
        (
            "decline",
            "使用下降",
            [x for x in findings if "decline" in x.get("reasons", [])],
        ),
        (
            "inactive",
            "长期无调用",
            [x for x in findings if "inactive" in x.get("reasons", [])],
        ),
    ]
    return [group for group in groups if group[2]]


def _finding_text(kind, item, rules, recovery, trigger, historical=False):
    identity = _identity(item)
    if recovery and not historical:
        return f"{identity}：该问题已恢复。"
    if historical:
        failed = int(item.get("failure_count") or 0)
        total = int(item.get("event_request_count") or failed)
        succeeded = max(0, total - failed)
        rate = float(item.get("failure_rate_percent") or 0)
        reason = (
            "余额不足"
            if "balance_failure" in item.get("reasons", [])
            else "原因待确认"
        )
        outcome = "当前已恢复" if recovery else "恢复状态待确认"
        return (
            f"{identity}：失败 {failed:,} 次，成功 {succeeded:,} 次，"
            f"失败率 {rate:g}%；原因：{reason}；{outcome}。"
        )
    if kind == "continuous_failure":
        failed = int(item.get("failure_count") or 0)
        total = int(
            item.get("event_request_count")
            or item.get("current_request_count")
            or failed
        )
        succeeded = max(0, total - failed)
        prefix = ""
        if trigger in {"manual", "automatic"}:
            minutes = int(rules.config.get("event_window_minutes", 120))
            prefix = f"最近 {minutes} 分钟内"
        text = (
            f"{identity}：{prefix}失败 {failed:,} 次，"
            f"成功 {succeeded:,} 次"
        )
        if "balance_failure" in item.get("reasons", []):
            text += "；已识别原因：余额不足"
        return text + "。"
    if kind == "balance_failure":
        failed = int(item.get("balance_failure_count") or 0)
        prefix = ""
        if trigger in {"manual", "automatic"}:
            minutes = int(rules.config.get("event_window_minutes", 120))
            prefix = f"最近 {minutes} 分钟内"
        return f"{identity}：{prefix}余额不足导致失败 {failed:,} 次。"
    if kind == "decline":
        current = int(item.get("current_request_count") or 0)
        previous = int(item.get("previous_request_count") or 0)
        percent = float(item.get("decline_percent") or 0)
        return (
            f"{identity}：本期 {current:,} 次，前期 {previous:,} 次，"
            f"下降 {percent:g}%。"
        )
    days = int(rules.config.get("inactivity_days", 7))
    return f"{identity}：连续 {days} 天无调用。"


def delivery_events(previous, current, config):
    """Return alert and resolved events for one complete analysis window."""
    if current.get("status") != "ready":
        return []
    current_findings = current.get("alerts", [])
    events = []
    if current_findings:
        events.append({"kind": "alert", "findings": current_findings})
    if config.get("send_recovery", True):
        current_issues = {
            (str(item.get("customer_id", "")), reason)
            for item in current_findings
            for reason in item.get("reasons", [])
        }
        recovered_by_customer = {}
        for item in previous.get("alerts", []):
            customer_id = str(item.get("customer_id", ""))
            reasons = [
                reason
                for reason in item.get("reasons", [])
                if (customer_id, reason) not in current_issues
            ]
            if reasons:
                recovered_by_customer[customer_id] = {
                    "customer_id": customer_id,
                    "customer_name": item.get("customer_name", customer_id),
                    "reasons": reasons,
                }
        recovered = list(recovered_by_customer.values())
        if previous.get("status") == "ready" and recovered:
            events.append({"kind": "recovery", "findings": recovered})
    return events


def _digest(value):
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _card_details(rules, event, current, trigger):
    """Persist a small, transport-neutral presentation for new alerts."""
    if event["kind"] != "alert" or event.get("historical_unconfirmed"):
        return None
    groups = []
    for kind, label, items in _notification_groups(event["findings"]):
        entries = []
        for item in items[:3]:
            details = _finding_text(kind, item, rules, False, trigger)
            identity = _identity(item) + "："
            metrics = []
            if kind == "continuous_failure":
                failed = int(item.get("failure_count") or 0)
                total = item.get("event_request_count")
                if total is None:
                    total = item.get("current_request_count")
                metrics = [{"label": "失败次数", "value": f"{failed:,} 次", "highlight": True}]
                if total is not None:
                    metrics.append({"label": "成功次数", "value": f"{max(0, int(total) - failed):,} 次"})
            elif kind == "balance_failure":
                metrics = [{"label": "余额不足失败", "value": f"{int(item.get('balance_failure_count') or 0):,} 次", "highlight": True}]
            elif kind == "decline":
                metrics = [{"label": "本期调用", "value": f"{int(item.get('current_request_count') or 0):,} 次"},
                           {"label": "前期调用", "value": f"{int(item.get('previous_request_count') or 0):,} 次"}]
            entries.append({
                "name": str(item.get("customer_name") or item.get("customer_id") or "-"),
                "id": str(item.get("customer_id") or "-"),
                "details": details.removeprefix(identity),
                "reason": "余额不足" if "balance_failure" in item.get("reasons", []) else "",
                "metrics": metrics,
            })
        groups.append({"label": label, "count": len(items), "entries": entries})
    start = _parse_time(current.get("event_start"))
    end = _parse_time(current.get("window_end"))
    event_times = None
    if trigger in {"manual", "automatic"} and start and end and start < end:
        event_times = [
            f"{value.month} 月 {value.day} 日 {value:%H:%M}"
            for value in (start, end)
        ]
    return {
        "groups": groups,
        "event_times": event_times,
        "window": (_display_event_range(current) if trigger in {"manual", "automatic"}
                   else _display_range(current, int(rules.config.get("analysis_days", 7)))),
        "window_label": "事件观察" if trigger in {"manual", "automatic"} else "统计范围",
        "collected": _display_collected(current.get("collected_at")),
        "source": rules.connection.name,
    }


def _notification_text(rules, event, current, trigger):
    findings = event["findings"]
    groups = _notification_groups(findings)
    issue_count = sum(len(items) for _, _, items in groups)
    recovery = event["kind"] in {"recovery", "recovered_history"}
    historical_unconfirmed = event.get("historical_unconfirmed", False)
    state = "已恢复" if recovery else "需要关注"
    if event["kind"] == "recovered_history":
        title = "已恢复的历史异常"
    elif historical_unconfirmed:
        title = "历史异常，恢复待确认"
    elif recovery:
        title = "恢复提醒"
    elif trigger in {"manual", "automatic"}:
        title = "实时异常提醒"
    else:
        title = "运营日报"
    lines = [f"【AGIOne {title}】发现 {issue_count} 项{state}"]
    for kind, label, items in groups:
        lines.extend(["", f"{label} · {len(items)} 位租户"])
        lines.extend(
            _finding_text(
                kind,
                item,
                rules,
                recovery,
                trigger,
                historical=(event["kind"] == "recovered_history"
                            or historical_unconfirmed),
            )
            for item in items[:3]
        )
        if len(items) > 3:
            lines.append(f"另有 {len(items) - 3} 位租户。")
    public_url = getattr(settings, "AGIONE_OPS_PUBLIC_URL", "")
    if public_url:
        lines.extend(["", f"查看全部线索 → {public_url}"])
    if event["kind"] == "recovered_history" or historical_unconfirmed:
        starts = [_parse_time(item.get("event_start")) for item in findings]
        ends = [_parse_time(item.get("event_end")) for item in findings]
        starts = [value for value in starts if value]
        ends = [value for value in ends if value]
        range_line = "异常发生：-"
        if starts and ends:
            range_line = (
                "异常发生："
                f"{min(starts).strftime('%m-%d %H:%M')}—"
                f"{max(ends).strftime('%m-%d %H:%M')}，北京时间；"
                + ("巡检时已恢复" if recovery else "恢复状态待确认")
            )
    elif trigger in {"manual", "automatic"}:
        range_line = "事件观察：" + _display_event_range(current)
    else:
        range_line = "统计范围：" + _display_range(
            current,
            int(rules.config.get("analysis_days", 7)),
        )
    lines.extend([
        "",
        range_line,
        "数据采集：" + _display_collected(current.get("collected_at")),
        f"数据源：{rules.connection.name}",
    ])
    return "\n".join(lines)


def _issue_map(findings, allowed_reasons):
    issues = {}
    for item in findings:
        customer_id = str(item.get("customer_id", ""))
        if not customer_id:
            continue
        for reason in item.get("reasons", []):
            if reason in allowed_reasons:
                issues[(customer_id, reason)] = item
    return issues


def _merged_findings(issue_items):
    merged = {}
    for (customer_id, reason), item in issue_items:
        target = merged.setdefault(
            customer_id,
            {**item, "reasons": []},
        )
        if reason not in target["reasons"]:
            target["reasons"].append(reason)
    return list(merged.values())


def _create_delivery(rules, event, current, trigger, scheduled_date):
    normalized = sorted(
        (
            str(item.get("customer_id", "")),
            tuple(sorted(item.get("reasons", []))),
        )
        for item in event["findings"]
    )
    signature_parts = {"kind": event["kind"], "findings": normalized}
    if event.get("historical_unconfirmed"):
        signature_parts["historical_unconfirmed"] = True
    signature = _digest(signature_parts)
    if trigger == "scheduled" and scheduled_date:
        event_identity = {
            "rules": rules.pk,
            "trigger": trigger,
            "scheduled_date": scheduled_date,
            "kind": event["kind"],
        }
    else:
        event_identity = {
            "rules": rules.pk,
            "trigger": trigger,
            "window_end": current.get("window_end"),
            "signature": signature,
        }
    delivery, created = NotificationDelivery.objects.get_or_create(
        event_key=_digest(event_identity),
        defaults={
            "rules": rules,
            "issue_signature": signature,
            "kind": event["kind"],
            "payload": {
                "text": _notification_text(
                    rules,
                    event,
                    current,
                    trigger,
                ),
                "finding_count": len(event["findings"]),
                "event_start": current.get("event_start"),
                "window_end": current.get("window_end"),
                "scheduled_date": scheduled_date,
                "trigger": trigger,
                "issues": normalized,
                "card_details": _card_details(rules, event, current, trigger),
            },
        },
    )
    return delivery if created else None


def enqueue_analysis_notifications(
    rules,
    previous,
    current,
    *,
    trigger="scheduled",
    scheduled_date=None,
    preserve_issue_state=False,
    dispatch=True,
):
    """Persist new events and dispatch each event at most once."""
    config = rules.config
    if (
        trigger == "historical"
        or not config.get("enabled")
        or not config.get("channel_id")
        or current.get("status") != "ready"
    ):
        return []
    urgent = {"continuous_failure", "balance_failure"}
    allowed = urgent if trigger in {"manual", "automatic"} else {
        "continuous_failure",
        "balance_failure",
        "decline",
        "inactive",
    }
    current_issues = _issue_map(current.get("alerts", []), allowed)
    if preserve_issue_state and trigger == "scheduled":
        if not current_issues:
            return []
        with transaction.atomic():
            delivery = _create_delivery(
                rules, {"kind": "alert", "findings": current.get("alerts", [])},
                current, trigger, scheduled_date,
            )
        created = [delivery] if delivery is not None else []
        if dispatch:
            dispatch_analysis_notifications(created)
        return created
    now = timezone.now()
    repeat_since = now - timedelta(hours=config.get("repeat_hours", 4))
    alert_items = []
    recovery_items = []
    with transaction.atomic():
        existing = {
            (item.customer_id, item.reason): item
            for item in NotificationIssue.objects.select_for_update().filter(
                rules=rules,
                reason__in=allowed,
            )
        }
        for key, finding in current_issues.items():
            issue = existing.get(key)
            is_due = trigger == "scheduled"
            if issue is None:
                issue, was_created = NotificationIssue.objects.get_or_create(
                    rules=rules,
                    customer_id=key[0],
                    reason=key[1],
                    defaults={
                        "finding": finding,
                        "first_seen_at": now,
                        "last_seen_at": now,
                    },
                )
                existing[key] = issue
                is_due = was_created or not issue.active
            elif not issue.active or not issue.last_alerted_at:
                is_due = True
            elif issue.last_alerted_at <= repeat_since:
                is_due = True
            issue.active = True
            issue.finding = finding
            issue.last_seen_at = now
            issue.resolved_at = None
            if is_due:
                issue.last_alerted_at = now
                alert_items.append((key, finding))
            issue.save(
                update_fields=[
                    "active",
                    "finding",
                    "last_seen_at",
                    "last_alerted_at",
                    "resolved_at",
                ]
            )
        for key, issue in existing.items():
            if not issue.active or key in current_issues:
                continue
            if issue.reason in urgent:
                evidence = current.get("recovery_evidence", {}).get(
                    issue.customer_id, {},
                )
                success = _parse_time(evidence.get("success"))
                failure = _parse_time(evidence.get("failure"))
                observed = (
                    _parse_time(issue.finding.get("event_end"))
                    or issue.first_seen_at
                )
                if (not success or success <= observed
                        or (failure and success <= failure)):
                    continue
            issue.active = False
            issue.resolved_at = now
            issue.save(update_fields=["active", "resolved_at"])
            if config.get("send_recovery", True):
                recovery_items.append((key, issue.finding))

        events = []
        if trigger == "scheduled" and current_issues:
            events.append({
                "kind": "alert",
                "findings": current.get("alerts", []),
            })
        elif alert_items:
            events.append({
                "kind": "alert",
                "findings": _merged_findings(alert_items),
            })
        if recovery_items:
            events.append({
                "kind": "recovery",
                "findings": _merged_findings(recovery_items),
            })
        historical = current.get("historical_alerts", [])
        recovered_history = [item for item in historical if item.get("recovered")]
        unconfirmed_history = [item for item in historical if not item.get("recovered")]
        if (
            trigger == "automatic"
            and config.get("send_recovered_history", True)
            and recovered_history
        ):
            events.append({
                "kind": "recovered_history",
                "findings": recovered_history,
            })
        if trigger == "automatic" and unconfirmed_history:
            for key, finding in _issue_map(
                unconfirmed_history, urgent,
            ).items():
                issue = existing.get(key)
                if issue and issue.active:
                    continue
                if issue is None:
                    issue, _ = NotificationIssue.objects.get_or_create(
                        rules=rules, customer_id=key[0], reason=key[1],
                        defaults={"first_seen_at": now, "last_seen_at": now},
                    )
                issue.active = True
                issue.finding = finding
                issue.first_seen_at = now
                issue.last_seen_at = now
                issue.last_alerted_at = now
                issue.resolved_at = None
                issue.save(update_fields=[
                    "active", "finding", "first_seen_at", "last_seen_at",
                    "last_alerted_at", "resolved_at",
                ])
            events.append({
                "kind": "alert",
                "historical_unconfirmed": True,
                "findings": unconfirmed_history,
            })
        created = [
            delivery
            for event in events
            if (
                delivery := _create_delivery(
                    rules,
                    event,
                    current,
                    trigger,
                    scheduled_date,
                )
            )
        ]

    if dispatch:
        dispatch_analysis_notifications(created)
    return created


def dispatch_analysis_notifications(deliveries):
    """Enqueue notification records after their transaction commits."""
    for delivery in deliveries:
        from agione_ops.tasks import deliver_notification

        try:
            deliver_notification.delay(delivery.pk)
        except Exception:
            logger.exception(
                "AGIOne notification dispatch failed delivery_id=%s",
                delivery.pk,
            )
