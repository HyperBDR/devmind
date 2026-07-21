from __future__ import annotations

import csv
from datetime import timedelta
from io import StringIO

from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.audit import record_audit_event
from quotation.models import AuditEvent, SecurityAlert
from quotation.security_alerts import can_manage_security_alerts
from quotation.serializers import (
    AuditEventSerializer,
    SecurityAlertDetailSerializer,
    SecurityAlertResolutionSerializer,
    SecurityAlertSerializer,
)


def _can_manage_alerts(user) -> bool:
    """Return whether the user may change a security alert's state."""
    return can_manage_security_alerts(user)


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
    if not include_internal:
        queryset = queryset.exclude(
            Q(metadata__has_key="automatic") & Q(metadata__automatic=True)
        ).exclude(
            module__in=["replica"],
        ).exclude(
            target_type="request",
        ).exclude(
            module="audit",
            action="view",
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
        response = Response(
            {
                "items": AuditEventSerializer(
                    events,
                    many=True,
                    context={"request": request},
                ).data,
                "total": total,
                "page": page,
                "page_size": page_size,
                "can_export": _can_manage_alerts(request.user),
            }
        )
        record_audit_event(
            request=request,
            module="audit",
            action="view",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="audit_log",
            summary="Viewed audit records.",
            metadata={"status_code": 200},
        )
        response._quotation_audit_handled = True
        return response


class AuditEventExportView(APIView):
    """Export filtered audit events for explicit administrators."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _can_manage_alerts(request.user):
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
                "risk_level",
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
                    event.risk_level,
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


class SecurityAlertListView(APIView):
    """Return security alerts and review summary to authenticated users."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = SecurityAlert.objects.prefetch_related("evidence_events")
        search = request.query_params.get("search", "").strip()
        severity = request.query_params.get("severity", "").strip()
        status_filter = request.query_params.get("status", "").strip()
        rule = request.query_params.get("rule", "").strip()
        days = request.query_params.get("days", "30").strip()

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(subject_email__icontains=search)
                | Q(subject_name__icontains=search)
                | Q(source_ip__icontains=search)
            )
        if severity:
            queryset = queryset.filter(severity=severity)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if rule:
            queryset = queryset.filter(rule=rule)
        if days and days != "all":
            try:
                day_count = min(max(int(days), 1), 365)
            except ValueError as error:
                raise ValidationError("Invalid date range.") from error
            queryset = queryset.filter(
                last_detected_at__gte=timezone.now()
                - timedelta(days=day_count)
            )

        page, page_size = _pagination(request)
        total = queryset.count()
        start = (page - 1) * page_size
        alerts = queryset[start : start + page_size]
        active = SecurityAlert.objects.filter(
            status__in=[
                SecurityAlert.STATUS_OPEN,
                SecurityAlert.STATUS_ACKNOWLEDGED,
            ]
        )
        last_day = timezone.now() - timedelta(hours=24)
        new_alerts = SecurityAlert.objects.filter(
            first_detected_at__gte=last_day
        )
        summary = {
            "open": active.count(),
            "critical": active.filter(
                severity=SecurityAlert.SEVERITY_CRITICAL
            ).count(),
            "high": active.filter(
                severity=SecurityAlert.SEVERITY_HIGH
            ).count(),
            "new_last_24_hours": new_alerts.count(),
            "immediate_review": active.filter(
                severity__in=[
                    SecurityAlert.SEVERITY_CRITICAL,
                    SecurityAlert.SEVERITY_HIGH,
                ]
            ).count(),
            "affected_users_last_24_hours": new_alerts.exclude(
                subject_key="system:anonymous"
            ).values("subject_key").distinct().count(),
        }
        return Response(
            {
                "items": SecurityAlertSerializer(
                    alerts,
                    many=True,
                    context={"request": request},
                ).data,
                "summary": summary,
                "total": total,
                "page": page,
                "page_size": page_size,
                "can_manage": _can_manage_alerts(request.user),
            }
        )


class SecurityAlertDetailView(APIView):
    """Return alert evidence and handle the administrative workflow."""

    permission_classes = [IsAuthenticated]

    def get_object(self, alert_id: int) -> SecurityAlert:
        return get_object_or_404(
            SecurityAlert.objects.prefetch_related("evidence_events"),
            id=alert_id,
        )

    def get(self, request, alert_id: int):
        alert = self.get_object(alert_id)
        return Response(
            {
                "alert": SecurityAlertDetailSerializer(
                    alert,
                    context={"request": request},
                ).data,
                "can_manage": _can_manage_alerts(request.user),
            }
        )

    def patch(self, request, alert_id: int):
        if not _can_manage_alerts(request.user):
            raise PermissionDenied(
                "Only administrators can manage security alerts."
            )
        alert = self.get_object(alert_id)
        serializer = SecurityAlertResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        action = values["action"]

        if alert.status in {
            SecurityAlert.STATUS_RESOLVED,
            SecurityAlert.STATUS_FALSE_POSITIVE,
        }:
            raise ValidationError("This alert has already been resolved.")
        now = timezone.now()
        if action == "acknowledge":
            alert.status = SecurityAlert.STATUS_ACKNOWLEDGED
            alert.acknowledged_by = request.user
            alert.acknowledged_at = now
            update_fields = [
                "status",
                "acknowledged_by",
                "acknowledged_at",
                "updated_at",
            ]
        else:
            resolution = values["resolution"]
            alert.status = (
                SecurityAlert.STATUS_FALSE_POSITIVE
                if resolution == SecurityAlert.RESOLUTION_FALSE_POSITIVE
                else SecurityAlert.STATUS_RESOLVED
            )
            alert.resolved_by = request.user
            alert.resolved_at = now
            alert.resolution = resolution
            alert.resolution_note = values["resolution_note"].strip()
            alert.notify_affected_user = values["notify_affected_user"]
            update_fields = [
                "status",
                "resolved_by",
                "resolved_at",
                "resolution",
                "resolution_note",
                "notify_affected_user",
                "updated_at",
            ]
        alert.save(update_fields=update_fields)
        record_audit_event(
            request=request,
            module="security",
            action=action,
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="security_alert",
            target_id=str(alert.id),
            target_label=SecurityAlertSerializer(
                alert,
                context={"request": request},
            ).data["alert_number"],
            summary=f"Security alert {action}d.",
        )
        response = Response(
            {
                "alert": SecurityAlertDetailSerializer(
                    alert,
                    context={"request": request},
                ).data,
                "can_manage": True,
            }
        )
        response._quotation_audit_handled = True
        return response
