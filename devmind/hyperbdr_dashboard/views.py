from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.access import get_effective_feature_keys

from .services import (
    build_hyperbdr_dashboard_monthly_trends,
    build_hyperbdr_dashboard_overview,
    build_hyperbdr_dashboard_tenants,
    build_hyperbdr_dashboard_trends,
)


FEATURE_KEY = "hyperbdr_dashboard"


def _check_feature_permission(user) -> None:
    """Raise PermissionDenied if user lacks the hyperbdr_dashboard feature."""
    features = get_effective_feature_keys(user)
    if FEATURE_KEY not in features:
        raise PermissionDenied(
            "You do not have access to the HyperMotion / HyperBDR Dashboard."
        )


class OverviewAPIView(APIView):
    """
    GET /api/v1/hyperbdr-dashboard/overview/

    Returns the full dashboard payload: KPIs, focus cards, distribution,
    conversion funnel, and tenant operations table.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["hyperbdr-dashboard"],
        summary="HyperMotion / HyperBDR Dashboard Overview",
        description="Returns KPIs, focus cards, distribution, funnel, and tenant table.",
    )
    def get(self, request):
        _check_feature_permission(request.user)
        payload = build_hyperbdr_dashboard_overview(
            year=int(request.query_params.get("year", 0)) or None,
            month=int(request.query_params.get("month", 0)) or None,
        )
        return Response(payload)


class TrendsAPIView(APIView):
    """
    GET /api/v1/hyperbdr-dashboard/trends/

    Returns trend/distribution data. For V1, returns the current snapshot.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["hyperbdr-dashboard"],
        summary="HyperMotion / HyperBDR Dashboard Trends",
        description="Returns utilization distribution and conversion data.",
    )
    def get(self, request):
        _check_feature_permission(request.user)
        days = int(request.query_params.get("days", 30))
        days = max(1, min(days, 365))
        payload = build_hyperbdr_dashboard_trends(days=days)
        return Response(payload)


class MonthlyTrendsAPIView(APIView):
    """
    GET /api/v1/hyperbdr-dashboard/trends/monthly/

    Returns monthly trend data for the last 12 months based on CollectionTask snapshots.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["hyperbdr-dashboard"],
        summary="HyperMotion / HyperBDR Dashboard Monthly Trends",
        description="Returns 12 months of tenant/license/host counts from CollectionTask snapshots.",
    )
    def get(self, request):
        _check_feature_permission(request.user)
        year_param = request.query_params.get("year", "all")
        year = None if year_param == "all" else (int(year_param) if year_param.isdigit() else None)
        payload = build_hyperbdr_dashboard_monthly_trends(year=year)
        return Response(payload)


class TenantsAPIView(APIView):
    """
    GET /api/v1/hyperbdr-dashboard/tenants/

    Returns the tenant operations table rows.
    Supports pagination via skip/limit query params.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["hyperbdr-dashboard"],
        summary="HyperMotion / HyperBDR Dashboard Tenants",
        description="Returns tenant table rows with pagination.",
    )
    def get(self, request):
        _check_feature_permission(request.user)
        all_tenants = build_hyperbdr_dashboard_tenants()
        total = len(all_tenants)
        skip = int(request.query_params.get("skip", 0))
        limit = int(request.query_params.get("limit", 100))
        return Response({
            "items": all_tenants[skip: skip + limit],
            "total": total,
            "skip": skip,
            "limit": limit,
        })
