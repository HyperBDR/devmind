from accounts.permissions import HasRequiredFeature
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from .serializers import (
    ComparisonItemSerializer,
    ModelItemSerializer,
    VendorItemSerializer,
)
from .services import ai_pricehub_service
from .tasks import enqueue_pricing_sync


class OverviewAPIView(APIView):
    permission_classes = [HasRequiredFeature]
    required_feature = "ai_pricehub"

    @extend_schema(
        tags=["ai-pricehub"],
        summary="Get AI pricing overview",
        description="Return vendors, primary models, and all synced pricing models.",
        responses={200: {"type": "object"}},
    )
    def get(self, request):
        payload = ai_pricehub_service.get_overview(
            platform_slug=request.query_params.get("platform_slug"),
        )
        VendorItemSerializer(payload["vendors"], many=True).data
        ModelItemSerializer(payload["primary_models"], many=True).data
        ModelItemSerializer(payload["models"], many=True).data
        return Response(payload)


class CompareAPIView(APIView):
    permission_classes = [HasRequiredFeature]
    required_feature = "ai_pricehub"

    @extend_schema(
        tags=["ai-pricehub"],
        summary="Compare AI model prices",
        description="Compare one primary model against matched vendor offerings.",
        responses={200: {"type": "object"}},
    )
    def get(self, request):
        primary_model_id = request.query_params.get("primary_model_id")
        payload = ai_pricehub_service.compare_models(
            int(primary_model_id) if primary_model_id else None,
            platform_slug=request.query_params.get("platform_slug"),
        )
        if payload is None:
            return Response({"detail": "No comparable models available."}, status=404)
        ModelItemSerializer(payload["primary_model"]).data
        ComparisonItemSerializer(payload["comparisons"], many=True).data
        return Response(payload)


class SyncAPIView(APIView):
    permission_classes = [HasRequiredFeature]
    required_feature = "ai_pricehub"

    @extend_schema(
        tags=["ai-pricehub"],
        summary="Sync vendor pricing",
        description="Fetch the latest pricing data from configured vendors.",
        responses={200: {"type": "object"}},
    )
    def post(self, request):
        platform_slug = request.data.get("platform_slug") or request.query_params.get("platform_slug")
        task_id = enqueue_pricing_sync(
            platform_slug=platform_slug,
            created_by=request.user if getattr(request.user, "is_authenticated", False) else None,
        )
        return Response(
            {
                "accepted": True,
                "task_id": task_id,
                "platform_slug": platform_slug or "",
                "message": "Pricing sync task queued.",
            },
            status=status.HTTP_202_ACCEPTED,
        )
