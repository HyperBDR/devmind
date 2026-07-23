from __future__ import annotations

from datetime import timedelta
import json
import logging
import re
import uuid

from django.db import DatabaseError
from django.utils import timezone

from quotation.audit import AUDIT_CONTEXT, record_audit_event
from quotation.models import AuditEvent


logger = logging.getLogger(__name__)
API_PREFIX = "/api/v1/quotation/"
SENSITIVE_FIELDS = {
    "access_token",
    "authorization",
    "cookie",
    "password",
    "refresh_token",
    "token",
}


def _classify(method: str, path: str):
    """Return audit semantics for a user-facing Quote Desk request."""
    relative = path.removeprefix(API_PREFIX).strip("/")
    if relative.startswith("audit-events"):
        return None
    if relative.startswith("pdf/"):
        return None

    quotation = re.fullmatch(r"quotations/([^/]+)", relative)
    if relative == "quotations" and method == "POST":
        return "quotation", "create", "quotation"
    if quotation and method == "GET":
        return "quotation", "view", "quotation"
    if quotation and method in {"PUT", "PATCH"}:
        return "quotation", "update", "quotation"
    if quotation and method == "DELETE":
        return "quotation", "delete", "quotation"
    if re.fullmatch(r"quotations/[^/]+/generate", relative):
        return "quotation", "generate", "quotation"
    if re.fullmatch(r"quotations/[^/]+/documents", relative):
        if method == "POST":
            return "document", "upload", "document"
        if method == "GET":
            return "document", "view", "quotation"

    if re.fullmatch(r"documents/[^/]+/download", relative):
        return "document", "download", "document"
    if re.fullmatch(r"documents/[^/]+", relative) and method == "DELETE":
        return "document", "delete", "document"

    if relative == "feishu/sync-folder" and method == "POST":
        return "feishu", "sync", "folder"
    if relative == "feishu/upload" and method == "POST":
        return "feishu", "upload", "document"
    if relative.startswith("feishu/import/") and method == "POST":
        return "feishu", "import", "document"
    if relative == "feishu/files/access/batch":
        return None
    if "/content" in relative or "/access" in relative:
        return "feishu", "open", "document"
    if relative == "feishu/oauth/start" and method == "GET":
        return "feishu", "connect", "account"

    if relative.startswith("catalog") and method != "GET":
        action = "import" if "import" in relative else "update"
        return "catalog", action, "catalog"

    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "quotation", method.lower(), "request"
    return None


def _is_automatic_activity(request) -> bool:
    """Return whether the client marked a background refresh operation."""
    return (
        request.META.get("HTTP_X_QUOTATION_AUDIT_SOURCE", "").lower()
        == "automatic"
    )


class RequestIdMiddleware:
    """Propagate a bounded request ID and trace ID on every response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = (
            request.META.get("HTTP_X_REQUEST_ID")
            or request.META.get("HTTP_X_CORRELATION_ID")
            or ""
        ).strip()
        request_id = incoming[:100] if incoming else str(uuid.uuid4())
        incoming_trace = request.META.get("HTTP_X_TRACE_ID", "").strip()
        trace_id = incoming_trace[:100] or request_id
        request.audit_request_id = request_id
        request.audit_trace_id = trace_id
        request.META["HTTP_X_REQUEST_ID"] = request_id
        request.META["HTTP_X_TRACE_ID"] = trace_id
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        response["X-Trace-ID"] = trace_id
        return response


def _json_fields(request) -> list[str]:
    """Return safe top-level request field names without storing values."""
    if "application/json" not in request.META.get("CONTENT_TYPE", ""):
        return []
    try:
        content_length = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return []
    if content_length > 65536:
        return []
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    return sorted(
        key for key in payload if key.lower() not in SENSITIVE_FIELDS
    )


def _response_payload(response) -> dict:
    payload = getattr(response, "data", {})
    if not isinstance(payload, dict):
        return {}
    if isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


def _target_id(request, payload: dict) -> str:
    match = getattr(request, "resolver_match", None)
    kwargs = getattr(match, "kwargs", {}) if match else {}
    for key in ("quotation_id", "document_id", "file_token"):
        if kwargs.get(key):
            return str(kwargs[key])
    for key in ("id", "document_id", "quotation_id", "sync_job_id"):
        if payload.get(key):
            return str(payload[key])
    return str(getattr(request, "quotation_audit_target_id", "") or "")


def _target_label(request, payload: dict) -> str:
    request_label = str(
        getattr(request, "quotation_audit_target_label", "") or ""
    )
    if request_label:
        return request_label
    for key in ("quote_no", "file_name", "path", "name"):
        if payload.get(key):
            return str(payload[key])
    folders = payload.get("folders")
    if isinstance(folders, list) and folders:
        root = folders[0]
        if isinstance(root, dict) and root.get("name"):
            return str(root["name"])
    return ""


def _quotation_id(request, target_type: str, target_id: str) -> str:
    """Return a quotation relation from the route or request query."""
    match = getattr(request, "resolver_match", None)
    kwargs = getattr(match, "kwargs", {}) if match else {}
    return str(
        kwargs.get("quotation_id")
        or request.GET.get("quotation_id")
        or (target_id if target_type == "quotation" else "")
    )


def _audit_changes(
    module: str,
    action: str,
    changed_fields: list[str],
) -> dict:
    """Keep quote version details in version history, not the audit event."""
    if module == "quotation" and action in {"update", "generate"}:
        return {}
    return {"fields": changed_fields} if changed_fields else {}


def _audit_metadata(
    response,
    payload: dict,
    action: str,
    changed_fields: list[str],
) -> dict:
    """Return safe linkage metadata for an audit event."""
    metadata = {"status_code": response.status_code}
    version_no = payload.get("version_current")
    skip_pending_version = (
        action == "update" and "skip_version" in changed_fields
    )
    if isinstance(version_no, int) and not skip_pending_version:
        metadata["version_no"] = version_no
    return metadata


def _is_automatic_generate_followup(
    request,
    module: str,
    action: str,
    target_id: str,
) -> bool:
    """Return whether generate immediately follows a successful quote edit."""
    if module != "quotation" or action != "generate" or not target_id:
        return False
    actor = getattr(request, "user", None)
    if not getattr(actor, "is_authenticated", False):
        return False
    return AuditEvent.objects.filter(
        actor=actor,
        module="quotation",
        action="update",
        result=AuditEvent.RESULT_SUCCEEDED,
        target_id=target_id,
        created_at__gte=timezone.now() - timedelta(seconds=60),
    ).exists()


class QuotationAuditMiddleware:
    """Capture server-verified Quote Desk activity as append-only events."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        context_token = AUDIT_CONTEXT.set(
            {
                "request_id": getattr(request, "audit_request_id", ""),
                "trace_id": getattr(request, "audit_trace_id", ""),
            }
        )
        classification = None
        changed_fields: list[str] = []
        if request.path.startswith(API_PREFIX):
            classification = _classify(request.method, request.path)
            if classification:
                changed_fields = _json_fields(request)

        try:
            response = self.get_response(request)
            if _is_automatic_activity(request):
                return response
            if not classification or getattr(
                response,
                "_quotation_audit_handled",
                False,
            ):
                return response

            module, action, target_type = classification
            payload = _response_payload(response)
            succeeded = response.status_code < 400
            if response.status_code in {401, 403}:
                result = AuditEvent.RESULT_DENIED
                reason_code = "authorization_denied"
            elif succeeded:
                result = AuditEvent.RESULT_SUCCEEDED
                reason_code = ""
            else:
                result = AuditEvent.RESULT_FAILED
                reason_code = (
                    "resource_not_found"
                    if response.status_code == 404
                    else "operation_failed"
                )
            target_id = _target_id(request, payload)
            if succeeded and _is_automatic_generate_followup(
                request,
                module,
                action,
                target_id,
            ):
                return response
            try:
                event = record_audit_event(
                    request=request,
                    module=module,
                    action=action,
                    result=result,
                    target_type=target_type,
                    target_id=target_id,
                    target_label=_target_label(request, payload),
                    quotation_id=_quotation_id(
                        request,
                        target_type,
                        target_id,
                    ),
                    document_id=(
                        target_id if target_type == "document" else ""
                    ),
                    summary=(
                        "Operation denied"
                        if result == AuditEvent.RESULT_DENIED
                        else "Operation failed"
                        if result == AuditEvent.RESULT_FAILED
                        else ""
                    ),
                    reason_code=reason_code,
                    error_code=(
                        f"http_{response.status_code}" if not succeeded else ""
                    ),
                    sync_job_id=(
                        target_id
                        if module == "feishu" and action == "sync"
                        else ""
                    ),
                    storage_connection_id=str(
                        payload.get("storage_connection_id") or ""
                    ),
                    changes=_audit_changes(module, action, changed_fields),
                    metadata=_audit_metadata(
                        response,
                        payload,
                        action,
                        changed_fields,
                    ),
                )
                logger.info(
                    "quotation_audit_event",
                    extra={
                        "event_name": event.event_name,
                        "result": event.result,
                        "risk_level": event.risk_level,
                        "reason_code": event.reason_code,
                        "request_id": event.request_id,
                        "trace_id": event.trace_id,
                    },
                )
            except DatabaseError:
                logger.exception("Unable to persist quotation audit event")
            return response
        finally:
            AUDIT_CONTEXT.reset(context_token)
