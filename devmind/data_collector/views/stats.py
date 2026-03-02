"""
Stats API for data_collector: counts by platform, trend, deleted count.
"""
from django.db.models import Count
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import RawDataRecord


class StatsAPIView(APIView):
    """
    GET: aggregate stats for current user (by platform, totals, deleted).
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["data-collector"],
        summary="Get collection stats",
        description="Counts by platform, total, deleted for current user.",
    )
    def get(self, request):
        user = request.user
        qs = RawDataRecord.objects.filter(user=user)
        by_platform = list(
            qs.values("platform")
            .annotate(count=Count("uuid"))
            .order_by("platform")
        )
        total = qs.count()
        deleted = qs.filter(is_deleted=True).count()
        return Response(
            {
                "by_platform": by_platform,
                "total": total,
                "deleted": deleted,
            }
        )
