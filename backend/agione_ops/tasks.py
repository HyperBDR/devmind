"""UUID-only synthetic/native synchronization, never a periodic seed."""

from celery import shared_task
from celery.exceptions import Retry
from django.conf import settings

from agione_ops.sync import execute_sync, mark_dispatch_failed


_RETRYABLE_SCHEDULE_STATUSES = frozenset({
    "failed", "interrupted", "dispatch_failed",
})
_RETRYABLE_SCHEDULE_ERRORS = frozenset({
    "NATIVE_SYNC_DEADLINE", "SYNC_FAILED", "LEASE_LOST",
    "SOURCE_PAGE_LIMIT", "SOURCE_TIMEOUT", "SOURCE_RATE_LIMITED",
    "SOURCE_UNAVAILABLE", "SOURCE_UNREACHABLE", "SOURCE_REJECTED",
    "SOURCE_CHANGED_DURING_PAGING", "SOURCE_INCOMPLETE_PAGING",
    "DISPATCH_FAILED", "LEASE_EXPIRED",
})
_SCHEDULE_RETRY_DELAYS = {1: 5, 2: 15}


def _sync_hard_time_limit():
    """Bound a stuck worker even when an upstream call never returns."""
    seconds = getattr(settings, "AGIONE_OPS_NATIVE_MAX_SECONDS", 600)
    if type(seconds) is not int or not 30 <= seconds <= 1800:
        seconds = 600
    return seconds + 90


def _retryable_schedule_run(run):
    return (
        run is not None
        and run.status in _RETRYABLE_SCHEDULE_STATUSES
        and (
            not run.error_code
            or run.error_code in _RETRYABLE_SCHEDULE_ERRORS
        )
    )


def _webhook_payload(provider_type, text):
    """Render text for the notifier's supported webhook providers."""
    if provider_type == "feishu":
        from urllib.parse import urlsplit

        from django.core.exceptions import ValidationError
        from django.core.validators import URLValidator

        lines = text.splitlines()
        title = lines.pop(0) if lines else "AGIOne 运营通知"
        color = "green" if "已恢复" in title or "恢复提醒" in title else (
            "orange" if "待确认" in title else (
                "red" if "异常" in title else "blue"
            )
        )
        body = []
        url = ""
        for line in lines:
            if line.startswith("查看全部线索 → "):
                candidate = line.removeprefix("查看全部线索 → ").strip()
                try:
                    URLValidator(schemes=["http", "https"])(candidate)
                    parts = urlsplit(candidate)
                    port = parts.port
                    valid = (
                        parts.hostname and not parts.username
                        and not parts.password and "\\" not in candidate
                        and (port is None or port > 0)
                    )
                except (ValidationError, ValueError):
                    valid = False
                if valid:
                    url = candidate
                    continue
            body.append(line)
        content = "\n".join(body).strip()
        elements = [{"tag": "div", "text": {
            "tag": "plain_text", "content": content or title,
        }}]
        if url:
            elements.extend([
                {"tag": "hr"},
                {"tag": "action", "actions": [{
                    "tag": "button", "text": {
                        "tag": "plain_text", "content": "查看经营看板 →",
                    }, "type": "primary", "url": url,
                }]},
            ])
        return {"msg_type": "interactive", "card": {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": title},
                       "template": color},
            "elements": elements,
        }}
    if provider_type in {"wechat", "wecom"}:
        return {"msgtype": "markdown", "markdown": {"content": text}}
    return {"text": text}


@shared_task(name="agione_ops.tasks.deliver_notification", acks_late=True)
def deliver_notification(delivery_id):
    """Attempt one durable delivery without exposing webhook credentials."""
    from datetime import timedelta

    from django.db import transaction
    from django.db.models import Q
    from django.utils import timezone

    from agentcore_notifier.adapters.django.models import NotificationChannel
    from agentcore_notifier.adapters.django.tasks.send import (
        NOTIFICATION_TYPE_WEBHOOK,
        send_notification,
    )
    from agione_ops.models import NotificationDelivery

    with transaction.atomic():
        delivery = NotificationDelivery.objects.select_for_update().select_related(
            "rules", "rules__connection",
        ).get(pk=delivery_id)
        if delivery.status in {"sent", "failed", "silenced"}:
            return {"status": delivery.status}
        if (delivery.status == "sending" and delivery.next_retry_at
                and delivery.next_retry_at > timezone.now()):
            return {"status": "sending"}
        if delivery.attempts >= 3:
            delivery.status = "failed"
            delivery.save(update_fields=["status"])
            return {"status": "failed"}
        config = delivery.rules.config
        channel = NotificationChannel.objects.filter(
            uuid=config.get("channel_id"),
            is_active=True,
            channel_type=NotificationChannel.TYPE_WEBHOOK,
        ).filter(
            Q(user__isnull=True) | Q(user=delivery.rules.user),
        ).first()
        if (delivery.rules.connection.removed_at is not None
                or not config.get("enabled") or channel is None):
            delivery.status = "silenced"
            delivery.error_message = "通知规则已停用或渠道不可用。"
            delivery.save(update_fields=["status", "error_message"])
            return {"status": "silenced"}
        delivery.status = "sending"
        delivery.attempts += 1
        delivery.next_retry_at = timezone.now() + timedelta(minutes=15)
        delivery.save(update_fields=[
            "status", "attempts", "next_retry_at",
        ])

    provider_type = (
        channel.config.get("provider_type")
        or channel.config.get("provider")
        or ""
    )
    try:
        result = send_notification.run(
            notification_type=NOTIFICATION_TYPE_WEBHOOK,
            source_app="agione_ops",
            source_type=delivery.kind,
            source_id=str(delivery.pk),
            user_id=delivery.rules.user_id,
            channel_uuid=str(channel.uuid),
            params={
                "payload": _webhook_payload(
                    provider_type,
                    delivery.payload.get("text", ""),
                ),
                "provider_type": provider_type,
            },
        )
    except Exception as error:
        result = {"success": False, "error": str(error)}

    delivery.refresh_from_db()
    if result.get("success"):
        delivery.status = "sent"
        delivery.sent_at = timezone.now()
        delivery.error_message = ""
        delivery.response = result.get("response")
        delivery.save(update_fields=[
            "status", "sent_at", "error_message", "response",
        ])
        return {"status": "sent"}
    if result.get("skipped") or result.get("status") == "skipped":
        delivery.status = "silenced"
        delivery.error_message = str(result.get("error") or "已被渠道静默。")[:500]
        delivery.save(update_fields=["status", "error_message"])
        return {"status": "silenced"}
    delivery.error_message = str(
        result.get("error") or "通知服务返回发送失败。",
    )[:500]
    delivery.response = result.get("response")
    if delivery.attempts >= 3:
        delivery.status = "failed"
        delivery.next_retry_at = None
    else:
        delivery.status = "retrying"
        delays = (5, 15)
        delivery.next_retry_at = timezone.now() + timedelta(
            minutes=delays[delivery.attempts - 1],
        )
    delivery.save(update_fields=[
        "status", "error_message", "response", "next_retry_at",
    ])
    return {"status": delivery.status}


@shared_task(name="agione_ops.tasks.retry_notification_deliveries")
def retry_notification_deliveries():
    """Requeue due attempts and recover abandoned sending leases."""
    from django.db.models import Q
    from django.utils import timezone

    from agione_ops.models import NotificationDelivery

    now = timezone.now()
    due = NotificationDelivery.objects.filter(attempts__lt=3).filter(
        Q(status="pending")
        | Q(status="retrying", next_retry_at__lte=now)
        | Q(status="sending", next_retry_at__lte=now)
    ).order_by("created_at").values_list("pk", flat=True)[:100]
    ids = list(due)
    for delivery_id in ids:
        deliver_notification.delay(delivery_id)
    return len(ids)


@shared_task(
    bind=True,
    name="agione_ops.tasks.run_sync",
    acks_late=True,
    max_retries=2,
    time_limit=_sync_hard_time_limit(),
    soft_time_limit=_sync_hard_time_limit() - 30,
)
def run_sync(self, run_id):
    """Execute one domain run and retry only its bounded temporary outcome."""

    result = execute_sync(run_id)
    if result.get("status") == "retrying" and "retryAfter" in result:
        try:
            raise self.retry(countdown=result["retryAfter"])
        except Retry:
            raise
        except Exception:
            mark_dispatch_failed(run_id)
            return {
                "status": "dispatch_failed",
                "errorCode": "DISPATCH_FAILED",
            }
    _record_auto_run_result(run_id, result)
    return result


def _record_auto_run_result(run_id, result):
    """Persist a safe terminal status for an automatic collection."""
    from agione_ops.models import NotificationRules, SyncRun

    run = SyncRun.objects.filter(pk=run_id).only(
        "connection_id",
        "initiated_by_id",
        "idempotency_key",
        "created_at",
        "status",
        "attempt",
        "error_code",
    ).first()
    if run is None or not run.idempotency_key.startswith("agione-auto-"):
        return
    status = result.get("status", "failed")
    if status not in {"succeeded", "failed", "revoked", "interrupted", "dispatch_failed"}:
        return
    if status != run.status:
        return
    displayed_status = "awaiting_inspection" if status == "succeeded" else status
    values = {
        "last_auto_status": displayed_status,
        "last_auto_error_code": str(result.get("errorCode") or "")[:64],
    }
    rules = NotificationRules.objects.filter(
        connection_id=run.connection_id,
        user_id=run.initiated_by_id,
        last_auto_started_at__lte=run.created_at,
    )
    if status == "succeeded":
        rules = rules.exclude(last_auto_status="succeeded")
    updated = rules.update(**values)
    if updated and status in {"failed", "revoked", "dispatch_failed"} and (
        run.attempt >= 3 or run.error_code not in _RETRYABLE_SCHEDULE_ERRORS
    ):
        from agione_ops.notification_delivery import notify_collection_failure

        notify_collection_failure(rules.select_related("connection").first(),
                                  "calls", run.error_code)


@shared_task(bind=True, name="agione_ops.tasks.refresh_native_finance",
             acks_late=True, max_retries=2, time_limit=1260,
             soft_time_limit=1230)
def refresh_native_finance(self, projection_id, run_id, generation=None):
    """Refresh finance independently of the published call-log snapshot."""
    from agione_ops.native_finance_refresh import execute_finance

    reason = execute_finance(
        projection_id, run_id, can_retry=self.request.retries < 2,
        checkpoint_scope=generation,
    )
    if reason:
        raise self.retry(countdown=60 if self.request.retries == 0 else 180)


@shared_task(name="agione_ops.tasks.refresh_classification_finance")
def refresh_classification_finance(operator_id):
    """Refresh affected projections after the classification response returns."""
    from agione_ops.native_finance_refresh import schedule_finance
    from agione_ops.native_sync_models import NativeFinanceProjection

    run_ids = NativeFinanceProjection.objects.filter(
        operator_id=operator_id,
    ).values_list("run_id", flat=True).distinct()
    scheduled = 0
    for run_id in run_ids.iterator():
        try:
            schedule_finance(run_id)
            scheduled += 1
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Tenant finance refresh scheduling failed"
            )
    return scheduled


@shared_task(name="agione_ops.tasks.refresh_native_accounts", acks_late=True)
def refresh_native_accounts(scope_id, run_id):
    """Classify known calling users in the background."""
    from agione_ops.native_account_refresh import execute_account_scope

    return execute_account_scope(scope_id, run_id)


@shared_task(name="agione_ops.tasks.analyze_native_snapshot", acks_late=True)
def analyze_native_snapshot(scope_id, run_id):
    """Analyze a new call snapshot with an authorized cached tenant scope."""
    from agione_ops.notification_rules import analyze_completed_snapshot

    try:
        return analyze_completed_snapshot(scope_id, run_id)
    except Exception:
        _mark_auto_inspection_failed(run_id)
        from agione_ops.models import NotificationRules, SyncRun
        from agione_ops.notification_rules import scheduled_date_from_key
        from django.utils import timezone

        run = SyncRun.objects.filter(pk=run_id).first()
        date = scheduled_date_from_key(run.idempotency_key) if run else None
        if date:
            NotificationRules.objects.filter(
                connection_id=run.connection_id, user_id=run.initiated_by_id,
                last_report_date=date,
            ).update(last_report_status="failed", last_report_updated_at=timezone.now())
        raise


def _mark_auto_inspection_failed(run_id):
    """Expose an inspection failure without advancing its checkpoint."""
    from agione_ops.models import NotificationRules, SyncRun

    run = SyncRun.objects.filter(pk=run_id).only(
        "connection_id",
        "initiated_by_id",
        "idempotency_key",
    ).first()
    if run and run.idempotency_key.startswith("agione-auto-"):
        NotificationRules.objects.filter(
            connection_id=run.connection_id,
            user_id=run.initiated_by_id,
        ).update(
            last_auto_status="inspection_failed",
            last_auto_error_code="INSPECTION_FAILED",
        )


def submit_recent_sync(connection, user, end, *, scheduled=False):
    """Submit a bounded prefetch, creating a new attempt after failure."""
    from datetime import timedelta

    from django.db.models import Q
    from django.utils import timezone

    from agione_ops.models import NotificationRules, SyncRun
    from agione_ops.notification_rules import required_collection_days
    from agione_ops.sync import recover_expired_run, submit_sync

    recover_expired_run(connection.pk)

    rule = NotificationRules.objects.filter(
        connection=connection, user=user,
    ).first()
    days = required_collection_days(rule.config) if rule else 7
    purpose = 'scheduled' if scheduled else 'prefetch'
    base_key = f'agione-{purpose}-{end.date().isoformat()}-{days}'
    prefix = base_key + '-retry-'
    runs = list(
        SyncRun.objects.filter(
            connection=connection,
            initiated_by=user,
        ).filter(
            Q(idempotency_key=base_key)
            | Q(idempotency_key__startswith=prefix),
        ).order_by('-created_at')
    )
    latest = runs[0] if runs else None
    if latest is None:
        return submit_sync(
            connection, user, end - timedelta(days=days), end,
            'Asia/Shanghai', base_key,
        )
    if latest.status in {"queued", "running", "retrying"}:
        if recover_expired_run(connection.pk, latest.pk):
            latest.refresh_from_db()
    if not _retryable_schedule_run(latest):
        return latest, False

    retry_numbers = []
    for run in runs:
        if run.idempotency_key.startswith(prefix):
            try:
                retry_numbers.append(int(run.idempotency_key[len(prefix):]))
            except ValueError:
                continue
    next_retry = max(retry_numbers, default=0) + 1
    if scheduled:
        prior_attempts = max(max(run.attempt, 1) for run in runs)
        if prior_attempts >= 3:
            return latest, False
        delay = _SCHEDULE_RETRY_DELAYS.get(next_retry)
        if delay is None:
            return latest, False
        failed_at = latest.finished_at or latest.created_at
        if timezone.now() < failed_at + timedelta(minutes=delay):
            return latest, False
    key = f'{base_key}-retry-{next_retry}'
    from django.db import transaction

    with transaction.atomic():
        next_run, created = submit_sync(
            connection, user, end - timedelta(days=days), end,
            'Asia/Shanghai', key,
        )
        if scheduled and created and next_run is not None:
            SyncRun.objects.filter(pk=next_run.pk).update(attempt=prior_attempts)
            next_run.attempt = prior_attempts
        return next_run, created


def submit_auto_sync(connection, user, end, rule):
    """Submit one bounded automatic run with a unique fixed end time."""
    from datetime import timedelta

    from agione_ops.notification_rules import required_collection_days
    from agione_ops.sync import submit_sync

    days = required_collection_days(rule.config)
    key = f"agione-auto-{end.strftime('%Y%m%dT%H%M%SZ')}-{days}"
    return submit_sync(
        connection,
        user,
        end - timedelta(days=days),
        end,
        "Asia/Shanghai",
        key,
    )


def start_initial_native_sync(connection, user):
    """Start the first authorized collection without blocking provisioning."""
    import logging
    from zoneinfo import ZoneInfo

    from django.conf import settings
    from django.utils import timezone
    from rest_framework.exceptions import APIException

    from agione_ops.models import ConnectionGrant
    from agione_ops.native_sync_models import NativePublishedSnapshot
    from agione_ops.notification_rules import required_collection_days
    from agione_ops.permissions import has_action
    from agione_ops.sync import submit_sync
    from agione_ops.models import NotificationRules
    from datetime import timedelta

    if not (getattr(settings, 'AGIONE_OPS_NATIVE_ENABLED', False)
            and connection.enabled and connection.source_kind == 'native'
            and has_action(user, 'view_business') and has_action(user, 'run_sync')
            and ConnectionGrant.objects.filter(connection=connection, user=user,
                                                can_view=True, can_sync=True).exists()
            and not NativePublishedSnapshot.objects.filter(
                version__connection=connection,
                version__run__config_version=connection.config_version,
                version__run__credential_version=connection.credential_version,
            ).exists()):
        return
    end = timezone.now().astimezone(ZoneInfo('Asia/Shanghai')).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    try:
        rule = NotificationRules.objects.filter(connection=connection, user=user).first()
        days = required_collection_days(rule.config if rule else {})
        key = (f"agione-initial-{end.date().isoformat()}-{days}-"
               f"{connection.config_version}-{connection.credential_version}")
        submit_sync(connection, user, end - timedelta(days=days), end,
                    "Asia/Shanghai", key)
    except APIException as error:
        logging.getLogger(__name__).info(
            'AGIOne initial collection skipped: %s',
            getattr(error, 'code', 'unavailable'),
        )


@shared_task(name='agione_ops.tasks.prefetch_recent_native_data')
def prefetch_recent_native_data():
    """Prefetch sources without an enabled user-defined schedule."""
    import logging
    from zoneinfo import ZoneInfo

    from django.conf import settings
    from django.utils import timezone
    from rest_framework.exceptions import APIException

    from agione_ops.models import (
        ConnectionGrant,
        NotificationRules,
        SourceConnection,
    )
    from agione_ops.permissions import has_action

    if not getattr(settings, 'AGIONE_OPS_NATIVE_ENABLED', False):
        return
    end = timezone.now().astimezone(ZoneInfo('Asia/Shanghai')).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    connections = SourceConnection.objects.filter(
        enabled=True, source_kind='native', verified_at__isnull=False,
    )
    for connection in connections.iterator():
        scheduled_user_ids = {
            row.user_id
            for row in NotificationRules.objects.filter(
                connection=connection,
            ).only("user_id", "config")
            if row.config.get("enabled")
            or row.config.get("auto_refresh_enabled")
        }
        grants = ConnectionGrant.objects.filter(
            connection=connection, can_view=True, can_sync=True,
            user__is_active=True,
        ).exclude(user_id__in=scheduled_user_ids).select_related(
            'user',
        ).order_by('user_id')
        for grant in grants:
            if not (has_action(grant.user, 'view_business') and
                    has_action(grant.user, 'run_sync')):
                continue
            try:
                submit_recent_sync(connection, grant.user, end)
            except APIException as error:
                logging.getLogger(__name__).info(
                    'AGIOne prefetch skipped: %s',
                    getattr(error, 'code', 'unavailable'),
                )
            break


@shared_task(name="agione_ops.tasks.dispatch_scheduled_rule_syncs")
def dispatch_scheduled_rule_syncs():
    """Start each enabled rule once per Shanghai calendar day."""
    import logging
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    from django.conf import settings
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.exceptions import APIException

    from agione_ops.models import ConnectionGrant, NotificationRules
    from agione_ops.permissions import has_action

    if not getattr(settings, "AGIONE_OPS_NATIVE_ENABLED", False):
        return 0
    now = timezone.now()
    local_now = now.astimezone(ZoneInfo("Asia/Shanghai"))
    end = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    dispatched = 0
    rule_ids = NotificationRules.objects.values_list("pk", flat=True)
    for rule_id in rule_ids.iterator():
        with transaction.atomic():
            rule = (
                NotificationRules.objects.select_for_update()
                .select_related("connection", "user")
                .get(pk=rule_id)
            )
            config = rule.config
            if not config.get("enabled"):
                continue
            try:
                hour, minute = map(
                    int,
                    config.get("schedule_time", "01:20").split(":"),
                )
            except (AttributeError, TypeError, ValueError):
                logging.getLogger(__name__).warning(
                    "AGIOne rule %s has an invalid schedule time.",
                    rule.pk,
                )
                continue
            if (local_now.hour, local_now.minute) < (hour, minute):
                continue
            connection = rule.connection
            user = rule.user
            authorized = (
                connection.enabled
                and connection.source_kind == "native"
                and connection.verified_at is not None
                and user.is_active
                and has_action(user, "view_business")
                and has_action(user, "run_sync")
                and ConnectionGrant.objects.filter(
                    connection=connection,
                    user=user,
                    can_view=True,
                    can_sync=True,
                ).exists()
            )
            if not authorized:
                continue
            today = local_now.date()
            if rule.last_report_date != today:
                rule.last_report_date = today
                rule.last_report_status = "idle"
                rule.last_report_attempts = 0
                rule.last_report_updated_at = None
                rule.save(update_fields=["last_report_date", "last_report_status",
                                         "last_report_attempts", "last_report_updated_at"])
            if rule.last_report_status in {"done", "no_alert"}:
                continue
            if rule.deliveries.filter(
                payload__trigger="scheduled", payload__scheduled_date=str(today),
                kind="alert",
            ).exists():
                rule.last_report_status = "done"
                rule.save(update_fields=["last_report_status"])
                continue
            try:
                _run, created = submit_recent_sync(
                    connection,
                    user,
                    end,
                    scheduled=True,
                )
            except APIException as error:
                logging.getLogger(__name__).info(
                    "AGIOne scheduled collection skipped: %s",
                    getattr(error, "code", "unavailable"),
                )
                continue
            if not created:
                if getattr(_run, "status", None) != "succeeded":
                    status = getattr(_run, "status", "")
                    if status in {"failed", "interrupted", "dispatch_failed", "revoked"}:
                        key = getattr(_run, "idempotency_key", "")
                        final = (key.endswith("-retry-2")
                                 or _run.attempt >= 3
                                 or not _retryable_schedule_run(_run))
                        rule.last_report_status = "failed" if final else "collection_retrying"
                        rule.save(update_fields=["last_report_status"])
                    continue
                if rule.last_report_attempts >= 3:
                    if rule.last_report_status != "failed":
                        rule.last_report_status = "failed"
                        rule.save(update_fields=["last_report_status"])
                    continue
                wait_until = rule.last_report_updated_at
                if wait_until and now < wait_until + timedelta(minutes=5):
                    continue
                from agione_ops.native_sync_models import NativeAccountScope

                scope = NativeAccountScope.objects.filter(
                    connection=connection, user=user, status="ready",
                ).first()
                if scope:
                    from agione_ops.native_account_refresh import scope_for

                    if not scope_for(connection, user)[1]:
                        scope = None
                if not scope:
                    rule.last_report_status = "waiting_scope"
                    rule.last_report_attempts += 1
                    rule.last_report_updated_at = now
                    rule.save(update_fields=["last_report_status", "last_report_attempts",
                                             "last_report_updated_at"])

                    def retry_scope(run_id=str(_run.pk)):
                        from agione_ops.native_account_refresh import schedule_account_scope

                        schedule_account_scope(run_id)

                    transaction.on_commit(retry_scope)
                    continue
                rule.last_report_status = "analyzing"
                rule.last_report_attempts += 1
                rule.last_report_updated_at = now
                rule.last_scheduled_at = now
                rule.save(update_fields=["last_report_status", "last_report_attempts",
                                         "last_report_updated_at", "last_scheduled_at"])
                transaction.on_commit(
                    lambda scope_id=scope.pk, run_id=str(_run.pk):
                    analyze_native_snapshot.delay(scope_id, run_id)
                )
                dispatched += 1
                continue
            rule.last_scheduled_at = now
            rule.last_report_status = "collecting"
            rule.last_report_updated_at = now
            rule.save(update_fields=["last_scheduled_at", "last_report_status",
                                     "last_report_updated_at"])
            dispatched += 1
    return dispatched


def retry_abandoned_auto_sync(run_id):
    """Retry the same automatic window at most three total attempts."""
    import re

    from django.db import transaction
    from django.db.models import Q
    from django.utils import timezone
    from rest_framework.exceptions import APIException

    from agione_ops.models import NotificationRules, SourceConnection, SyncRun
    from agione_ops.sync import submit_sync

    candidate = SyncRun.objects.filter(pk=run_id).first()
    if (candidate is None or candidate.status != "interrupted"
            or candidate.error_code != "LEASE_EXPIRED"
            or not candidate.idempotency_key.startswith("agione-auto-")):
        return False
    base = re.sub(r"-retry-\d+$", "", candidate.idempotency_key)
    with transaction.atomic():
        rules = NotificationRules.objects.select_for_update().filter(
            connection_id=candidate.connection_id,
            user_id=candidate.initiated_by_id,
        ).first()
        if not rules or not rules.config.get("auto_refresh_enabled"):
            return False
        connection = SourceConnection.objects.select_for_update().get(
            pk=candidate.connection_id,
        )
        runs = list(SyncRun.objects.filter(
            connection=connection, initiated_by_id=candidate.initiated_by_id,
        ).filter(Q(idempotency_key=base) | Q(idempotency_key__startswith=base + "-retry-"))
            .order_by("-created_at", "-pk"))
        if not runs or runs[0].pk != candidate.pk:
            return False
        prior_attempts = max(max(run.attempt, 1) for run in runs)
        if prior_attempts >= 3:
            from agione_ops.notification_delivery import notify_collection_failure

            notify_collection_failure(rules, "calls", "LEASE_EXPIRED")
            return False
        numbers = [int(match.group(1)) for run in runs
                   if (match := re.search(r"-retry-(\d+)$", run.idempotency_key))]
        key = f"{base}-retry-{max(numbers, default=0) + 1}"
        started = timezone.now()
        try:
            next_run, created = submit_sync(
                connection, candidate.initiated_by, candidate.window_start,
                candidate.window_end, candidate.timezone, key,
            )
        except APIException:
            return False
        if created:
            SyncRun.objects.filter(pk=next_run.pk).update(attempt=prior_attempts)
            NotificationRules.objects.filter(
                pk=rules.pk, last_auto_started_at__lte=candidate.created_at,
            ).update(last_auto_started_at=started, last_auto_status="queued",
                     last_auto_error_code="")
        return created


@shared_task(name="agione_ops.tasks.recover_abandoned_native_syncs")
def recover_abandoned_native_syncs():
    """Reconcile expired leases independently of each connection's schedule."""
    from datetime import timedelta

    from django.db.models import Q
    from django.utils import timezone

    from agione_ops.models import SyncRun
    from agione_ops.sync import recover_expired_run

    cutoff = timezone.now() - timedelta(minutes=5)
    runs = SyncRun.objects.filter(
        connection__source_kind="native", status__in=["queued", "running", "retrying"],
    ).filter(Q(heartbeat_at__lte=cutoff) | Q(heartbeat_at__isnull=True, created_at__lte=cutoff))
    candidates = runs.order_by("created_at").values_list("connection_id", "pk")[:200]
    recovered = sum(1 for connection_id, run_id in candidates
                    if recover_expired_run(connection_id, run_id))
    interrupted = SyncRun.objects.filter(
        connection__source_kind="native", status="interrupted",
        error_code="LEASE_EXPIRED", idempotency_key__startswith="agione-auto-",
        finished_at__gte=timezone.now() - timedelta(days=1),
    ).order_by("-finished_at").values_list("pk", flat=True)[:200]
    for run_id in interrupted:
        retry_abandoned_auto_sync(run_id)
    from agione_ops.native_finance_refresh import recover_expired_finance

    recover_expired_finance()
    return recovered


@shared_task(name="agione_ops.tasks.dispatch_auto_refresh_syncs")
def dispatch_auto_refresh_syncs():
    """Dispatch due per-user refreshes without coupling them to digests."""
    import logging
    from datetime import timedelta

    from django.conf import settings
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.exceptions import APIException

    from agione_ops.models import ConnectionGrant, NotificationRules
    from agione_ops.permissions import has_action

    if not getattr(settings, "AGIONE_OPS_NATIVE_ENABLED", False):
        return 0
    now = timezone.now().replace(second=0, microsecond=0)
    dispatched = 0
    ids = NotificationRules.objects.filter(
        config__auto_refresh_enabled=True,
    ).values_list("pk", flat=True)
    for rule_id in ids.iterator():
        from agione_ops.sync import recover_expired_run

        connection_id = NotificationRules.objects.filter(pk=rule_id).values_list(
            "connection_id", flat=True,
        ).first()
        if connection_id:
            recover_expired_run(connection_id)
        with transaction.atomic():
            rule = NotificationRules.objects.select_for_update().select_related(
                "connection",
                "user",
            ).get(pk=rule_id)
            if not rule.config.get("auto_refresh_enabled"):
                continue
            if rule.next_auto_refresh_at and rule.next_auto_refresh_at > now:
                continue
            connection = rule.connection
            user = rule.user
            authorized = (
                connection.enabled
                and connection.source_kind == "native"
                and connection.verified_at is not None
                and user.is_active
                and has_action(user, "view_business")
                and has_action(user, "run_sync")
                and ConnectionGrant.objects.filter(
                    connection=connection,
                    user=user,
                    can_view=True,
                    can_sync=True,
                ).exists()
            )
            if not authorized:
                rule.last_auto_status = "unauthorized"
                rule.last_auto_error_code = "AUTHORITY_UNAVAILABLE"
                rule.save(update_fields=[
                    "last_auto_status",
                    "last_auto_error_code",
                ])
                continue
            try:
                _run, created = submit_auto_sync(
                    connection,
                    user,
                    now,
                    rule,
                )
            except APIException as error:
                logging.getLogger(__name__).info(
                    "AGIOne automatic collection deferred: %s",
                    getattr(error, "code", "unavailable"),
                )
                continue
            if not created:
                continue
            hours = int(rule.config.get("auto_refresh_hours", 3))
            rule.last_auto_started_at = now
            rule.next_auto_refresh_at = now + timedelta(hours=hours)
            rule.last_auto_status = "queued"
            rule.last_auto_error_code = ""
            rule.save(update_fields=[
                "last_auto_started_at",
                "next_auto_refresh_at",
                "last_auto_status",
                "last_auto_error_code",
            ])
            dispatched += 1
    return dispatched


@shared_task(name='agione_ops.tasks.cleanup_native_staging')
def cleanup_native_staging():
    """Remove old terminal staging, preserving published snapshots."""
    from datetime import timedelta

    from django.conf import settings
    from django.db.models import Q
    from django.utils import timezone

    from agione_ops.native_sync_models import NativeStagedRecord

    days = getattr(settings, 'AGIONE_OPS_STAGING_RETENTION_DAYS', 14)
    if type(days) is not int or days < 7:
        days = 14
    cutoff = timezone.now() - timedelta(days=days)
    rows = NativeStagedRecord.objects.filter(
        Q(run__status='succeeded',
          run__published_version__native_snapshot__isnull=False)
        | Q(run__status__in=['failed', 'revoked', 'interrupted',
                             'dispatch_failed']),
        run__finished_at__lt=cutoff,
    )
    total = 0
    while True:
        ids = list(rows.order_by('pk').values_list('pk', flat=True)[:1000])
        if not ids:
            return total
        count, _ = NativeStagedRecord.objects.filter(pk__in=ids).delete()
        total += count


@shared_task(name='agione_ops.tasks.cleanup_native_snapshots')
def cleanup_native_snapshots():
    """Delete expired payloads by source while preserving live read leases."""
    from datetime import timedelta

    from django.conf import settings
    from django.db import connection, models, transaction
    from django.db.models import OuterRef, Q, Subquery
    from django.utils import timezone

    from agione_ops.native_sync_models import NativePublishedSnapshot

    days = getattr(settings, 'AGIONE_OPS_SNAPSHOT_RETENTION_DAYS', 90)
    manual_days = getattr(
        settings,
        "AGIONE_OPS_MANUAL_SNAPSHOT_RETENTION_DAYS",
        30,
    )
    if type(days) is not int or days < 30:
        days = 90
    if type(manual_days) is not int or manual_days < 7:
        manual_days = 30
    now = timezone.now()
    latest = NativePublishedSnapshot.objects.filter(
        version__connection_id=OuterRef('version__connection_id'),
    ).order_by('-version__published_at', '-version_id').values('version_id')[:1]
    candidates = NativePublishedSnapshot.objects.filter(
        Q(version__native_lease__expires_at__isnull=True)
        | Q(version__native_lease__expires_at__lte=now),
        version__published_at__lt=now - timedelta(days=manual_days),
    ).exclude(version_id=Subquery(latest)).order_by('version__published_at')
    ids = []
    for item in candidates.select_related("version")[:400]:
        trigger = item.version.coverage.get("trigger", "daily")
        retention = manual_days if trigger == "manual" else days
        if item.version.published_at < now - timedelta(days=retention):
            ids.append(item.version_id)
        if len(ids) >= 200:
            break
    removed = 0
    for version_id in ids:
        with transaction.atomic():
            lock_options = {}
            if connection.features.has_select_for_update_skip_locked:
                lock_options['skip_locked'] = True
            snapshot = NativePublishedSnapshot.objects.select_for_update(
                **lock_options,
            ).filter(pk=version_id).first()
            if snapshot is None or not candidates.filter(pk=version_id).exists():
                continue
            count, _ = models.QuerySet(
                model=NativePublishedSnapshot, using=connection.alias,
            ).filter(pk=version_id).delete()
            removed += count
    return removed


@shared_task(name="agione_ops.tasks.cleanup_notification_history")
def cleanup_notification_history():
    """Remove only closed notification history beyond its safe retention."""
    from datetime import timedelta

    from django.utils import timezone

    from agione_ops.models import NotificationDelivery, NotificationIssue

    cutoff = timezone.now() - timedelta(days=90)
    deliveries, _ = NotificationDelivery.objects.filter(
        created_at__lt=cutoff,
        status__in={"sent", "failed", "silenced"},
    ).delete()
    issues, _ = NotificationIssue.objects.filter(
        active=False,
        resolved_at__lt=cutoff,
    ).delete()
    return {"deliveries": deliveries, "issues": issues}
