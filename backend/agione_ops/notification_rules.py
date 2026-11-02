"""Validation and defaults for AGIOne notification rules."""

import re
from collections import defaultdict
from datetime import timedelta
from zoneinfo import ZoneInfo

from rest_framework import serializers


_SCHEDULED_RUN_PATTERN = re.compile(
    r"^agione-scheduled-(\d{4}-\d{2}-\d{2})-\d+"
    r"(?:-retry-\d+)?$"
)
_AUTOMATIC_RUN_PATTERN = re.compile(r"^agione-(?:prefetch|auto)-")


def scheduled_date_from_key(idempotency_key):
    """Return the Shanghai schedule date encoded in a scheduled run key."""
    match = _SCHEDULED_RUN_PATTERN.fullmatch(idempotency_key or "")
    return match.group(1) if match else None


def notification_trigger_from_key(idempotency_key):
    """Classify a completed collection by its notification contract."""
    if scheduled_date_from_key(idempotency_key):
        return "scheduled"
    if _AUTOMATIC_RUN_PATTERN.match(idempotency_key or ""):
        return "automatic"
    return "manual"


def notification_trigger_for_run(idempotency_key, window_end, now):
    """Suppress event alerts for manually collected historical windows."""
    trigger = notification_trigger_from_key(idempotency_key)
    if trigger == "manual" and window_end < now - timedelta(minutes=15):
        return "historical"
    return trigger


def extend_manual_window(window, now):
    """Include same-day records when refreshing the latest complete range."""
    local_now = now.astimezone(ZoneInfo("Asia/Shanghai")).replace(
        microsecond=0,
    )
    today = local_now.replace(hour=0, minute=0, second=0)
    end = window["end_exclusive"].astimezone(
        ZoneInfo("Asia/Shanghai"),
    )
    if end != today or local_now - window["start"] > timedelta(days=31):
        return window
    return {**window, "end_exclusive": local_now}


class NotificationRulesSerializer(serializers.Serializer):
    """Persist explicit settings without accepting arbitrary fields."""

    analysis_days = serializers.IntegerField(
        min_value=1,
        max_value=15,
        default=7,
    )
    inactivity_days = serializers.IntegerField(
        min_value=1,
        max_value=31,
        default=7,
    )
    decline_percent = serializers.FloatField(
        min_value=1,
        max_value=100,
        default=40,
    )
    technical_failure_percent = serializers.FloatField(
        min_value=0.1,
        max_value=100,
        default=2,
    )
    min_technical_requests = serializers.IntegerField(min_value=1, default=20)
    schedule_time = serializers.RegexField(
        regex=r"^(?:[01]\d|2[0-3]):[0-5]\d$",
        default="01:20",
    )
    enabled = serializers.BooleanField(default=False)
    auto_refresh_enabled = serializers.BooleanField(default=False)
    auto_refresh_hours = serializers.ChoiceField(
        choices=(2, 3, 4),
        default=3,
    )
    finance_refresh_hours = serializers.ChoiceField(
        choices=(6, 12, 24),
        default=12,
    )
    tenant_refresh_hours = serializers.ChoiceField(
        choices=(6, 12, 24),
        default=12,
    )
    channel_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        default=None,
    )
    continuous_failure = serializers.BooleanField(default=True)
    balance_failure = serializers.BooleanField(default=True)
    decline = serializers.BooleanField(default=False)
    inactive = serializers.BooleanField(default=False)
    min_failure_count = serializers.IntegerField(min_value=1, default=6)
    event_window_minutes = serializers.IntegerField(
        min_value=5,
        max_value=1440,
        default=120,
    )
    failure_rate_percent = serializers.FloatField(
        min_value=1,
        max_value=100,
        default=80,
    )
    min_balance_failure_count = serializers.IntegerField(
        min_value=1,
        default=1,
    )
    repeat_hours = serializers.IntegerField(
        min_value=1,
        max_value=168,
        default=4,
    )
    send_recovery = serializers.BooleanField(default=True)
    send_recovered_history = serializers.BooleanField(default=True)

    def validate(self, attrs):
        if attrs.get("enabled") and not attrs.get("channel_id"):
            raise serializers.ValidationError("请选择通知渠道。")
        if attrs.get("channel_id"):
            attrs["channel_id"] = str(attrs["channel_id"])
        return attrs


def required_collection_days(config):
    """Return the complete source window required by enabled rules."""
    days = config.get("analysis_days", 7)
    required = days * 2 if config.get("decline", False) else days
    if config.get("inactive", False):
        required = max(required, config.get("inactivity_days", days))
    return required


def collect_failure_alerts(rows, config):
    """Group known failures by tenant without treating unknown as success."""
    groups = defaultdict(list)
    for row in rows:
        if row.get("customer_id"):
            groups[row["customer_id"]].append(row)
    alerts = []
    minimum = config.get("min_failure_count", 6)
    failure_rate_threshold = config.get("failure_rate_percent", 80)
    balance_minimum = config.get("min_balance_failure_count", 1)
    for customer_id, items in groups.items():
        failures = [row for row in items if row.get("result") == "FAILURE"]
        balance = sum(row.get("failureKey") == "source:3" for row in failures)
        failure_rate = len(failures) / len(items) * 100
        blocked = (
            config.get("continuous_failure", True)
            and len(failures) >= minimum
            and failure_rate >= failure_rate_threshold
        )
        low_balance = (
            config.get("balance_failure", True)
            and balance >= balance_minimum
        )
        if blocked or low_balance:
            alerts.append(
                {
                    "customer_id": customer_id,
                    "failure_count": len(failures),
                    "request_count": len(items),
                    "failure_rate_percent": round(failure_rate, 2),
                    "balance_failure_count": balance,
                    "blocked": blocked,
                    "balance_failure": low_balance,
                }
            )
    return sorted(
        alerts,
        key=lambda item: (-item["failure_count"], item["customer_id"]),
    )


def collect_interval_failure_events(
    rows,
    config,
    inspection_start,
    inspection_end,
    customer_names=None,
):
    """Find qualifying failure windows anywhere in an inspection interval."""
    from agione_ops.native_analytics import parse_time

    customer_names = customer_names or {}
    window = timedelta(
        minutes=config.get("event_window_minutes", 120),
    )
    groups = defaultdict(list)
    for row in rows:
        occurred_at = parse_time(row["occurred_at"])
        if inspection_start - window <= occurred_at < inspection_end:
            groups[str(row.get("customer_id", ""))].append(
                (occurred_at, row)
            )
    events = []
    for customer_id, items in groups.items():
        if not customer_id:
            continue
        items.sort(key=lambda item: item[0])
        anchors = sorted(
            {
                occurred_at
                for occurred_at, _row in items
                if inspection_start <= occurred_at < inspection_end
            }
            | {inspection_end}
        )
        matches = []
        for anchor in anchors:
            observed = [
                row
                for occurred_at, row in items
                if anchor - window < occurred_at <= anchor
            ]
            alert = next(
                iter(collect_failure_alerts(observed, config)),
                None,
            )
            if alert:
                matches.append((anchor, alert))
        if not matches:
            continue
        segments = []
        for anchor, alert in matches:
            if not segments or anchor - segments[-1]["end"] > window:
                segments.append({
                    "start": max(inspection_start, anchor - window),
                    "end": anchor,
                    "alert": alert,
                })
            else:
                segments[-1]["end"] = anchor
                if alert["failure_count"] >= segments[-1]["alert"][
                    "failure_count"
                ]:
                    segments[-1]["alert"] = alert
        for segment in segments:
            alert = segment["alert"]
            reasons = []
            if alert["blocked"]:
                reasons.append("continuous_failure")
            if alert["balance_failure"]:
                reasons.append("balance_failure")
            events.append({
                "customer_id": customer_id,
                "customer_name": customer_names.get(
                    customer_id,
                    customer_id,
                ),
                "reasons": reasons,
                "failure_count": alert["failure_count"],
                "event_request_count": alert["request_count"],
                "failure_rate_percent": alert["failure_rate_percent"],
                "balance_failure_count": alert[
                    "balance_failure_count"
                ],
                "event_start": segment["start"].isoformat(),
                "event_end": segment["end"].isoformat(),
                "recovered": segment["end"] < inspection_end,
            })
    return events


def analyze_rows(
    rows,
    customer_ids,
    config,
    end,
    customer_names=None,
    event_only=False,
):
    """Analyze four rule types over complete current and prior windows."""
    from agione_ops.native_analytics import parse_time

    customer_names = customer_names or {}
    days = config.get("analysis_days", 7)
    current_start = end - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)
    inactivity_start = end - timedelta(
        days=config.get("inactivity_days", days),
    )
    event_start = end - timedelta(
        minutes=config.get("event_window_minutes", 60),
    )
    current = [
        row
        for row in rows
        if current_start <= parse_time(row["occurred_at"]) < end
    ]
    previous = [
        row
        for row in rows
        if previous_start <= parse_time(row["occurred_at"]) < current_start
    ]
    current_counts = defaultdict(int)
    previous_counts = defaultdict(int)
    recent = set()
    for row in current:
        current_counts[row["customer_id"]] += 1
    for row in previous:
        previous_counts[row["customer_id"]] += 1
    for row in rows:
        if inactivity_start <= parse_time(row["occurred_at"]) < end:
            recent.add(row["customer_id"])

    findings = {}

    def finding(customer_id):
        return findings.setdefault(
            customer_id,
            {
                "customer_id": customer_id,
                "customer_name": customer_names.get(customer_id, customer_id),
                "reasons": [],
                "current_request_count": current_counts[customer_id],
                "previous_request_count": previous_counts[customer_id],
            },
        )

    failure_rows = [
        row
        for row in rows
        if event_start <= parse_time(row["occurred_at"]) < end
    ] if event_only else current
    for item in collect_failure_alerts(failure_rows, config):
        target = finding(item["customer_id"])
        if item["blocked"]:
            target["reasons"].append("continuous_failure")
        if item["balance_failure"]:
            target["reasons"].append("balance_failure")
        target["failure_count"] = item["failure_count"]
        target["event_request_count"] = item["request_count"]
        target["failure_rate_percent"] = item["failure_rate_percent"]
        target["balance_failure_count"] = item["balance_failure_count"]

    if config.get("decline", False):
        threshold = config.get("decline_percent", 40)
        for customer_id, prior in previous_counts.items():
            if prior == 0:
                continue
            drop = max(
                0.0,
                (prior - current_counts[customer_id]) / prior * 100,
            )
            if drop >= threshold:
                target = finding(customer_id)
                target["reasons"].append("decline")
                target["decline_percent"] = round(drop, 2)

    if config.get("inactive", False):
        for customer_id in customer_ids - recent:
            finding(customer_id)["reasons"].append("inactive")

    return {
        "current_start": current_start.isoformat(),
        "event_start": event_start.isoformat(),
        "previous_start": previous_start.isoformat(),
        "window_end": end.isoformat(),
        "current_request_count": len(current),
        "previous_request_count": len(previous),
        "alerts": sorted(
            findings.values(),
            key=lambda item: item["customer_id"],
        ),
    }


def analyze_completed_snapshot(scope_id, run_id):
    """Compute findings only after a complete, authorized classification."""
    from django.db import transaction
    from django.utils import timezone

    from agione_ops.models import NotificationRules, SyncRun
    from agione_ops.native_account_refresh import scope_for
    from agione_ops.native_account_scope import (
        external_rows,
        tenant_classification,
    )
    from agione_ops.native_sync import authorize_native_run, validate_snapshot_data
    from agione_ops.native_sync_models import NativeAccountScope
    from agione_ops.tenant_directory import overrides_for

    scope = NativeAccountScope.objects.select_related(
        "connection",
        "user",
        "run__published_version__native_snapshot",
    ).get(pk=scope_id, status="ready")
    if str(scope.run_id) == str(run_id):
        run = scope.run
    else:
        run = SyncRun.objects.select_related(
            "published_version__native_snapshot",
        ).get(pk=run_id, connection=scope.connection, initiated_by=scope.user,
              status="succeeded")
        if not scheduled_date_from_key(run.idempotency_key):
            raise ValueError("Only scheduled reports can reuse an account scope.")
    authorize_native_run(run, scope.connection)
    config = NotificationRules.objects.filter(
        connection=scope.connection,
        user=scope.user,
    ).first()
    if not config:
        return None
    trigger = notification_trigger_for_run(
        run.idempotency_key,
        run.window_end,
        timezone.now(),
    )
    types, valid = scope_for(scope.connection, scope.user)
    if not valid:
        return None
    snapshot = run.published_version.native_snapshot
    validate_snapshot_data(snapshot.data, snapshot.content_digest)
    overrides = overrides_for(scope.connection, scope.user)
    end = run.window_end
    inspection_start = None
    if trigger == "automatic":
        inspection_start = config.last_inspection_at or (
            end - timedelta(
                hours=config.config.get("auto_refresh_hours", 3),
            )
        )
        start = inspection_start - timedelta(
            minutes=config.config.get("event_window_minutes", 120),
        )
    elif trigger in {"manual", "historical"}:
        start = end - timedelta(
            minutes=config.config.get("event_window_minutes", 120),
        )
    else:
        days = required_collection_days(config.config)
        start = end - timedelta(days=days)
    if run.window_start > start:
        result = {
            "status": "insufficient_data",
            "required_start": start.isoformat(),
            "available_start": run.window_start.isoformat(),
            "window_end": end.isoformat(),
            "alerts": [],
            "trigger": trigger,
        }
    else:
        rows = external_rows(snapshot.data["rows"], types, overrides)
        customers = snapshot.data["customers"]
        customer_ids = {
            str(customer_id)
            for customer_id in customers
            if tenant_classification(
                customer_id,
                types,
                overrides,
            )[0]
            != "internal"
        }
        customer_names = {
            str(customer_id): str(
                details.get("name")
                or details.get("organizationName")
                or customer_id
            )
            for customer_id, details in customers.items()
            if isinstance(details, dict)
        }
        analysis = analyze_rows(
            rows,
            customer_ids,
            config.config,
            end,
            customer_names=customer_names,
            event_only=trigger in {"manual", "historical", "automatic"},
        )
        result = {
            "status": "ready",
            "trigger": trigger,
            **analysis,
            "collected_at": snapshot.data.get("metadata", {}).get(
                "collectedAt"
            ),
        }
        if trigger == "automatic":
            interval_events = collect_interval_failure_events(
                rows,
                config.config,
                inspection_start,
                end,
                customer_names,
            )
            result["inspection_start"] = inspection_start.isoformat()
            result["inspection_end"] = end.isoformat()
            result["historical_alerts"] = [
                item for item in interval_events if item["recovered"]
            ]
    with transaction.atomic():
        locked = NotificationRules.objects.select_for_update().get(
            pk=config.pk,
        )
        prior = locked.last_analysis or {}
        older = prior.get("window_end", "") > end.isoformat()
        if older and trigger != "scheduled":
            return prior
        if not older:
            locked.last_analysis = result
            update_fields = ["last_analysis"]
            if trigger == "automatic" and result["status"] == "ready":
                locked.last_inspection_at = end
                locked.last_auto_success_at = timezone.now()
                locked.last_auto_status = "succeeded"
                locked.last_auto_error_code = ""
                update_fields.extend([
                    "last_inspection_at",
                    "last_auto_success_at",
                    "last_auto_status",
                    "last_auto_error_code",
                ])
            locked.save(update_fields=update_fields)
    from agione_ops.notification_delivery import (
        enqueue_analysis_notifications,
    )

    created = enqueue_analysis_notifications(
        config,
        prior,
        result,
        trigger=trigger,
        scheduled_date=scheduled_date_from_key(
            run.idempotency_key,
        ),
        preserve_issue_state=older and trigger == "scheduled",
    )
    if trigger == "scheduled":
        report_date = scheduled_date_from_key(run.idempotency_key)
        delivered_or_queued = bool(created) or config.deliveries.filter(
            payload__trigger="scheduled", payload__scheduled_date=report_date,
            kind="alert",
        ).exists()
        NotificationRules.objects.filter(
            pk=config.pk, last_report_date=report_date,
        ).update(
            last_report_status=("done" if delivered_or_queued else "no_alert")
            if result.get("status") == "ready" else "failed",
            last_report_updated_at=timezone.now(),
        )
    return result
