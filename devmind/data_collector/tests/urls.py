"""
Minimal URLconf for data_collector tests.
"""
from django.urls import path, include

urlpatterns = [
    path("api/v1/data-collector/", include("data_collector.urls")),
]
