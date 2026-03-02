"""
API URL routes for data_collector.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CollectorConfigViewSet,
    RawDataAttachmentViewSet,
    RawDataRecordViewSet,
    StatsAPIView,
)

router = DefaultRouter()
router.register(r"configs", CollectorConfigViewSet, basename="config")
router.register(r"records", RawDataRecordViewSet, basename="record")
router.register(
    r"attachments", RawDataAttachmentViewSet, basename="attachment"
)

urlpatterns = [
    path("", include(router.urls)),
    path("stats/", StatsAPIView.as_view(), name="stats"),
]
