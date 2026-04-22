"""
Views for recharge approval callbacks and records.
"""

from __future__ import annotations

import os
from hmac import compare_digest

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import generics

from ..models import RechargeApprovalRecord
from ..serializers import RechargeApprovalRecordSerializer
from ..services.recharge_approval import (
    create_recharge_approval_event,
    normalize_feishu_status,
)

# Final statuses that trigger a notification
FINAL_RECHARGE_STATUSES = {
    RechargeApprovalRecord.STATUS_APPROVED,
    RechargeApprovalRecord.STATUS_REJECTED,
    RechargeApprovalRecord.STATUS_CANCELED,
    RechargeApprovalRecord.STATUS_FAILED,
}


def _get_callback_verification_token() -> str:
    return str(
        os.getenv("FEISHU_CALLBACK_VERIFICATION_TOKEN")
        or os.getenv("FEISHU_VERIFICATION_TOKEN")
        or ""
    ).strip()


def _extract_callback_token(payload, request) -> str:
    token = ""
    if isinstance(payload, dict):
        token = str(
            payload.get("token")
            or payload.get("verification_token")
            or payload.get("verify_token")
            or payload.get("verificationToken")
            or ""
        ).strip()
    if not token:
        for header_name in (
            "X-Lark-Event-Token",
            "X-Feishu-Event-Token",
            "X-Feishu-Verification-Token",
        ):
            token = str(request.headers.get(header_name) or "").strip()
            if token:
                break
    return token


class RechargeApprovalListView(generics.ListAPIView):
    queryset = RechargeApprovalRecord.objects.select_related(
        "provider",
        "alert_record",
        "triggered_by",
        "submitted_by",
        "latest_llm_usage",
    ).prefetch_related("events", "llm_runs")
    serializer_class = RechargeApprovalRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = self.queryset
        provider_id = self.request.query_params.get("provider")
        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        return queryset


class RechargeApprovalDetailView(generics.RetrieveAPIView):
    queryset = RechargeApprovalRecord.objects.select_related(
        "provider",
        "alert_record",
        "triggered_by",
        "submitted_by",
        "latest_llm_usage",
    ).prefetch_related("events", "llm_runs")
    serializer_class = RechargeApprovalRecordSerializer
    permission_classes = [IsAuthenticated]


class RechargeApprovalFeishuCallbackView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["cloud-billing"],
        summary="Receive Feishu recharge approval callback",
        description=(
            "Receive Feishu approval status callbacks and sync recharge "
            "approval record status."
        ),
        responses={200: {"type": "object"}},
    )
    def post(self, request):
        payload = request.data or {}
        callback_type = str(payload.get("type") or "").strip()
        challenge = payload.get("challenge")
        if callback_type == "url_verification" and challenge:
            return Response({"challenge": challenge})

        expected_token = _get_callback_verification_token()
        received_token = _extract_callback_token(payload, request)
        if not expected_token or not received_token or not compare_digest(
            received_token, expected_token
        ):
            return Response(
                {
                    "ok": False,
                    "ignored": True,
                    "reason": "invalid_callback_token",
                },
                status=403,
            )

        event = payload.get("event") or payload
        instance_code = str(
            event.get("instance_code") or event.get("instanceCode") or ""
        ).strip()
        approval_code = str(
            event.get("approval_code") or event.get("approvalCode") or ""
        ).strip()
        if not instance_code:
            return Response({"ok": True, "ignored": True, "reason": "missing_instance_code"})

        record = RechargeApprovalRecord.objects.filter(
            feishu_instance_code=instance_code
        ).first()
        if record is None and approval_code:
            record = RechargeApprovalRecord.objects.filter(
                feishu_approval_code=approval_code
            ).order_by("-created_at").first()
        if record is None:
            return Response({"ok": True, "ignored": True, "reason": "record_not_found"})

        status_text = str(
            event.get("status") or event.get("approval_status") or ""
        ).strip()
        timeline = event.get("timeline") or event.get("approval_timeline") or []
        record.status = normalize_feishu_status(status_text)
        record.status_message = status_text or record.status_message
        record.callback_payload = payload
        if isinstance(timeline, list):
            record.approval_timeline = timeline
            if timeline:
                latest_node = timeline[-1]
                if isinstance(latest_node, dict):
                    record.latest_node_name = str(
                        latest_node.get("node_name")
                        or latest_node.get("name")
                        or latest_node.get("type")
                        or ""
                    ).strip()
                    record.latest_node_status = str(
                        latest_node.get("status")
                        or latest_node.get("type")
                        or status_text
                    ).strip()
        record.last_callback_at = timezone.now()
        record.latest_stage = "callback"
        record.save(
            update_fields=[
                "status",
                "status_message",
                "callback_payload",
                "approval_timeline",
                "latest_node_name",
                "latest_node_status",
                "last_callback_at",
                "latest_stage",
                "updated_at",
            ]
        )
        create_recharge_approval_event(
            record=record,
            event_type="callback_received",
            stage="callback",
            source="feishu_callback",
            message="Feishu callback received.",
            payload=payload,
            operator_label=str(
                event.get("user_id")
                or event.get("operator")
                or event.get("open_id")
                or ""
            ).strip(),
        )
        # Send notification for final statuses (approved/rejected/canceled/failed)
        if record.status in FINAL_RECHARGE_STATUSES:
            # Import here to avoid circular imports
            from ..tasks import send_recharge_approval_notification
            try:
                send_recharge_approval_notification.delay(record.id, record.status)
            except Exception:
                # Callback acknowledgement should not fail just because the
                # async notification broker is temporarily unavailable.
                pass
        return Response({"ok": True, "record_id": record.id, "status": record.status})
