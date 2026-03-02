"""
Views for data_collector API.
"""
from .config import CollectorConfigViewSet
from .records import RawDataAttachmentViewSet, RawDataRecordViewSet
from .stats import StatsAPIView

__all__ = [
    "CollectorConfigViewSet",
    "RawDataRecordViewSet",
    "RawDataAttachmentViewSet",
    "StatsAPIView",
]
