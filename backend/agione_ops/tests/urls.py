"""Only the new app is mounted in the isolated acceptance database."""

from django.urls import include, path

urlpatterns = [
    path("api/v1/agione-ops/", include("agione_ops.urls")),
]
