"""Expose archived and new API routes together for local regression only."""

from django.urls import include, path

from llm_ops.tests.archive_urls import urlpatterns as archived_patterns

urlpatterns = [
    *archived_patterns,
    path("api/v1/agione-ops/", include("agione_ops.urls")),
]
