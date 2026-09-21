from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.access import filter_accessible_quotations
from quotation.models import Quotation
from quotation.serializers import (
    DashboardCurrencyQuerySerializer,
    DashboardRecentQuerySerializer,
    DashboardSummaryQuerySerializer,
)
from quotation.services.dashboard import (
    build_dashboard_analytics,
    build_dashboard_recent,
    build_dashboard_summary,
)


def _accessible_quotations(request):
    return filter_accessible_quotations(
        request.user,
        Quotation.objects.all(),
    )


class DashboardSummaryView(APIView):
    """Return the quotation dashboard KPI summary."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = DashboardSummaryQuerySerializer(
            data=request.query_params
        )
        serializer.is_valid(raise_exception=True)
        payload = build_dashboard_summary(
            _accessible_quotations(request),
            serializer.validated_data["currency"],
            serializer.validated_data["period"],
            serializer.validated_data.get("date_from", ""),
            serializer.validated_data.get("date_to", ""),
        )
        return Response(payload)


class DashboardAnalyticsView(APIView):
    """Return bounded quotation dashboard chart aggregates."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = DashboardCurrencyQuerySerializer(
            data=request.query_params
        )
        serializer.is_valid(raise_exception=True)
        payload = build_dashboard_analytics(
            _accessible_quotations(request),
            serializer.validated_data["currency"],
            serializer.validated_data.get("date_from", ""),
            serializer.validated_data.get("date_to", ""),
        )
        return Response(payload)


class DashboardRecentView(APIView):
    """Return the latest accessible quotations as a narrow projection."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = DashboardRecentQuerySerializer(
            data=request.query_params
        )
        serializer.is_valid(raise_exception=True)
        payload = build_dashboard_recent(
            _accessible_quotations(request),
            serializer.validated_data["limit"],
            serializer.validated_data.get("currency", "USD"),
            serializer.validated_data.get("date_from", ""),
            serializer.validated_data.get("date_to", ""),
        )
        return Response(payload)


class DashboardOverviewView(APIView):
    """Return the dashboard summary, charts, and recent rows together."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = DashboardCurrencyQuerySerializer(
            data=request.query_params
        )
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        quotations = _accessible_quotations(request)
        summary = build_dashboard_summary(
            quotations,
            values["currency"],
            "",
            values.get("date_from", ""),
            values.get("date_to", ""),
        )
        available_currencies = summary["available_currencies"]
        return Response(
            {
                "summary": summary,
                "analytics": build_dashboard_analytics(
                    quotations,
                    values["currency"],
                    values.get("date_from", ""),
                    values.get("date_to", ""),
                    available_currencies,
                ),
                "recent": build_dashboard_recent(
                    quotations,
                    5,
                    values["currency"],
                    values.get("date_from", ""),
                    values.get("date_to", ""),
                ),
            }
        )
