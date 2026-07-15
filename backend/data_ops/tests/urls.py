"""URLconf for data_ops tests."""

from django.urls import include, path

urlpatterns = [
    path("api/v1/assistant/", include("ai_assistant.urls")),
    path("api/v1/data-ops/", include("data_ops.urls")),
]
