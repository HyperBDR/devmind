from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ChannelModelPriceHistoryViewSet,
    ChannelModelPriceViewSet,
    ChannelPriceItemViewSet,
    CollectedModelPriceHistoryViewSet,
    CollectedModelPriceSnapshotViewSet,
    LLMModelViewSet,
    LLMProviderViewSet,
    ManualPriceImportAPIView,
    MetaModelViewSet,
    ModelPriceItemViewSet,
    PriceCollectionRunViewSet,
    PriceCollectionSourceViewSet,
    ProcurementChannelViewSet,
    ResaleListingExclusionViewSet,
    ResaleListingPriceHistoryViewSet,
    ResaleListingViewSet,
    ResalePlatformViewSet,
    SummaryAPIView,
    UsageReconciliationRecordViewSet,
    YunceCollectionAPIView,
)

router = DefaultRouter()
router.register(
    r"collection-sources",
    PriceCollectionSourceViewSet,
    basename="collection-source",
)
router.register(
    r"collection-runs",
    PriceCollectionRunViewSet,
    basename="collection-run",
)
router.register(
    r"collected-price-snapshots",
    CollectedModelPriceSnapshotViewSet,
    basename="collected-price-snapshot",
)
router.register(
    r"collected-price-history",
    CollectedModelPriceHistoryViewSet,
    basename="collected-price-history",
)
router.register(r"providers", LLMProviderViewSet, basename="provider")
router.register(r"meta-models", MetaModelViewSet, basename="meta-model")
router.register(r"models", LLMModelViewSet, basename="model")
router.register(
    r"model-price-items",
    ModelPriceItemViewSet,
    basename="model-price-item",
)
router.register(r"channels", ProcurementChannelViewSet, basename="channel")
router.register(
    r"channel-model-prices",
    ChannelModelPriceViewSet,
    basename="channel-model-price",
)
router.register(
    r"channel-model-price-history",
    ChannelModelPriceHistoryViewSet,
    basename="channel-model-price-history",
)
router.register(
    r"channel-price-items",
    ChannelPriceItemViewSet,
    basename="channel-price-item",
)
router.register(
    r"resale-platforms",
    ResalePlatformViewSet,
    basename="resale-platform",
)
router.register(
    r"resale-listings",
    ResaleListingViewSet,
    basename="resale-listing",
)
router.register(
    r"resale-listing-exclusions",
    ResaleListingExclusionViewSet,
    basename="resale-listing-exclusion",
)
router.register(
    r"resale-listing-price-history",
    ResaleListingPriceHistoryViewSet,
    basename="resale-listing-price-history",
)
router.register(
    r"reconciliation-records",
    UsageReconciliationRecordViewSet,
    basename="reconciliation-record",
)

urlpatterns = [
    path("", include(router.urls)),
    path("summary/", SummaryAPIView.as_view(), name="llm-ops-summary"),
    path(
        "collect/yunce/",
        YunceCollectionAPIView.as_view(),
        name="llm-ops-yunce-collect",
    ),
    path(
        "manual-price-import/",
        ManualPriceImportAPIView.as_view(),
        name="llm-ops-manual-price-import",
    ),
]
