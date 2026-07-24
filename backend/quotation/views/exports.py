from __future__ import annotations

from django.conf import settings
from django.db import IntegrityError, transaction
from quotation.access import can_access_quotation, forbidden_response
from quotation.audit import set_request_audit_target
from quotation.models import (
    ExportJob,
    ExportJobStatus,
    Quotation,
    QuotationTemplate,
    QuotationTemplateStatus,
)
from quotation.services.export_jobs import ExportRequestError, create_export_job
from quotation.services.export_renderer import (
    TemplateValidationError,
    register_template_version,
)
from rest_framework import serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class QuotationTemplateUploadSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    version = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(
        choices=QuotationTemplateStatus.choices,
        default=QuotationTemplateStatus.DRAFT,
    )
    file = serializers.FileField()

    def validate_file(self, upload):
        if upload.size > settings.QUOTATION_MAX_TEMPLATE_BYTES:
            raise serializers.ValidationError(
                "quotation template exceeds the size limit"
            )
        return upload


def quotation_template_data(template: QuotationTemplate) -> dict:
    return {
        "id": template.id,
        "name": template.name,
        "version": template.version,
        "content_hash": template.content_hash,
        "status": template.status,
        "created_by": template.created_by_id,
        "created_at": template.created_at,
    }


class QuotationTemplateListCreateView(APIView):
    """List and upload immutable XLSX template versions."""

    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser]

    def get(self, request):
        templates = QuotationTemplate.objects.select_related("created_by").all()
        return Response([quotation_template_data(template) for template in templates])

    def post(self, request):
        serializer = QuotationTemplateUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]
        try:
            template = register_template_version(
                name=serializer.validated_data["name"],
                version=serializer.validated_data["version"],
                content=upload.read(),
                status=serializer.validated_data["status"],
                created_by=request.user,
            )
        except TemplateValidationError as exc:
            return Response(
                {"detail": str(exc), "error_code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError:
            return Response(
                {"detail": "template name and version already exist"},
                status=status.HTTP_409_CONFLICT,
            )
        set_request_audit_target(
            request,
            target_id=template.id,
            target_label=f"{template.name} v{template.version}",
        )
        return Response(
            quotation_template_data(template),
            status=status.HTTP_201_CREATED,
        )


class ExportCreateSerializer(serializers.Serializer):
    formats = serializers.ListField(
        child=serializers.ChoiceField(choices=("xlsx", "pdf")),
        allow_empty=False,
    )
    quotation_version = serializers.IntegerField(
        min_value=1,
        required=False,
    )
    template_id = serializers.CharField(required=False, allow_blank=False)
    archive_to_feishu = serializers.BooleanField(
        required=False,
        default=False,
    )


def export_job_data(job: ExportJob) -> dict:
    assets = [
        {
            "id": asset.id,
            "format": "xlsx" if asset.doc_type == "excel" else "pdf",
            "file_name": asset.file_name,
            "mime_type": asset.mime_type,
            "size_bytes": asset.size_bytes,
            "content_hash": asset.content_hash,
            "download_url": (f"/api/v1/quotation/documents/{asset.id}/download"),
        }
        for asset in job.assets.all()
    ]
    return {
        "job_id": job.id,
        "status": job.status,
        "quotation_id": job.quotation_id,
        "quotation_version": job.quotation_version_no,
        "template_id": job.template_id,
        "template_version": job.template_version,
        "renderer_version": job.renderer_version,
        "formats": job.formats,
        "archive_to_feishu": job.archive_to_feishu,
        "error_code": job.error_code or None,
        "error_message": job.error_message or None,
        "assets": assets,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "finished_at": job.finished_at,
    }


class QuotationExportCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quotation_id: str):
        quotation = (
            Quotation.objects.prefetch_related("versions")
            .filter(pk=quotation_id)
            .first()
        )
        if quotation is None:
            return Response({"detail": "quotation not found"}, status=404)
        if not can_access_quotation(request.user, quotation):
            return forbidden_response()
        serializer = ExportCreateSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        set_request_audit_target(
            request,
            target_id=quotation.id,
            target_label=quotation.quote_no,
        )
        try:
            job, _ = create_export_job(
                quotation=quotation,
                formats=serializer.validated_data["formats"],
                actor=request.user,
                quotation_version_no=serializer.validated_data.get("quotation_version"),
                template_id=serializer.validated_data.get("template_id"),
                archive_to_feishu=serializer.validated_data["archive_to_feishu"],
                request=request,
            )
        except ExportRequestError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(
            {"job_id": job.id, "status": job.status},
            status=status.HTTP_202_ACCEPTED,
        )


class ExportJobDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id: str):
        job = (
            ExportJob.objects.select_related(
                "quotation",
                "quotation_version",
                "template",
            )
            .prefetch_related("assets")
            .filter(pk=job_id)
            .first()
        )
        if job is None:
            return Response({"detail": "export job not found"}, status=404)
        if not can_access_quotation(request.user, job.quotation):
            return forbidden_response()
        set_request_audit_target(
            request,
            target_id=job.quotation_id,
            target_label=job.quotation.quote_no,
        )
        return Response(export_job_data(job))


class ExportJobRetryUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id: str):
        from quotation.services.export_pipeline import queue_replica_uploads

        with transaction.atomic():
            job = (
                ExportJob.objects.select_for_update()
                .select_related("quotation")
                .prefetch_related("assets")
                .filter(pk=job_id)
                .first()
            )
            if job is None:
                return Response(
                    {"detail": "export job not found"},
                    status=404,
                )
            if not can_access_quotation(request.user, job.quotation):
                return forbidden_response()
            if job.status != ExportJobStatus.UPLOAD_FAILED:
                return Response(
                    {"detail": "only failed uploads can be retried"},
                    status=409,
                )
            assets = list(job.assets.all())
            if not assets:
                return Response(
                    {"detail": "rendered assets are unavailable"},
                    status=409,
                )
            job.status = ExportJobStatus.UPLOAD_QUEUED
            job.error_code = ""
            job.error_message = ""
            job.finished_at = None
            job.save(
                update_fields=[
                    "status",
                    "error_code",
                    "error_message",
                    "finished_at",
                    "updated_at",
                ]
            )
            transaction.on_commit(lambda: queue_replica_uploads(job, assets))
        job.refresh_from_db(fields=["status"])
        return Response(
            {"job_id": job.id, "status": job.status},
            status=status.HTTP_202_ACCEPTED,
        )
