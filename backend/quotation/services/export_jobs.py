from __future__ import annotations

import logging
from hashlib import sha256

from django.db import transaction
from django.utils import timezone
from quotation.audit import AUDIT_CONTEXT
from quotation.models import (
    ExportJob,
    ExportJobStatus,
    Quotation,
    QuotationTemplate,
    QuotationTemplateStatus,
    QuotationVersion,
)
from quotation.permissions import user_display_email
from quotation.services.export_renderer import (
    CURRENT_RENDERER_VERSION,
    ensure_default_template,
)
from quotation.services.quotation_service import create_version_snapshot

logger = logging.getLogger(__name__)


class ExportRequestError(ValueError):
    pass


def renderer_version() -> str:
    return CURRENT_RENDERER_VERSION


def _resolve_version(
    *,
    quotation: Quotation,
    version_no: int | None,
    actor,
) -> QuotationVersion:
    if version_no is not None:
        version = QuotationVersion.objects.filter(
            quotation=quotation,
            version_no=version_no,
        ).first()
        if version is None:
            raise ExportRequestError("quotation version not found")
        return version
    return create_version_snapshot(
        quotation,
        operator_email=user_display_email(actor),
        notes="Snapshot created for document export",
    )


def _resolve_template(
    *,
    template_id: str | None,
    actor,
) -> QuotationTemplate:
    if template_id:
        template = QuotationTemplate.objects.filter(
            pk=template_id,
            status=QuotationTemplateStatus.ACTIVE,
        ).first()
        if template is None:
            raise ExportRequestError("active quotation template not found")
        return template
    return ensure_default_template(created_by=actor)


def _idempotency_key(
    *,
    version: QuotationVersion,
    template: QuotationTemplate,
    formats: list[str],
    archive_folder_token: str = "",
) -> str:
    material = "|".join(
        [
            version.quotation_id,
            str(version.version_no),
            template.id,
            str(template.version),
            renderer_version(),
            ",".join(formats),
            archive_folder_token,
        ]
    )
    return sha256(material.encode("utf-8")).hexdigest()


def _enqueue_export(job_id: str) -> None:
    from quotation.tasks import render_quotation_export_task

    try:
        result = render_quotation_export_task.apply_async(
            args=[job_id],
            queue="quotation_render",
        )
    except Exception:
        logger.exception(
            "quotation_export_enqueue_failed",
            extra={"export_job_id": job_id},
        )
        ExportJob.objects.filter(pk=job_id).update(
            status=ExportJobStatus.RENDER_FAILED,
            error_code="export_enqueue_failed",
            error_message="Quotation export could not be queued",
            finished_at=timezone.now(),
        )
        return
    ExportJob.objects.filter(pk=job_id).update(celery_task_id=result.id)


def create_export_job(
    *,
    quotation: Quotation,
    formats: list[str],
    actor,
    quotation_version_no: int | None = None,
    template_id: str | None = None,
    archive_to_feishu: bool = False,
    archive_folder_token: str = "",
    request=None,
) -> tuple[ExportJob, bool]:
    normalized_formats = sorted(set(formats))
    with transaction.atomic():
        quotation = Quotation.objects.select_for_update().get(
            pk=quotation.pk,
        )
        version = _resolve_version(
            quotation=quotation,
            version_no=quotation_version_no,
            actor=actor,
        )
        template = _resolve_template(
            template_id=template_id,
            actor=actor,
        )
        context = AUDIT_CONTEXT.get()
        request_id = getattr(request, "audit_request_id", "") or context.get(
            "request_id", ""
        )
        trace_id = getattr(request, "audit_trace_id", "") or context.get("trace_id", "")
        key = _idempotency_key(
            version=version,
            template=template,
            formats=normalized_formats,
            archive_folder_token=archive_folder_token,
        )
        job, created = ExportJob.objects.get_or_create(
            idempotency_key=key,
            defaults={
                "quotation": quotation,
                "quotation_version": version,
                "template": template,
                "quotation_version_no": version.version_no,
                "template_version": template.version,
                "renderer_version": renderer_version(),
                "formats": normalized_formats,
                "archive_to_feishu": archive_to_feishu,
                "archive_folder_token": archive_folder_token,
                "requested_by": actor,
                "request_id": request_id,
                "trace_id": trace_id,
            },
        )
        if not created:
            job = ExportJob.objects.select_for_update().get(pk=job.pk)
        archive_upgraded = archive_to_feishu and not job.archive_to_feishu
        if archive_upgraded:
            job.archive_to_feishu = True
            job.save(update_fields=["archive_to_feishu", "updated_at"])
        if created:
            transaction.on_commit(lambda: _enqueue_export(job.id))
        elif job.status == ExportJobStatus.RENDER_FAILED:
            job.status = ExportJobStatus.QUEUED
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
            transaction.on_commit(lambda: _enqueue_export(job.id))
        elif archive_upgraded and job.assets.exists():
            from quotation.services.export_pipeline import queue_replica_uploads

            assets = list(job.assets.all())
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
    return job, created
