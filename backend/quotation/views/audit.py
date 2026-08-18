from __future__ import annotations

import csv
from io import StringIO

from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.audit import business_audit_events_query, record_audit_event
from quotation.models import AuditEvent
from quotation.permissions import is_quotation_platform_admin
from quotation.serializers import AuditEventSerializer


def _can_export_audit(user) -> bool:
    """Return whether the user may export operation audit records."""
    return is_quotation_platform_admin(user)


def _pagination(request) -> tuple[int, int]:
    """Return bounded pagination parameters or raise a DRF error."""
    try:
        page = max(int(request.query_params.get("page", 1)), 1)
        page_size = min(
            max(int(request.query_params.get("page_size", 20)), 1),
            100,
        )
    except (TypeError, ValueError) as error:
        raise ValidationError("Invalid pagination.") from error
    return page, page_size


def _audit_queryset(request):
    """Return audit events filtered by the supported query contract."""
    queryset = AuditEvent.objects.select_related("actor").all()
    include_internal = (
        request.query_params.get("include_internal", "").lower() == "true"
    )
    if include_internal and not is_quotation_platform_admin(request.user):
        record_audit_event(
            request=request,
            module="audit",
            action="view",
            result=AuditEvent.RESULT_DENIED,
            target_type="audit_log",
            summary="Internal audit access denied.",
            reason_code="administrator_required",
            error_code="authorization_denied",
            metadata={"status_code": 403},
        )
        raise PermissionDenied(
            "Only administrators can view internal audit records."
        )
    if not include_internal:
        queryset = queryset.filter(
            business_audit_events_query(),
        ).exclude(
            result=AuditEvent.RESULT_DENIED,
        ).exclude(
            Q(metadata__has_key="automatic") & Q(metadata__automatic=True)
        )
    search = request.query_params.get("search", "").strip()
    filters = {
        "actor": request.query_params.get("actor", "").strip(),
        "module": request.query_params.get("module", "").strip(),
        "action": request.query_params.get("action", "").strip(),
        "event_name": request.query_params.get("event_name", "").strip(),
        "result": request.query_params.get("result", "").strip(),
        "risk_level": request.query_params.get("risk_level", "").strip(),
        "request_id": request.query_params.get("request_id", "").strip(),
        "quotation_id_snapshot": request.query_params.get(
            "quotation_id",
            "",
        ).strip(),
        "document_id_snapshot": request.query_params.get(
            "document_id",
            "",
        ).strip(),
        "workspace_id": request.query_params.get("workspace_id", "").strip(),
        "source_organization_id": request.query_params.get(
            "source_organization_id",
            "",
        ).strip(),
        "target_organization_id": request.query_params.get(
            "target_organization_id",
            "",
        ).strip(),
    }
    date_from = parse_date(request.query_params.get("date_from", ""))
    date_to = parse_date(request.query_params.get("date_to", ""))
    if search:
        queryset = queryset.filter(
            Q(actor_email__icontains=search)
            | Q(actor_name__icontains=search)
            | Q(target_id__icontains=search)
            | Q(target_label__icontains=search)
            | Q(summary__icontains=search)
            | Q(event_name__icontains=search)
            | Q(request_id__icontains=search)
        )
    actor = filters.pop("actor")
    if actor:
        queryset = queryset.filter(
            Q(actor_email__iexact=actor) | Q(actor_name__iexact=actor)
        )
    for field, value in filters.items():
        if value:
            queryset = queryset.filter(**{field: value})
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    return queryset


class AuditEventListView(APIView):
    """Return immutable audit events to any authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = _audit_queryset(request)
        page, page_size = _pagination(request)

        total = queryset.count()
        start = (page - 1) * page_size
        events = queryset[start : start + page_size]
        return Response(
            {
                "items": AuditEventSerializer(
                    events,
                    many=True,
                    context={"request": request},
                ).data,
                "total": total,
                "page": page,
                "page_size": page_size,
                "can_export": _can_export_audit(request.user),
            }
        )


class AuditEventExportView(APIView):
    """Export filtered audit events for explicit administrators."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _can_export_audit(request.user):
            record_audit_event(
                request=request,
                module="audit",
                action="export",
                result=AuditEvent.RESULT_DENIED,
                target_type="audit_log",
                summary="Audit export denied.",
                reason_code="administrator_required",
                error_code="authorization_denied",
                metadata={"status_code": 403},
            )
            raise PermissionDenied(
                "Only administrators can export audit records."
            )
        max_rows = settings.QUOTATION_AUDIT_EXPORT_MAX_ROWS
        rows = list(_audit_queryset(request)[:max_rows])
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "occurred_at",
                "event_name",
                "actor",
                "actor_role",
                "action",
                "result",
                "reason_code",
                "target_type",
                "target_id",
                "request_id",
                "trace_id",
            ]
        )
        for event in rows:
            writer.writerow(
                [
                    event.created_at.isoformat(),
                    event.event_name,
                    event.actor_email or event.actor_name,
                    event.actor_role_snapshot,
                    event.action,
                    event.result,
                    event.reason_code,
                    event.target_type,
                    event.target_id,
                    event.request_id,
                    event.trace_id,
                ]
            )
        record_audit_event(
            request=request,
            module="audit",
            action="export",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="audit_log",
            summary=f"Exported {len(rows)} audit records.",
            metadata={"status_code": 200},
        )
        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="quote-desk-audit.csv"'
        )
        response._quotation_audit_handled = True
        return response
