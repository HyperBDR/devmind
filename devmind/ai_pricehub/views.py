from accounts.permissions import HasRequiredFeature
from django.db.utils import OperationalError, ProgrammingError
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from .llm_config import get_llm_config_reference
from .serializers import (
    ComparisonItemSerializer,
    ModelItemSerializer,
    PriceSourceConfigSerializer,
    VendorItemSerializer,
)
from .services import (
    ai_pricehub_service,
    create_primary_source_config,
    get_primary_source_config,
    list_primary_source_configs,
    sync_primary_source_configs_to_collector,
    update_primary_source_config,
)
from .tasks import enqueue_pricing_sync


def serialize_primary_source_config(config):
    parser_llm = get_llm_config_reference(
        str(config.get("parser_llm_config_uuid") or "")
    )
    return {
        "id": config["id"],
        "vendor_slug": config["vendor_slug"],
        "platform_slug": config["platform_slug"],
        "vendor_name": config["vendor_name"],
        "region": config["region"],
        "endpoint_url": config["endpoint_url"],
        "parser_llm_config_uuid": parser_llm["uuid"],
        "parser_llm_config_label": parser_llm["label"],
        "currency": config["currency"],
        "points_per_currency_unit": config["points_per_currency_unit"],
        "is_enabled": config["is_enabled"],
        "notes": config["notes"],
        "updated_at": config.get("updated_at"),
    }


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


class PrimarySourceConfigAPIView(APIView):
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_console"

    @extend_schema(
        tags=["ai-pricehub"],
        summary="Get primary pricing source config",
        description="Return editable AGIOne configuration used by model pricing sync.",
        responses={200: {"type": "object"}},
    )
    def get(self, request):
        try:
            source_configs = sync_primary_source_configs_to_collector(
                owner_user=request.user,
            )
        except (OperationalError, ProgrammingError):
            source_configs = list_primary_source_configs()
        payload = [serialize_primary_source_config(config) for config in source_configs]
        PriceSourceConfigSerializer(payload, many=True).data
        return Response(payload)

    @extend_schema(
        tags=["ai-pricehub"],
        summary="Create primary pricing source config",
        description="Create a new editable AGIOne platform configuration used by model pricing sync.",
        responses={200: {"type": "object"}},
    )
    def post(self, request):
        serializer = PriceSourceConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            config = create_primary_source_config(
                serializer.validated_data,
                owner_user=request.user,
            )
        except (OperationalError, ProgrammingError):
            return Response(
                {
                    "detail": (
                        "AI Price Hub config table is not available yet. "
                        "Please run database migrations first."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(serialize_primary_source_config(config), status=status.HTTP_201_CREATED)


class PrimarySourceConfigDetailAPIView(APIView):
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_console"

    @extend_schema(
        tags=["ai-pricehub"],
        summary="Update primary pricing source config",
        description="Update editable AGIOne configuration used by model pricing sync.",
        responses={200: {"type": "object"}},
    )
    def patch(self, request, config_id: int):
        config = get_primary_source_config(config_id)
        if config is None:
            return Response(
                {
                    "detail": (
                        "Primary pricing source config is not available yet. "
                        "Please run database migrations first."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = PriceSourceConfigSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            updated = update_primary_source_config(
                config_id,
                serializer.validated_data,
                owner_user=request.user,
            )
        except (OperationalError, ProgrammingError):
            return Response(
                {
                    "detail": (
                        "AI Price Hub config table is not available yet. "
                        "Please run database migrations first."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if updated is None:
            return Response(
                {
                    "detail": (
                        "Primary pricing source config is not available yet. "
                        "Please run database migrations first."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(serialize_primary_source_config(updated))
