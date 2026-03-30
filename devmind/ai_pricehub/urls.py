from django.urls import path

from .views import (
    CompareAPIView,
    OverviewAPIView,
    PrimarySourceConfigAPIView,
    PrimarySourceConfigDetailAPIView,
    SyncAPIView,
)

urlpatterns = [
    path("overview/", OverviewAPIView.as_view(), name="ai-pricehub-overview"),
    path("compare/", CompareAPIView.as_view(), name="ai-pricehub-compare"),
    path("sync/", SyncAPIView.as_view(), name="ai-pricehub-sync"),
    path(
        "admin/primary-source-config/",
        PrimarySourceConfigAPIView.as_view(),
        name="ai-pricehub-primary-source-config",
    ),
    path(
        "admin/primary-source-config/<int:config_id>/",
        PrimarySourceConfigDetailAPIView.as_view(),
        name="ai-pricehub-primary-source-config-detail",
    ),
]
