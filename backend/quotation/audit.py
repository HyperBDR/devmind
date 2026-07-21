from __future__ import annotations

from contextvars import ContextVar
from hashlib import sha256
from ipaddress import ip_address
import re
from typing import Any

from quotation.models import AuditEvent
from quotation.permissions import user_role
from quotation.security_alerts import evaluate_security_event


AUDIT_CONTEXT: ContextVar[dict[str, str]] = ContextVar(
    "quotation_audit_context",
    default={},
)


def set_request_audit_target(
    request,
    *,
    target_id: str = "",
    target_label: str = "",
) -> None:
    """Attach a safe business target for response-level audit capture."""
    raw_request = getattr(request, "_request", request)
    if target_id:
        raw_request.quotation_audit_target_id = str(target_id)
    if target_label:
        raw_request.quotation_audit_target_label = str(target_label)

SENSITIVE_KEY_PARTS = {
    "access_token",
    "authorization",
    "body",
    "code",
    "cookie",
    "html",
    "jwt",
    "password",
    "refresh_token",
    "secret",
    "signature",
    "state",
    "token",
}

ALLOWED_METADATA_KEYS = {
    "automatic",
    "catalog_item_type",
    "duration_ms",
    "fields",
    "file_type",
    "http_method",
    "provider",
    "status_code",
    "version_no",
}

EVENT_NAMES = {
    ("quotation", "create"): "quotation.created",
    ("quotation", "view"): "quotation.viewed",
    ("quotation", "update"): "quotation.updated",
    ("quotation", "delete"): "quotation.deleted",
    ("quotation", "generate"): "quotation.generated",
    ("document", "upload"): "document.uploaded",
    ("document", "download"): "document.downloaded",
    ("document", "delete"): "document.deleted",
    ("feishu", "upload"): "document.uploaded",
    ("feishu", "import"): "document.imported",
    ("feishu", "open"): "document.opened",
    ("feishu", "sync"): "storage.archive_synced",
    ("feishu", "connect"): "feishu.oauth.connected",
    ("feishu", "disconnect"): "feishu.oauth.disconnected",
    ("feishu", "refresh"): "feishu.oauth.refresh_failed",
    ("catalog", "create"): "catalog.item_created",
    ("catalog", "update"): "catalog.item_updated",
    ("catalog", "delete"): "catalog.item_deleted",
    ("audit", "view"): "audit.viewed",
    ("audit", "export"): "audit.exported",
    ("security", "acknowledge"): "security.alert_acknowledged",
    ("security", "resolve"): "security.alert_resolved",
    ("storage", "connection_created"): "storage.connection_created",
    ("storage", "connection_disabled"): "storage.connection_disabled",
    ("storage", "credential_rotated"): (
        "storage.connection_credential_rotated"
    ),
    ("storage", "health_checked"): "storage.connection_health_checked",
    ("storage", "mount_created"): "storage.mount_created",
    ("storage", "mount_updated"): "storage.mount_updated",
    ("storage", "mount_deleted"): "storage.mount_deleted",
    ("replica", "sync_started"): "document.replica_sync_started",
    ("replica", "sync_succeeded"): "document.replica_sync_succeeded",
    ("replica", "sync_failed"): "document.replica_sync_failed",
    ("replica", "revoked"): "document.replica_revoked",
}


def _actor_name(actor) -> str:
    """Return a stable display name snapshot for an audit actor."""
    if actor is None:
        return ""
    full_name = getattr(actor, "get_full_name", lambda: "")() or ""
    return full_name.strip() or getattr(actor, "username", "") or ""


def _client_ip(request) -> str | None:
    """Return a validated client IP address."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    raw_value = forwarded.split(",")[0].strip() if forwarded else None
    raw_value = raw_value or request.META.get("REMOTE_ADDR")
    if not raw_value:
        return None
    try:
        return str(ip_address(raw_value))
    except ValueError:
        return None


def _safe_text(value: Any, max_length: int) -> str:
    """Return bounded text with common credential forms removed."""
    text = str(value or "")
    text = re.sub(
        r"(?i)bearer\s+[a-z0-9._~+/-]+=*",
        "Bearer [REDACTED]",
        text,
    )
    text = re.sub(
        r"(?i)(token|secret|password|code|state)\s*[=:]\s*[^\s,;]+",
        r"\1=[REDACTED]",
        text,
    )
    return text[:max_length]


def _safe_mapping(
    value: dict | None,
    *,
    allowlist: set[str] | None = None,
) -> dict:
    """Return a shallow allowlisted mapping without sensitive values."""
    if not isinstance(value, dict):
        return {}
    output = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key)[:100]
        lowered = key.lower()
        if allowlist is not None and key not in allowlist:
            continue
        if allowlist is None and any(
            part in lowered for part in SENSITIVE_KEY_PARTS
        ):
            continue
        if isinstance(raw_value, (str, int, float, bool)) or raw_value is None:
            output[key] = _safe_text(raw_value, 500) if isinstance(
                raw_value,
                str,
            ) else raw_value
        elif isinstance(raw_value, list):
            output[key] = [
                _safe_text(item, 100)
                for item in raw_value[:50]
                if isinstance(item, (str, int, float, bool))
            ]
    return output


def event_name_for(module: str, action: str) -> str:
    """Return the stable dotted event name for one operation."""
    return EVENT_NAMES.get((module, action), f"{module}.{action}")


def risk_level_for(module: str, action: str, result: str) -> str:
    """Return a low-cardinality risk level for an operation."""
    if result == AuditEvent.RESULT_DENIED:
        return AuditEvent.RISK_HIGH
    if action in {"delete", "export", "resolve"}:
        return AuditEvent.RISK_HIGH
    if module in {
        "feishu",
        "catalog",
        "security",
        "storage",
        "replica",
    } or action == "download":
        return AuditEvent.RISK_MEDIUM
    return AuditEvent.RISK_LOW


def record_audit_event(
    *,
    request,
    module: str,
    action: str,
    result: str,
    target_type: str = "",
    target_id: str = "",
    target_label: str = "",
    summary: str = "",
    changes: dict | None = None,
    metadata: dict | None = None,
    event_name: str = "",
    reason_code: str = "",
    risk_level: str = "",
    actor_type: str = "",
    before_summary: dict | None = None,
    after_summary: dict | None = None,
    quotation_id: str = "",
    document_id: str = "",
    workspace_id: str = "",
    storage_connection_id: str = "",
    source_organization_id: str = "",
    target_organization_id: str = "",
    sync_job_id: str = "",
    error_code: str = "",
) -> AuditEvent:
    """Persist one immutable, allowlisted Quote Desk audit event."""
    actor = getattr(request, "user", None)
    if not getattr(actor, "is_authenticated", False):
        actor = None
    context = AUDIT_CONTEXT.get()
    automatic = request.META.get(
        "HTTP_X_QUOTATION_AUDIT_SOURCE",
        "",
    ).lower() == "automatic"
    resolved_actor_type = actor_type or (
        AuditEvent.ACTOR_SYSTEM if automatic else AuditEvent.ACTOR_USER
    )
    request_id = (
        getattr(request, "audit_request_id", "")
        or request.META.get("HTTP_X_REQUEST_ID")
        or request.META.get("HTTP_X_CORRELATION_ID")
        or context.get("request_id", "")
    )
    trace_id = (
        getattr(request, "audit_trace_id", "")
        or request.META.get("HTTP_X_TRACE_ID")
        or context.get("trace_id", "")
        or request_id
    )
    resolved_event_name = event_name or event_name_for(module, action)
    resolved_risk = risk_level or risk_level_for(module, action, result)
    resolved_quotation_id = quotation_id
    resolved_document_id = document_id
    if target_type == "quotation" and not resolved_quotation_id:
        resolved_quotation_id = target_id
    if target_type == "document" and not resolved_document_id:
        resolved_document_id = target_id
    safe_metadata = _safe_mapping(
        {**(metadata or {}), "automatic": automatic},
        allowlist=ALLOWED_METADATA_KEYS,
    )
    raw_idempotency_key = request.META.get("HTTP_IDEMPOTENCY_KEY", "").strip()
    idempotency_key = None
    if raw_idempotency_key:
        actor_key = str(getattr(actor, "pk", "") or "anonymous")
        idempotency_material = "|".join(
            [
                actor_key,
                raw_idempotency_key[:200],
                resolved_event_name,
                target_type[:100],
                _safe_text(target_id, 100),
            ]
        )
        idempotency_key = sha256(
            idempotency_material.encode("utf-8")
        ).hexdigest()
        existing = AuditEvent.objects.filter(
            idempotency_key=idempotency_key
        ).first()
        if existing is not None:
            return existing
    event = AuditEvent.objects.create(
        actor=actor,
        actor_email=getattr(actor, "email", "") or "",
        actor_name=_actor_name(actor),
        actor_type=resolved_actor_type,
        actor_role_snapshot=user_role(actor) if actor else "",
        impersonator_id=_safe_text(
            request.META.get("HTTP_X_IMPERSONATOR_ID", ""),
            100,
        ),
        event_name=resolved_event_name[:100],
        module=module[:50],
        action=action[:50],
        result=result,
        target_type=target_type[:100],
        target_id=_safe_text(target_id, 100),
        target_label=_safe_text(target_label, 255),
        summary=_safe_text(summary, 500),
        before_summary=_safe_mapping(before_summary),
        after_summary=_safe_mapping(after_summary),
        changes=_safe_mapping(changes, allowlist={"fields"}),
        metadata=safe_metadata,
        request_id=_safe_text(request_id, 100),
        trace_id=_safe_text(trace_id, 100),
        reason_code=_safe_text(reason_code, 100),
        risk_level=resolved_risk,
        workspace_id=_safe_text(workspace_id, 100),
        quotation_id_snapshot=_safe_text(resolved_quotation_id, 100),
        document_id_snapshot=_safe_text(resolved_document_id, 100),
        storage_connection_id=_safe_text(storage_connection_id, 100),
        source_organization_id=_safe_text(source_organization_id, 100),
        target_organization_id=_safe_text(target_organization_id, 100),
        sync_job_id=_safe_text(sync_job_id, 100),
        error_code=_safe_text(error_code, 100),
        idempotency_key=idempotency_key,
        ip_address=_client_ip(request),
        user_agent=_safe_text(request.META.get("HTTP_USER_AGENT", ""), 500),
    )
    evaluate_security_event(event)
    return event
