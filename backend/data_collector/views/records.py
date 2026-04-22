"""
RawDataRecord and RawDataAttachment views. User-scoped; uuid in URLs.
"""
import os

from django.http import FileResponse

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import RawDataAttachment, RawDataRecord
from ..serializers import (
    RawDataAttachmentSerializer,
    RawDataRecordDetailSerializer,
    RawDataRecordListSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=["data-collector"],
        summary="List raw data records",
        description="List records for user; filter by platform.",
    ),
    retrieve=extend_schema(
        tags=["data-collector"],
        summary="Get raw data record",
        description="Get record by uuid with raw_data and attachments.",
    ),
)
class RawDataRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for RawDataRecord. Filter by user; uuid in URL.
    """

    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        qs = RawDataRecord.objects.filter(user=self.request.user)
        platform = self.request.query_params.get("platform")
        if platform:
            qs = qs.filter(platform=platform)
        is_deleted = self.request.query_params.get("is_deleted")
        if is_deleted is not None:
            qs = qs.filter(is_deleted=is_deleted.lower() == "true")
        return qs.order_by("-last_collected_at")

    def get_serializer_class(self):
        if self.action == "list":
            return RawDataRecordListSerializer
        return RawDataRecordDetailSerializer


@extend_schema_view(
    retrieve=extend_schema(
        tags=["data-collector"],
        summary="Get attachment",
        description="Get attachment metadata by uuid.",
    ),
)
class RawDataAttachmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for RawDataAttachment. Download via separate action.
    """

    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"
    serializer_class = RawDataAttachmentSerializer

    def get_queryset(self):
        return RawDataAttachment.objects.filter(
            raw_record__user=self.request.user
        )

    @extend_schema(
        tags=["data-collector"],
        summary="Download attachment",
        description="Return file stream or redirect to file_url.",
    )
    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, uuid=None):
        att = self.get_object()
        if not att.file_path:
            return Response(
                {"detail": "File path not set."},
                status=404,
            )
        if not os.path.isfile(att.file_path):
            return Response(
                {"detail": "File not found on server."},
                status=404,
            )
        return FileResponse(
            open(att.file_path, "rb"),
            as_attachment=True,
            filename=att.file_name,
        )
