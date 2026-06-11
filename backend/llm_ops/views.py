from decimal import Decimal

from accounts.permissions import HasRequiredFeature
from django.db import transaction
from django.db.models import Count, IntegerField, Q, Value
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .collection_services import (
    sync_official_provider_model_prices,
    sync_yunce_model_prices,
)
from .models import (
    ChannelModelPrice,
    ChannelModelPriceHistory,
    ChannelPriceItem,
    CollectedModelPriceHistory,
    CollectedModelPriceSnapshot,
    LLMModel,
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    PriceCollectionRun,
    PriceCollectionSource,
    ProcurementChannel,
    ResaleListing,
    ResaleListingExclusion,
    ResaleListingPriceHistory,
    ResalePlatform,
    UsageReconciliationRecord,
)
from .serializers import (
    ChannelModelPriceSerializer,
    ChannelModelPriceHistorySerializer,
    ChannelPriceItemSerializer,
    CollectedModelPriceHistorySerializer,
    CollectedModelPriceSnapshotSerializer,
    LLMModelSerializer,
    LLMProviderSerializer,
    ManualPriceImportRequestSerializer,
    MetaModelSerializer,
    ModelPriceItemSerializer,
    PriceCollectionRunSerializer,
    PriceCollectionSourceSerializer,
    ProcurementChannelSerializer,
    ResaleListingExclusionSerializer,
    ResaleListingSerializer,
    ResaleListingPriceHistorySerializer,
    ResalePlatformSerializer,
    UsageReconciliationRecordSerializer,
    YunceCollectionRequestSerializer,
)
from .services import (
    build_currency_conversion_context,
    calculate_usage_cost,
    convert_currency_amount,
    import_manual_model_prices,
    record_channel_model_price_history,
    record_resale_listing_price_history,
    resolve_channel_model_currency,
    resolve_channel_model_price,
    resolve_resale_listing_currency,
    sync_channel_price_items,
)


FEATURE_KEY = "llm_ops"
DEFAULT_INPUT_TOKENS = 10_000_000
DEFAULT_OUTPUT_TOKENS = 15_000_000
DISPLAY_PRICE_FIELDS = (
    "input_price_per_million",
    "output_price_per_million",
    "image_output_price_per_image",
    "audio_input_price_per_second",
    "audio_output_price_per_second",
    "video_input_price_per_second",
    "video_output_price_per_second",
    "estimated_cost",
)


class LLMOpsPermissionMixin:
    """Require access to the LLM operations app."""

    permission_classes = [HasRequiredFeature]
    required_feature = FEATURE_KEY


class PriceCollectionSourceViewSet(
    LLMOpsPermissionMixin,
    viewsets.ModelViewSet,
):
    """CRUD API for typed pricing sources."""

    serializer_class = PriceCollectionSourceSerializer

    def get_queryset(self):
        return PriceCollectionSource.objects.select_related(
            "provider",
            "channel",
        ).order_by("source_category", "provider__name", "channel__name", "id")

    @action(detail=True, methods=["post"], url_path="collect")
    def collect(self, request, pk=None):
        """Collect prices from a configured source."""
        source = self.get_object()
        if not source.is_enabled:
            return Response(
                {"detail": "Price collection source is disabled."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (
            source.source_category
            == PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            and source.provider_id
        ):
            try:
                stats = sync_official_provider_model_prices(
                    provider=source.provider,
                    source=source,
                    verify_source=True,
                )
            except ValueError as exc:
                return Response(
                    {"detail": str(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(stats, status=status.HTTP_200_OK)

        return Response(
            {
                "detail": (
                    "This source does not support direct collection yet. "
                    "Use manual import or a dedicated collector."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class PriceCollectionRunViewSet(
    LLMOpsPermissionMixin,
    viewsets.ReadOnlyModelViewSet,
):
    """Read-only API for pricing collection runs."""

    serializer_class = PriceCollectionRunSerializer

    def get_queryset(self):
        queryset = PriceCollectionRun.objects.select_related(
            "source",
            "source__provider",
        )
        source = self.request.query_params.get("source")
        if source:
            queryset = queryset.filter(source_id=source)
        return queryset.order_by("-started_at", "-id")


class CollectedModelPriceSnapshotViewSet(
    LLMOpsPermissionMixin,
    viewsets.ReadOnlyModelViewSet,
):
    """Read-only API for latest normalized collected price snapshots."""

    serializer_class = CollectedModelPriceSnapshotSerializer

    def get_queryset(self):
        queryset = CollectedModelPriceSnapshot.objects.select_related(
            "source",
            "provider",
            "model",
        )
        source = self.request.query_params.get("source")
        model_type = self.request.query_params.get("source_model_type")
        if source:
            queryset = queryset.filter(source_id=source)
        if model_type:
            queryset = queryset.filter(source_model_type=model_type)
        return queryset.order_by(
            "source_model_type",
            "source_provider_name",
            "source_model_name",
        )


class CollectedModelPriceHistoryViewSet(
    LLMOpsPermissionMixin,
    viewsets.ReadOnlyModelViewSet,
):
    """Read-only API for historical collected price versions."""

    serializer_class = CollectedModelPriceHistorySerializer

    def get_queryset(self):
        queryset = CollectedModelPriceHistory.objects.select_related(
            "source",
            "provider",
            "model",
            "run",
        )
        source = self.request.query_params.get("source")
        model = self.request.query_params.get("model")
        source_platform_id = self.request.query_params.get(
            "source_platform_id"
        )
        is_current = self.request.query_params.get("is_current")
        if source:
            queryset = queryset.filter(source_id=source)
        if model:
            queryset = queryset.filter(model_id=model)
        if source_platform_id:
            queryset = queryset.filter(source_platform_id=source_platform_id)
        if is_current in {"true", "false"}:
            queryset = queryset.filter(is_current=is_current == "true")
        return queryset.order_by("-effective_from", "-id")


class LLMProviderViewSet(LLMOpsPermissionMixin, viewsets.ModelViewSet):
    """CRUD API for original LLM providers."""

    serializer_class = LLMProviderSerializer

    def get_queryset(self):
        return LLMProvider.objects.annotate(
            model_count=Count("models"),
        ).order_by("name", "id")


class MetaModelViewSet(LLMOpsPermissionMixin, viewsets.ModelViewSet):
    """CRUD API for canonical model identities."""

    serializer_class = MetaModelSerializer

    def get_queryset(self):
        queryset = MetaModel.objects.select_related("vendor").annotate(
            provider_price_count=Count("provider_prices"),
        )
        vendor = self.request.query_params.get("vendor")
        if vendor:
            queryset = queryset.filter(vendor_id=vendor)
        return queryset.order_by("name", "id")


class LLMModelViewSet(LLMOpsPermissionMixin, viewsets.ModelViewSet):
    """CRUD API for model SKUs."""

    serializer_class = LLMModelSerializer

    def get_queryset(self):
        queryset = LLMModel.objects.select_related(
            "meta_model",
            "provider",
            "source",
        )
        provider = self.request.query_params.get("provider")
        meta_model = self.request.query_params.get("meta_model")
        if provider:
            queryset = queryset.filter(provider_id=provider)
        if meta_model:
            queryset = queryset.filter(meta_model_id=meta_model)
        return queryset.order_by("meta_model__name", "provider__name", "id")


class ModelPriceItemViewSet(
    LLMOpsPermissionMixin,
    viewsets.ModelViewSet,
):
    """CRUD API for normalized model price items."""

    serializer_class = ModelPriceItemSerializer

    def get_queryset(self):
        queryset = ModelPriceItem.objects.select_related(
            "meta_model",
            "provider",
            "model",
            "source",
        )
        provider = self.request.query_params.get("provider")
        meta_model = self.request.query_params.get("meta_model")
        model = self.request.query_params.get("model")
        source = self.request.query_params.get("source")
        dimension = self.request.query_params.get("dimension")
        is_current = self.request.query_params.get("is_current")
        if provider:
            queryset = queryset.filter(provider_id=provider)
        if meta_model:
            queryset = queryset.filter(meta_model_id=meta_model)
        if model:
            queryset = queryset.filter(model_id=model)
        if source:
            queryset = queryset.filter(source_id=source)
        if dimension:
            queryset = queryset.filter(dimension=dimension)
        if is_current in {"true", "false"}:
            queryset = queryset.filter(is_current=is_current == "true")
        return queryset.order_by(
            "provider__name",
            "model__name",
            "dimension",
            "tier_start",
            "id",
        )


class ProcurementChannelViewSet(
    LLMOpsPermissionMixin,
    viewsets.ModelViewSet,
):
    """CRUD API for procurement channels."""

    serializer_class = ProcurementChannelSerializer

    def get_queryset(self):
        total_model_count = LLMModel.objects.filter(is_active=True).count()
        return ProcurementChannel.objects.annotate(
            configured_model_count=Count("model_prices"),
            listed_model_count=Count(
                "model_prices",
                filter=Q(model_prices__is_listed=True),
            ),
            listed_provider_count=Count(
                "model_prices__model__provider",
                distinct=True,
                filter=Q(model_prices__is_listed=True),
            ),
            total_model_count=Value(
                total_model_count,
                output_field=IntegerField(),
            ),
        ).order_by("name", "id")


class ChannelModelPriceViewSet(
    LLMOpsPermissionMixin,
    viewsets.ModelViewSet,
):
    """CRUD API for channel model price overrides."""

    serializer_class = ChannelModelPriceSerializer

    def get_queryset(self):
        queryset = ChannelModelPrice.objects.select_related(
            "channel",
            "meta_model",
            "model",
            "model__provider",
            "price_source",
        )
        channel = self.request.query_params.get("channel")
        meta_model = self.request.query_params.get("meta_model")
        model = self.request.query_params.get("model")
        if channel:
            queryset = queryset.filter(channel_id=channel)
        if meta_model:
            queryset = queryset.filter(meta_model_id=meta_model)
        if model:
            queryset = queryset.filter(model_id=model)
        return queryset.order_by("channel__name", "model__name", "id")

    def perform_create(self, serializer):
        price = serializer.save()
        record_channel_model_price_history(price)
        sync_channel_price_items(price)

    def perform_update(self, serializer):
        price = serializer.save()
        record_channel_model_price_history(price)
        sync_channel_price_items(price)

    @action(detail=False, methods=["post"], url_path="bulk-upsert")
    def bulk_upsert(self, request):
        """Create or update channel model prices in bulk."""

        items = request.data.get("items", [])
        if not isinstance(items, list):
            return Response(
                {"detail": "items must be a list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        prices = []
        with transaction.atomic():
            for item in items:
                existing = ChannelModelPrice.objects.filter(
                    channel_id=item.get("channel"),
                    model_id=item.get("model"),
                ).first()
                serializer = self.get_serializer(
                    existing,
                    data=item,
                    partial=existing is not None,
                )
                serializer.is_valid(raise_exception=True)
                data = serializer.validated_data
                lookup = {
                    "channel": data["channel"],
                    "model": data["model"],
                }
                defaults = {
                    key: value
                    for key, value in data.items()
                    if key not in {"channel", "model"}
                }
                defaults["meta_model"] = data["model"].meta_model
                price, _ = ChannelModelPrice.objects.update_or_create(
                    **lookup,
                    defaults=defaults,
                )
                record_channel_model_price_history(price)
                sync_channel_price_items(price)
                prices.append(price)

        output = self.get_serializer(prices, many=True)
        return Response(output.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="sync-price-items")
    def sync_price_items(self, request):
        """Sync normalized channel price items for configured models."""
        queryset = self.get_queryset().filter(is_listed=True)
        channel_id = request.data.get("channel")
        model_id = request.data.get("model")
        if channel_id:
            queryset = queryset.filter(channel_id=channel_id)
        if model_id:
            queryset = queryset.filter(model_id=model_id)

        synced_count = 0
        model_count = 0
        with transaction.atomic():
            for price in queryset:
                synced_count += len(sync_channel_price_items(price))
                model_count += 1

        return Response(
            {
                "models": model_count,
                "price_items": synced_count,
            },
            status=status.HTTP_200_OK,
        )


class ChannelModelPriceHistoryViewSet(
    LLMOpsPermissionMixin,
    viewsets.ReadOnlyModelViewSet,
):
    """Read-only API for historical channel/model price versions."""

    serializer_class = ChannelModelPriceHistorySerializer

    def get_queryset(self):
        queryset = ChannelModelPriceHistory.objects.select_related(
            "channel",
            "meta_model",
            "model",
            "model__provider",
        )
        channel = self.request.query_params.get("channel")
        meta_model = self.request.query_params.get("meta_model")
        model = self.request.query_params.get("model")
        is_current = self.request.query_params.get("is_current")
        if channel:
            queryset = queryset.filter(channel_id=channel)
        if meta_model:
            queryset = queryset.filter(meta_model_id=meta_model)
        if model:
            queryset = queryset.filter(model_id=model)
        if is_current in {"true", "false"}:
            queryset = queryset.filter(is_current=is_current == "true")
        return queryset.order_by("-effective_from", "-id")


class ChannelPriceItemViewSet(
    LLMOpsPermissionMixin,
    viewsets.ModelViewSet,
):
    """CRUD API for normalized channel price items."""

    serializer_class = ChannelPriceItemSerializer

    def get_queryset(self):
        queryset = ChannelPriceItem.objects.select_related(
            "channel",
            "meta_model",
            "model",
            "model__provider",
            "base_price_item",
            "source",
        )
        channel = self.request.query_params.get("channel")
        meta_model = self.request.query_params.get("meta_model")
        model = self.request.query_params.get("model")
        dimension = self.request.query_params.get("dimension")
        is_current = self.request.query_params.get("is_current")
        if channel:
            queryset = queryset.filter(channel_id=channel)
        if meta_model:
            queryset = queryset.filter(meta_model_id=meta_model)
        if model:
            queryset = queryset.filter(model_id=model)
        if dimension:
            queryset = queryset.filter(dimension=dimension)
        if is_current in {"true", "false"}:
            queryset = queryset.filter(is_current=is_current == "true")
        return queryset.order_by(
            "channel__name",
            "model__name",
            "dimension",
            "tier_start",
            "id",
        )


class ResalePlatformViewSet(LLMOpsPermissionMixin, viewsets.ModelViewSet):
    """CRUD API for downstream resale platforms."""

    serializer_class = ResalePlatformSerializer

    def get_queryset(self):
        return ResalePlatform.objects.annotate(
            listing_count=Count("listings"),
        ).order_by("name", "id")


class ResaleListingViewSet(LLMOpsPermissionMixin, viewsets.ModelViewSet):
    """CRUD API for downstream resale listings."""

    serializer_class = ResaleListingSerializer

    def get_queryset(self):
        queryset = ResaleListing.objects.select_related(
            "platform",
            "meta_model",
            "model",
            "channel",
        )
        platform = self.request.query_params.get("platform")
        meta_model = self.request.query_params.get("meta_model")
        model = self.request.query_params.get("model")
        if platform:
            queryset = queryset.filter(platform_id=platform)
        if meta_model:
            queryset = queryset.filter(meta_model_id=meta_model)
        if model:
            queryset = queryset.filter(model_id=model)
        return queryset.order_by("platform__name", "model__name", "id")

    def perform_create(self, serializer):
        listing = serializer.save()
        record_resale_listing_price_history(listing)

    def perform_update(self, serializer):
        listing = serializer.save()
        record_resale_listing_price_history(listing)

    @action(detail=False, methods=["post"], url_path="bulk-upsert")
    def bulk_upsert(self, request):
        """Create or update resale listings in bulk."""

        items = request.data.get("items", [])
        if not isinstance(items, list):
            return Response(
                {"detail": "items must be a list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        listings = []
        with transaction.atomic():
            for item in items:
                channel_id = item.get("channel") or None
                existing = ResaleListing.objects.filter(
                    platform_id=item.get("platform"),
                    model_id=item.get("model"),
                    channel_id=channel_id,
                ).first()
                serializer = self.get_serializer(
                    existing,
                    data=item,
                    partial=existing is not None,
                )
                serializer.is_valid(raise_exception=True)
                data = serializer.validated_data
                lookup = {
                    "platform": data["platform"],
                    "model": data["model"],
                    "channel": data.get("channel"),
                }
                defaults = {
                    key: value
                    for key, value in data.items()
                    if key not in {"platform", "model", "channel"}
                }
                defaults["meta_model"] = data["model"].meta_model
                listing, _ = ResaleListing.objects.update_or_create(
                    **lookup,
                    defaults=defaults,
                )
                ResaleListingExclusion.objects.filter(
                    platform=data["platform"],
                    model=data["model"],
                ).delete()
                record_resale_listing_price_history(listing)
                listings.append(listing)

        output = self.get_serializer(listings, many=True)
        return Response(output.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="bulk-replace")
    def bulk_replace(self, request):
        """Replace active listings for platform/model pairs in bulk."""

        items = request.data.get("items", [])
        if not isinstance(items, list):
            return Response(
                {"detail": "items must be a list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        listings = []
        with transaction.atomic():
            for item in items:
                channel_id = item.get("channel") or None
                existing = ResaleListing.objects.filter(
                    platform_id=item.get("platform"),
                    model_id=item.get("model"),
                    channel_id=channel_id,
                ).first()
                serializer = self.get_serializer(
                    existing,
                    data=item,
                    partial=existing is not None,
                )
                serializer.is_valid(raise_exception=True)
                data = serializer.validated_data
                active_listings = list(
                    ResaleListing.objects.filter(
                        platform=data["platform"],
                        model=data["model"],
                        is_active=True,
                    )
                )
                ResaleListing.objects.filter(
                    platform=data["platform"],
                    model=data["model"],
                    is_active=True,
                ).update(is_active=False)
                for active_listing in active_listings:
                    active_listing.is_active = False
                    record_resale_listing_price_history(active_listing)
                lookup = {
                    "platform": data["platform"],
                    "model": data["model"],
                    "channel": data.get("channel"),
                }
                defaults = {
                    key: value
                    for key, value in data.items()
                    if key not in {"platform", "model", "channel"}
                }
                defaults["meta_model"] = data["model"].meta_model
                listing, _ = ResaleListing.objects.update_or_create(
                    **lookup,
                    defaults=defaults,
                )
                ResaleListingExclusion.objects.filter(
                    platform=data["platform"],
                    model=data["model"],
                ).delete()
                record_resale_listing_price_history(listing)
                listings.append(listing)

        output = self.get_serializer(listings, many=True)
        return Response(output.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="bulk-offline")
    def bulk_offline(self, request):
        """Deactivate active resale listings for selected platform/models."""

        platform_id = request.data.get("platform")
        model_ids = request.data.get("models", [])
        if not platform_id:
            return Response(
                {"detail": "platform is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(model_ids, list) or not model_ids:
            return Response(
                {"detail": "models must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            listings = list(
                ResaleListing.objects.filter(
                    platform_id=platform_id,
                    model_id__in=model_ids,
                    is_active=True,
                )
            )
            ResaleListing.objects.filter(
                platform_id=platform_id,
                model_id__in=model_ids,
                is_active=True,
            ).update(is_active=False)
            for listing in listings:
                listing.is_active = False
                record_resale_listing_price_history(listing)

        output = self.get_serializer(listings, many=True)
        return Response(output.data, status=status.HTTP_200_OK)


class ResaleListingExclusionViewSet(
    LLMOpsPermissionMixin,
    viewsets.ModelViewSet,
):
    """CRUD API for models removed from resale platform workbench lists."""

    serializer_class = ResaleListingExclusionSerializer

    def get_queryset(self):
        queryset = ResaleListingExclusion.objects.select_related(
            "platform",
            "meta_model",
            "model",
        )
        platform = self.request.query_params.get("platform")
        meta_model = self.request.query_params.get("meta_model")
        model = self.request.query_params.get("model")
        if platform:
            queryset = queryset.filter(platform_id=platform)
        if meta_model:
            queryset = queryset.filter(meta_model_id=meta_model)
        if model:
            queryset = queryset.filter(model_id=model)
        return queryset.order_by("platform__name", "model__name", "id")

    @action(detail=False, methods=["post"], url_path="bulk-upsert")
    def bulk_upsert(self, request):
        """Remove selected models from a resale platform workbench."""

        platform_id = request.data.get("platform")
        model_ids = request.data.get("models", [])
        if not platform_id:
            return Response(
                {"detail": "platform is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(model_ids, list) or not model_ids:
            return Response(
                {"detail": "models must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        exclusions = []
        with transaction.atomic():
            for model_id in model_ids:
                model = LLMModel.objects.get(id=model_id)
                exclusion, _ = ResaleListingExclusion.objects.update_or_create(
                    platform_id=platform_id,
                    model_id=model_id,
                    defaults={
                        "meta_model": model.meta_model,
                        "reason": request.data.get("reason", ""),
                    },
                )
                exclusions.append(exclusion)

        output = self.get_serializer(exclusions, many=True)
        return Response(output.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="bulk-restore")
    def bulk_restore(self, request):
        """Restore selected models to a resale platform workbench."""

        platform_id = request.data.get("platform")
        model_ids = request.data.get("models", [])
        if not platform_id:
            return Response(
                {"detail": "platform is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(model_ids, list) or not model_ids:
            return Response(
                {"detail": "models must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deleted_count, _ = ResaleListingExclusion.objects.filter(
            platform_id=platform_id,
            model_id__in=model_ids,
        ).delete()
        return Response(
            {"deleted_count": deleted_count},
            status=status.HTTP_200_OK,
        )


class ResaleListingPriceHistoryViewSet(
    LLMOpsPermissionMixin,
    viewsets.ReadOnlyModelViewSet,
):
    """Read-only API for historical downstream listing price versions."""

    serializer_class = ResaleListingPriceHistorySerializer

    def get_queryset(self):
        queryset = ResaleListingPriceHistory.objects.select_related(
            "platform",
            "model",
            "model__provider",
            "channel",
        )
        platform = self.request.query_params.get("platform")
        model = self.request.query_params.get("model")
        is_current = self.request.query_params.get("is_current")
        if platform:
            queryset = queryset.filter(platform_id=platform)
        if model:
            queryset = queryset.filter(model_id=model)
        if is_current in {"true", "false"}:
            queryset = queryset.filter(is_current=is_current == "true")
        return queryset.order_by("-effective_from", "-id")


class UsageReconciliationRecordViewSet(
    LLMOpsPermissionMixin,
    viewsets.ModelViewSet,
):
    """CRUD API for reconciliation records."""

    serializer_class = UsageReconciliationRecordSerializer

    def get_queryset(self):
        queryset = UsageReconciliationRecord.objects.select_related(
            "channel",
            "model",
            "model__provider",
        )
        channel = self.request.query_params.get("channel")
        model = self.request.query_params.get("model")
        if channel:
            queryset = queryset.filter(channel_id=channel)
        if model:
            queryset = queryset.filter(model_id=model)
        return queryset.order_by("-date", "-id")


def _as_float(value) -> float:
    return float(value or Decimal("0"))


def _converted_amount(value, source_currency: str, currency_context):
    return convert_currency_amount(value, source_currency, currency_context)


def _apply_display_currency(row: dict, source_currency: str, currency_context):
    row["original_currency"] = source_currency
    row["display_currency"] = currency_context.display_currency
    row["exchange_rate"] = _as_float(currency_context.usd_to_cny_rate)
    missing_conversion = False
    for field in DISPLAY_PRICE_FIELDS:
        if field not in row:
            continue
        original_value = row[field]
        row[f"original_{field}"] = original_value
        converted_value = _converted_amount(
            original_value,
            source_currency,
            currency_context,
        )
        if converted_value is None:
            missing_conversion = True
            continue
        row[field] = _as_float(converted_value)
    row["currency"] = (
        row["display_currency"] if not missing_conversion else source_currency
    )
    row["requires_currency_conversion"] = missing_conversion
    return row


def _exchange_rate_payload(currency_context):
    return {
        "display_currency": currency_context.display_currency,
        "usd_to_cny_rate": _as_float(currency_context.usd_to_cny_rate),
        "rate_source_label": currency_context.rate_source_label,
        "rate_source_url": currency_context.rate_source_url,
        "rate_collected_at": currency_context.rate_collected_at,
    }


def _selected_resale_platform(value: str | None):
    """Resolve selected resale platform by id or code."""
    queryset = ResalePlatform.objects.filter(is_active=True).order_by(
        "name",
        "id",
    )
    if value:
        if str(value).isdigit():
            selected = queryset.filter(id=value).first()
            if selected:
                return selected
        selected = queryset.filter(code=value).first()
        if selected:
            return selected
    return (
        queryset.filter(code="agione").first()
        or queryset.filter(platform_type=ResalePlatform.PLATFORM_TYPE_AGIONE)
        .first()
        or queryset.first()
    )


def _point_conversion_payload(platform: ResalePlatform | None):
    """Return fixed point conversion settings for a resale platform."""
    if platform is None:
        return None
    return {
        "platform_id": platform.id,
        "platform_name": platform.name,
        "point_name": platform.point_name,
        "points_per_currency_unit": _as_float(
            platform.points_per_currency_unit
        ),
        "rounding_mode": platform.point_rounding_mode,
        "currency": platform.currency,
        "formula_label": (
            f"1 {platform.currency} = "
            f"{platform.points_per_currency_unit} {platform.point_name}"
        ),
    }


def _gross_margin(retail: Decimal, cost: Decimal, fee_rate: Decimal) -> dict:
    net = retail * (Decimal("1") - fee_rate)
    margin = net - cost
    margin_rate = Decimal("0")
    if net:
        margin_rate = margin / net * Decimal("100")
    return {
        "net_revenue": _as_float(net),
        "gross_margin": _as_float(margin),
        "gross_margin_rate": _as_float(margin_rate),
        "requires_currency_conversion": False,
    }


def _empty_margin(*, requires_currency_conversion: bool) -> dict:
    return {
        "net_revenue": None,
        "gross_margin": None,
        "gross_margin_rate": None,
        "requires_currency_conversion": requires_currency_conversion,
    }


def _select_best_option(options: list[dict]):
    comparable_options = [
        item
        for item in options
        if not item.get("requires_currency_conversion")
    ]
    if len(comparable_options) != len(options):
        return None
    return sorted(
        comparable_options,
        key=lambda item: item["estimated_cost"],
    )[0]


def _listing_option(
    listing: ResaleListing,
    options: list[dict],
    best_option=None,
):
    if listing.channel_id is None:
        return best_option
    return next(
        (
            option
            for option in options
            if option["channel_id"] == listing.channel_id
        ),
        None,
    )


def _listing_price_gap(active_option, lowest_option) -> float | None:
    if not active_option or not lowest_option:
        return None
    gap = active_option["estimated_cost"] - lowest_option["estimated_cost"]
    return max(gap, 0)


def _diagnostic_status(
    *,
    best_channel,
    coverage_count: int,
    is_agione_listed: bool,
    has_lowest_listing: bool,
    requires_currency_conversion: bool = False,
) -> dict:
    if requires_currency_conversion:
        return {
            "status": "currency_mismatch",
            "status_label": "需要汇率",
            "status_priority": 1,
        }
    if not best_channel:
        return {
            "status": "missing_channel",
            "status_label": "缺少渠道价",
            "status_priority": 1,
        }
    if not is_agione_listed:
        return {
            "status": "unlisted",
            "status_label": "未上架",
            "status_priority": 2,
        }
    if not has_lowest_listing:
        return {
            "status": "not_lowest",
            "status_label": "非最低价",
            "status_priority": 3,
        }
    if coverage_count <= 1:
        return {
            "status": "low_coverage",
            "status_label": "覆盖偏少",
            "status_priority": 4,
        }
    return {
        "status": "ready",
        "status_label": "就绪",
        "status_priority": 5,
    }


class SummaryAPIView(LLMOpsPermissionMixin, APIView):
    """Return dashboard metrics and calculation summaries."""

    @extend_schema(
        tags=["llm-ops"],
        summary="Get LLM operations summary",
        responses={200: {"type": "object"}},
    )
    def get(self, request):
        input_tokens = int(
            request.query_params.get("input_tokens") or DEFAULT_INPUT_TOKENS
        )
        output_tokens = int(
            request.query_params.get("output_tokens") or DEFAULT_OUTPUT_TOKENS
        )
        video_resolution = request.query_params.get("video_resolution") or ""
        display_currency = (
            request.query_params.get("display_currency") or "CNY"
        )
        selected_platform_param = (
            request.query_params.get("resale_platform") or ""
        )
        currency_context = build_currency_conversion_context(display_currency)
        selected_platform = _selected_resale_platform(selected_platform_param)

        models = list(
            LLMModel.objects.filter(is_active=True)
            .select_related("provider")
            .order_by("provider__name", "name", "id")
        )
        channels = list(
            ProcurementChannel.objects.filter(is_active=True).order_by(
                "name",
                "id",
            )
        )
        overrides = {
            (item.channel_id, item.model_id): item
            for item in ChannelModelPrice.objects.select_related(
                "channel",
                "model",
            )
        }

        procurement_rows = []
        for model in models:
            options = []
            for channel in channels:
                override = overrides.get((channel.id, model.id))
                if not override or not override.is_listed:
                    continue
                unit_prices = resolve_channel_model_price(
                    channel,
                    model,
                    override=override,
                    video_resolution=video_resolution,
                )
                currency = resolve_channel_model_currency(
                    channel,
                    model,
                    override=override,
                )
                estimated_cost = calculate_usage_cost(
                    unit_prices,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
                option = {
                    "channel_id": channel.id,
                    "channel_name": channel.name,
                    "currency": currency,
                    "input_price_per_million": _as_float(
                        unit_prices.input_per_million
                    ),
                    "output_price_per_million": _as_float(
                        unit_prices.output_per_million
                    ),
                    "image_output_price_per_image": _as_float(
                        unit_prices.image_output_per_image
                    ),
                    "audio_input_price_per_second": _as_float(
                        unit_prices.audio_input_per_second
                    ),
                    "audio_output_price_per_second": _as_float(
                        unit_prices.audio_output_per_second
                    ),
                    "video_input_price_per_second": _as_float(
                        unit_prices.video_input_per_second
                    ),
                    "video_output_price_per_second": _as_float(
                        unit_prices.video_output_per_second
                    ),
                    "estimated_cost": _as_float(estimated_cost),
                }
                options.append(
                    _apply_display_currency(
                        option,
                        currency,
                        currency_context,
                    )
                )

            options.sort(
                key=lambda item: (
                    item.get("requires_currency_conversion", False),
                    item["estimated_cost"],
                )
            )
            requires_currency_conversion = any(
                item.get("requires_currency_conversion")
                for item in options
            )
            best = _select_best_option(options) if options else None
            procurement_rows.append(
                {
                    "model_id": model.id,
                    "model_name": model.name,
                    "model_code": model.code,
                    "provider_name": model.provider.name,
                    "currency": model.currency,
                    "requires_currency_conversion": (
                        requires_currency_conversion
                    ),
                    "best_channel": best,
                    "options": options,
                }
            )

        listing_rows = []
        active_listings = list(
            ResaleListing.objects.filter(is_active=True).select_related(
                "platform",
                "model",
                "model__provider",
                "channel",
            )
        )
        valid_active_listings = []
        for listing in active_listings:
            channel = listing.channel
            row = next(
                (
                    procurement_row
                    for procurement_row in procurement_rows
                    if procurement_row["model_id"] == listing.model_id
                ),
                None,
            )
            options = row["options"] if row else []
            if channel is None:
                best_row = row["best_channel"] if row else None
                if not best_row:
                    continue
                cost_input = Decimal(
                    str(best_row["original_input_price_per_million"])
                )
                cost_output = Decimal(
                    str(best_row["original_output_price_per_million"])
                )
                cost_currency = (
                    best_row.get("original_currency") or listing.model.currency
                )
            else:
                override = overrides.get((channel.id, listing.model_id))
                if (
                    not channel.is_active
                    or override is None
                    or not override.is_listed
                ):
                    continue
                unit_prices = resolve_channel_model_price(
                    channel,
                    listing.model,
                    override=override,
                    video_resolution=video_resolution,
                )
                cost_input = unit_prices.input_per_million
                cost_output = unit_prices.output_per_million
                cost_currency = resolve_channel_model_currency(
                    channel,
                    listing.model,
                    override=override,
                )
            valid_active_listings.append(listing)

            retail_input = listing.retail_input_price_per_million
            retail_output = listing.retail_output_price_per_million
            retail_currency = resolve_resale_listing_currency(listing)
            fee_rate = listing.platform.fee_rate or Decimal("0")
            cost_input_display = _converted_amount(
                cost_input,
                cost_currency,
                currency_context,
            )
            cost_output_display = _converted_amount(
                cost_output,
                cost_currency,
                currency_context,
            )
            retail_input_display = _converted_amount(
                retail_input,
                retail_currency,
                currency_context,
            )
            retail_output_display = _converted_amount(
                retail_output,
                retail_currency,
                currency_context,
            )
            requires_currency_conversion = any(
                value is None
                for value in (
                    cost_input_display,
                    cost_output_display,
                    retail_input_display,
                    retail_output_display,
                )
            )
            if requires_currency_conversion:
                input_margin = _empty_margin(
                    requires_currency_conversion=True,
                )
                output_margin = _empty_margin(
                    requires_currency_conversion=True,
                )
            else:
                input_margin = _gross_margin(
                    retail_input_display,
                    cost_input_display,
                    fee_rate,
                )
                output_margin = _gross_margin(
                    retail_output_display,
                    cost_output_display,
                    fee_rate,
                )
            listing_rows.append(
                {
                    "listing_id": listing.id,
                    "platform_id": listing.platform_id,
                    "platform_name": listing.platform.name,
                    "model_id": listing.model_id,
                    "model_name": listing.model.name,
                    "model_code": listing.model.code,
                    "channel_id": listing.channel_id,
                    "channel_name": (
                        channel.name if channel else "自动最优"
                    ),
                    "currency": (
                        currency_context.display_currency
                        if not requires_currency_conversion
                        else retail_currency
                    ),
                    "display_currency": currency_context.display_currency,
                    "exchange_rate": _as_float(
                        currency_context.usd_to_cny_rate
                    ),
                    "original_currency": retail_currency,
                    "retail_currency": retail_currency,
                    "cost_currency": cost_currency,
                    "requires_currency_conversion": (
                        requires_currency_conversion
                    ),
                    "retail_input_price_per_million": _as_float(
                        retail_input_display
                        if retail_input_display is not None
                        else retail_input
                    ),
                    "retail_output_price_per_million": _as_float(
                        retail_output_display
                        if retail_output_display is not None
                        else retail_output
                    ),
                    "original_retail_input_price_per_million": (
                        _as_float(retail_input)
                    ),
                    "original_retail_output_price_per_million": (
                        _as_float(retail_output)
                    ),
                    "cost_input_price_per_million": _as_float(
                        cost_input_display
                        if cost_input_display is not None
                        else cost_input
                    ),
                    "cost_output_price_per_million": _as_float(
                        cost_output_display
                        if cost_output_display is not None
                        else cost_output
                    ),
                    "original_cost_input_price_per_million": (
                        _as_float(cost_input)
                    ),
                    "original_cost_output_price_per_million": (
                        _as_float(cost_output)
                    ),
                    "input_margin": input_margin,
                    "output_margin": output_margin,
                    "option": _listing_option(
                        listing,
                        options,
                        row["best_channel"] if row else None,
                    ),
                }
            )

        selected_platform_listing_rows = [
            listing
            for listing in valid_active_listings
            if (
                selected_platform
                and listing.platform_id == selected_platform.id
            )
        ]
        selected_platform_listings_by_model = {}
        for listing in selected_platform_listing_rows:
            selected_platform_listings_by_model.setdefault(
                listing.model_id,
                [],
            ).append(listing)

        diagnostics = []
        for row in procurement_rows:
            options = row["options"]
            best_channel = row["best_channel"]
            active_model_listings = selected_platform_listings_by_model.get(
                row["model_id"],
                [],
            )
            active_options = [
                _listing_option(listing, options, best_channel)
                for listing in active_model_listings
            ]
            active_options = [option for option in active_options if option]
            has_lowest_listing = any(
                best_channel
                and option["channel_id"] == best_channel["channel_id"]
                for option in active_options
            )
            cheapest_active = (
                sorted(
                    active_options,
                    key=lambda option: option["estimated_cost"],
                )[0]
                if active_options
                else None
            )
            status_payload = _diagnostic_status(
                best_channel=best_channel,
                coverage_count=len(options),
                is_agione_listed=bool(active_model_listings),
                has_lowest_listing=has_lowest_listing,
                requires_currency_conversion=row[
                    "requires_currency_conversion"
                ],
            )
            diagnostics.append(
                {
                    **row,
                    "coverage_count": len(options),
                    "is_agione_listed": bool(active_model_listings),
                    "has_lowest_listing": has_lowest_listing,
                    "active_listing_count": len(active_model_listings),
                    "price_gap": _listing_price_gap(
                        cheapest_active,
                        best_channel,
                    ),
                    **status_payload,
                }
            )

        diagnostic_counts = {
            "currency_mismatch": 0,
            "missing_channel": 0,
            "unlisted": 0,
            "not_lowest": 0,
            "low_coverage": 0,
            "ready": 0,
        }
        for row in diagnostics:
            diagnostic_counts[row["status"]] += 1
        total_models = len(models)
        ready_count = diagnostic_counts["ready"]
        agione_listed_model_count = len(
            {listing.model_id for listing in selected_platform_listing_rows}
        )

        status_counts = {
            item["status"]: item["count"]
            for item in UsageReconciliationRecord.objects.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        }
        return Response(
            {
                "kpis": {
                    "providers": LLMProvider.objects.count(),
                    "models": LLMModel.objects.count(),
                    "channels": ProcurementChannel.objects.count(),
                    "listings": ResaleListing.objects.count(),
                    "active_models": total_models,
                    "agione_listed_models": agione_listed_model_count,
                    "ready_models": ready_count,
                    "reconciliation_anomalies": (
                        UsageReconciliationRecord.objects.exclude(
                            status=UsageReconciliationRecord.STATUS_PERFECT
                        ).count()
                    ),
                },
                "status_counts": status_counts,
                "simulation": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "video_resolution": video_resolution,
                    "display_currency": currency_context.display_currency,
                },
                "currency": _exchange_rate_payload(currency_context),
                "point_conversion": _point_conversion_payload(
                    selected_platform,
                ),
                "procurement": procurement_rows,
                "listings": listing_rows,
                "agione": {
                    "platform_id": (
                        selected_platform.id if selected_platform else None
                    ),
                    "platform_name": (
                        selected_platform.name if selected_platform else ""
                    ),
                    "diagnostics": diagnostics,
                    "diagnostic_counts": diagnostic_counts,
                },
            }
        )


class YunceCollectionAPIView(LLMOpsPermissionMixin, APIView):
    """Collect basic Yunce model pricing and persist text model prices."""

    @extend_schema(
        tags=["llm-ops"],
        summary="Collect Yunce model pricing",
        request=YunceCollectionRequestSerializer,
        responses={200: {"type": "object"}},
    )
    def post(self, request):
        serializer = YunceCollectionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            kwargs = {
                "username": data["username"],
                "password": data["password"],
            }
            if data.get("source"):
                kwargs["source"] = data["source"]
            if data.get("base_url"):
                kwargs["base_url"] = data["base_url"]
            result = sync_yunce_model_prices(**kwargs)
        except Exception as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result)


class ManualPriceImportAPIView(LLMOpsPermissionMixin, APIView):
    """Import manually maintained model prices from table-like data."""

    @extend_schema(
        tags=["llm-ops"],
        summary="Import manual model pricing table",
        request=ManualPriceImportRequestSerializer,
        responses={200: {"type": "object"}},
    )
    def post(self, request):
        serializer = ManualPriceImportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        provider = data["provider"]
        source = data.get("source")
        if source is None:
            source_slug = data.get("source_slug") or slugify(
                f"{provider.code}-{data['source_name']}",
            )
            if not source_slug:
                source_slug = f"{provider.code}-manual"
            source, _ = PriceCollectionSource.objects.update_or_create(
                slug=source_slug,
                defaults={
                    "name": data["source_name"],
                    "provider": provider,
                    "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
                    "source_category": (
                        PriceCollectionSource.SOURCE_CATEGORY_MANUAL
                    ),
                    "endpoint_url": data.get("source_url") or "",
                    "currency": data["currency"],
                    "is_enabled": True,
                    "updates_model_prices": data["updates_model_prices"],
                },
            )
        result = import_manual_model_prices(
            source=source,
            provider=provider,
            rows=data["rows"],
            default_currency=data["currency"],
            updates_model_prices=data["updates_model_prices"],
        )
        return Response(result)
