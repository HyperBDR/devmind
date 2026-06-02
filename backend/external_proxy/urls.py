from django.urls import path

from .views import (
    ExternalSiteDetailView,
    ExternalSiteLaunchView,
    ExternalSiteListView,
    InternalAuthCheckView,
    InternalAuthTokenView,
    InternalRoutingConfigView,
)

urlpatterns = [
    path("sites/", ExternalSiteListView.as_view(), name="external-site-list"),
    path(
        "sites/<int:site_id>/launch/",
        ExternalSiteLaunchView.as_view(),
        name="external-site-launch",
    ),
    path(
        "sites/<int:site_id>/",
        ExternalSiteDetailView.as_view(),
        name="external-site-detail",
    ),
    path(
        "internal/routing-config/",
        InternalRoutingConfigView.as_view(),
        name="external-site-routing-config",
    ),
    path(
        "internal/auth-token/",
        InternalAuthTokenView.as_view(),
        name="external-site-auth-token",
    ),
    path(
        "internal/auth-check/",
        InternalAuthCheckView.as_view(),
        name="external-site-auth-check",
    ),
]
