from django.urls import path

from .views import (
    CompareAPIView,
    OverviewAPIView,
    SyncAPIView,
)

urlpatterns = [
    path("overview/", OverviewAPIView.as_view(), name="ai-pricehub-overview"),
    path("compare/", CompareAPIView.as_view(), name="ai-pricehub-compare"),
    path("sync/", SyncAPIView.as_view(), name="ai-pricehub-sync"),
]
