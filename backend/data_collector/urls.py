"""
URL configuration for data_collector API.
"""
from django.urls import include, path

urlpatterns = [
    path("", include("data_collector.api_urls")),
]
