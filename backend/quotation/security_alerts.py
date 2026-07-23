from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q, QuerySet

from accounts.access import get_effective_roles
from quotation.models import AuditEvent, SecurityAlert


@dataclass(frozen=True)
class AlertSignal:
    """Security rule result ready to be merged into an alert."""

    rule: str
    severity: str
    title: str
    reason: str
    recommendation: str
    runbook: str
    owner: str
    threshold: int
    window_minutes: int
    evidence: tuple[AuditEvent, ...]


def can_manage_security_alerts(user) -> bool:
    """Return whether a user has an explicit administrative identity."""
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False) or getattr(
        user,
        "is_superuser",
        False,
    ):
        return True
    profile = getattr(user, "profile", None)
    if str(getattr(profile, "role", "") or "").lower() == "admin":
        return True
    role_names = {
        role.name.strip().lower().replace(" ", "_")
        for role in get_effective_roles(user)
    }
    return "admin" in role_names


def _rule_context(rule: str, threshold: int, window: int) -> dict:
    base_url = settings.QUOTATION_SECURITY_ALERT_RUNBOOK_BASE_URL.rstrip("/")
    return {
        "runbook": f"{base_url}/{rule}",
        "owner": settings.QUOTATION_SECURITY_ALERT_OWNER,
        "threshold": threshold,
        "window_minutes": window,
    }


def _subject_key(event: AuditEvent) -> str:
    if event.actor_id:
        return f"user:{event.actor_id}"
    if event.actor_email:
        return f"email:{event.actor_email.lower()}"
    if event.ip_address:
        return f"ip:{event.ip_address}"
    return "system:anonymous"


def _subject_events(event: AuditEvent) -> QuerySet[AuditEvent]:
    queryset = AuditEvent.objects.all()
    if event.actor_id:
        return queryset.filter(actor_id=event.actor_id)
    if event.actor_email:
        return queryset.filter(actor_email__iexact=event.actor_email)
    if event.ip_address:
        return queryset.filter(ip_address=event.ip_address)
    return queryset.none()


def _window_evidence(
    event: AuditEvent,
    window: int,
    **filters,
) -> tuple[AuditEvent, ...]:
    start = event.created_at - timedelta(minutes=window)
    return tuple(
        _subject_events(event)
        .filter(
            created_at__gte=start,
            created_at__lte=event.created_at,
            **filters,
        )
        .order_by("created_at", "id")
    )


def _repeated_access_denials(event: AuditEvent) -> AlertSignal | None:
    denied_results = [AuditEvent.RESULT_DENIED, AuditEvent.RESULT_FAILED]
    if event.result not in denied_results or event.module == "feishu":
        return None
    threshold = settings.QUOTATION_SECURITY_DENIAL_THRESHOLD
    window = settings.QUOTATION_SECURITY_DENIAL_WINDOW_MINUTES
    evidence = _window_evidence(
        event,
        window,
        result__in=denied_results,
    )
    if len(evidence) < threshold:
        return None
    return AlertSignal(
        rule="repeated_access_denials",
        severity=SecurityAlert.SEVERITY_CRITICAL,
        title="Repeated access denials",
        reason=(
            f"{len(evidence)} requests were denied for one account within "
            f"{window} minutes. The configured threshold is {threshold}."
        ),
        recommendation=(
            "Confirm whether the requests were expected. If they were not, "
            "revoke active sessions and review the affected account."
        ),
        **_rule_context("repeated_access_denials", threshold, window),
        evidence=evidence,
    )


def _unusual_bulk_downloads(event: AuditEvent) -> AlertSignal | None:
    if not (
        event.module == "document"
        and event.action == "download"
        and event.result == AuditEvent.RESULT_SUCCEEDED
    ):
        return None
    threshold = settings.QUOTATION_SECURITY_DOWNLOAD_THRESHOLD
    window = settings.QUOTATION_SECURITY_DOWNLOAD_WINDOW_MINUTES
    evidence = _window_evidence(
        event,
        window,
        module="document",
        action="download",
        result=AuditEvent.RESULT_SUCCEEDED,
    )
    if len(evidence) < threshold:
        return None
    return AlertSignal(
        rule="unusual_bulk_downloads",
        severity=SecurityAlert.SEVERITY_HIGH,
        title="Unusual bulk downloads",
        reason=(
            f"{len(evidence)} quotation files were downloaded by one account "
            f"within {window} minutes. The threshold is {threshold} files."
        ),
        recommendation=(
            "Confirm whether the download was authorized. If it was not, "
            "revoke active sessions and review the affected quotation files."
        ),
        **_rule_context("unusual_bulk_downloads", threshold, window),
        evidence=evidence,
    )


def _repeated_feishu_failures(event: AuditEvent) -> AlertSignal | None:
    if event.module != "feishu" or event.result != AuditEvent.RESULT_FAILED:
        return None
    threshold = settings.QUOTATION_SECURITY_DENIAL_THRESHOLD
    window = settings.QUOTATION_SECURITY_DOWNLOAD_WINDOW_MINUTES
    evidence = _window_evidence(
        event,
        window,
        module="feishu",
        result=AuditEvent.RESULT_FAILED,
    )
    if len(evidence) < threshold:
        return None
    return AlertSignal(
        rule="repeated_feishu_access_failures",
        severity=SecurityAlert.SEVERITY_MEDIUM,
        title="Repeated Feishu access failures",
        reason=(
            f"{len(evidence)} Feishu requests failed within {window} minutes. "
            f"The configured threshold is {threshold}."
        ),
        recommendation=(
            "Verify the managed Feishu connection and configured archive "
            "permissions."
        ),
        **_rule_context(
            "repeated_feishu_access_failures",
            threshold,
            window,
        ),
        evidence=evidence,
    )


def _new_device_sensitive_action(event: AuditEvent) -> AlertSignal | None:
    if not (
        event.action in {"upload", "import", "sync"}
        and event.result == AuditEvent.RESULT_SUCCEEDED
        and event.actor_id
        and event.user_agent
    ):
        return None
    previous_devices = _subject_events(event).filter(
        created_at__gte=event.created_at - timedelta(days=30),
        created_at__lt=event.created_at,
    ).exclude(Q(user_agent="") | Q(user_agent=event.user_agent))
    if not previous_devices.exists():
        return None
    return AlertSignal(
        rule="new_device_sensitive_action",
        severity=SecurityAlert.SEVERITY_MEDIUM,
        title="New device performed a sensitive action",
        reason=(
            "A new browser performed a sensitive Quote Desk action after "
            "another device had used this account in the last 30 days."
        ),
        recommendation=(
            "Confirm that the user recognizes this device and authorized the "
            "sensitive action."
        ),
        **_rule_context("new_device_sensitive_action", 1, 43200),
        evidence=(event,),
    )


def _object_id_enumeration(event: AuditEvent) -> AlertSignal | None:
    if event.reason_code != "resource_not_found" or not event.target_id:
        return None
    threshold = settings.QUOTATION_SECURITY_ENUMERATION_THRESHOLD
    window = settings.QUOTATION_SECURITY_ENUMERATION_WINDOW_MINUTES
    evidence = _window_evidence(
        event,
        window,
        reason_code="resource_not_found",
    )
    distinct_targets = {
        item.target_id for item in evidence if item.target_id
    }
    if len(distinct_targets) < threshold:
        return None
    return AlertSignal(
        rule="object_id_enumeration",
        severity=SecurityAlert.SEVERITY_HIGH,
        title="Possible object ID enumeration",
        reason=(
            f"One account requested at least {threshold} distinct missing "
            f"objects within {window} minutes."
        ),
        recommendation=(
            "Review the requested IDs and revoke the session if this was not "
            "an expected integration."
        ),
        **_rule_context("object_id_enumeration", threshold, window),
        evidence=evidence,
    )


def _configuration_change(event: AuditEvent) -> AlertSignal | None:
    catalog_change = event.module == "catalog" and event.action in {
        "create",
        "update",
        "delete",
        "import",
    }
    storage_change = event.event_name in {
        "storage.connection_created",
        "storage.connection_disabled",
        "storage.connection_credential_rotated",
        "storage.mount_created",
        "storage.mount_updated",
        "storage.mount_deleted",
    }
    if event.result != AuditEvent.RESULT_SUCCEEDED:
        return None
    if not catalog_change and not storage_change:
        return None
    return AlertSignal(
        rule="configuration_change",
        severity=SecurityAlert.SEVERITY_MEDIUM,
        title="Quote Desk configuration changed",
        reason="A user changed a Quote Desk catalog configuration.",
        recommendation="Confirm that the configuration change was approved.",
        **_rule_context("configuration_change", 1, 1),
        evidence=(event,),
    )


def _credential_refresh_failure(event: AuditEvent) -> AlertSignal | None:
    if not (
        event.event_name == "feishu.oauth.refresh_failed"
        and event.result == AuditEvent.RESULT_FAILED
    ):
        return None
    return AlertSignal(
        rule="credential_refresh_failure",
        severity=SecurityAlert.SEVERITY_HIGH,
        title="Feishu credential refresh failed",
        reason="A managed Feishu credential could not be refreshed.",
        recommendation=(
            "Check the managed connection and rotate credentials if the "
            "failure persists."
        ),
        **_rule_context("credential_refresh_failure", 1, 1),
        evidence=(event,),
    )


def _sync_failure_backlog(event: AuditEvent) -> AlertSignal | None:
    sync_actions = ["sync", "sync_failed"]
    if (
        event.action not in sync_actions
        or event.result != AuditEvent.RESULT_FAILED
    ):
        return None
    threshold = settings.QUOTATION_SECURITY_SYNC_FAILURE_THRESHOLD
    window = settings.QUOTATION_SECURITY_SYNC_FAILURE_WINDOW_MINUTES
    evidence = _window_evidence(
        event,
        window,
        action__in=sync_actions,
        result=AuditEvent.RESULT_FAILED,
    )
    if len(evidence) < threshold:
        return None
    return AlertSignal(
        rule="sync_failure_backlog",
        severity=SecurityAlert.SEVERITY_HIGH,
        title="Repeated archive synchronization failures",
        reason=(
            f"{len(evidence)} archive synchronizations failed within "
            f"{window} minutes."
        ),
        recommendation=(
            "Check the managed connection, archive mount, and failed sync "
            "jobs before retrying."
        ),
        **_rule_context("sync_failure_backlog", threshold, window),
        evidence=evidence,
    )


RULE_EVALUATORS = (
    _repeated_access_denials,
    _unusual_bulk_downloads,
    _repeated_feishu_failures,
    _new_device_sensitive_action,
    _object_id_enumeration,
    _configuration_change,
    _credential_refresh_failure,
    _sync_failure_backlog,
)


def _merge_signal(event: AuditEvent, signal: AlertSignal) -> SecurityAlert:
    active_statuses = (
        SecurityAlert.STATUS_OPEN,
        SecurityAlert.STATUS_ACKNOWLEDGED,
    )
    with transaction.atomic():
        alert = (
            SecurityAlert.objects.select_for_update()
            .filter(
                rule=signal.rule,
                subject_key=_subject_key(event),
                status__in=active_statuses,
            )
            .first()
        )
        if alert is None:
            alert = SecurityAlert.objects.create(
                rule=signal.rule,
                severity=signal.severity,
                title=signal.title,
                reason=signal.reason,
                recommendation=signal.recommendation,
                runbook=signal.runbook,
                owner=signal.owner,
                threshold=signal.threshold,
                window_minutes=signal.window_minutes,
                subject_key=_subject_key(event),
                subject_email=event.actor_email,
                subject_name=event.actor_name,
                source_ip=event.ip_address,
                subject_user_agent=event.user_agent,
                trigger_count=len(signal.evidence),
                first_detected_at=signal.evidence[0].created_at,
                last_detected_at=signal.evidence[-1].created_at,
            )
        else:
            alert.severity = signal.severity
            alert.reason = signal.reason
            alert.recommendation = signal.recommendation
            alert.runbook = signal.runbook
            alert.owner = signal.owner
            alert.threshold = signal.threshold
            alert.window_minutes = signal.window_minutes
            alert.source_ip = event.ip_address or alert.source_ip
            alert.subject_user_agent = (
                event.user_agent or alert.subject_user_agent
            )
            alert.trigger_count = max(
                alert.trigger_count,
                len(signal.evidence),
            )
            alert.last_detected_at = max(
                alert.last_detected_at,
                signal.evidence[-1].created_at,
            )
            alert.save(
                update_fields=[
                    "severity",
                    "reason",
                    "recommendation",
                    "runbook",
                    "owner",
                    "threshold",
                    "window_minutes",
                    "source_ip",
                    "subject_user_agent",
                    "trigger_count",
                    "last_detected_at",
                    "updated_at",
                ]
            )
        alert.evidence_events.add(*signal.evidence)
        return alert


def evaluate_security_event(event: AuditEvent) -> list[SecurityAlert]:
    """Evaluate one committed audit event against configured rules."""
    alerts = []
    for evaluator in RULE_EVALUATORS:
        signal = evaluator(event)
        if signal is not None:
            alerts.append(_merge_signal(event, signal))
    return alerts
