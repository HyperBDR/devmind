from __future__ import annotations

import logging
import re
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone
from quotation.models import (
    DocumentAsset,
    DocumentParseResult,
    DocumentParseStatus,
    DocumentType,
    ExportJob,
    ExportJobStatus,
    Quotation,
    QuotationSourceType,
    SyncJob,
    SyncJobStatus,
)
from quotation.services.export_archive import (
    prepare_export_upload_tracking,
    update_export_upload_tracking,
)
from quotation.services.export_renderer import (
    CURRENT_RENDERER_VERSION,
    TemplateValidationError,
    convert_xlsx_to_pdf,
    render_quotation_xlsx,
)
from quotation.services.storage import (
    delete_document,
    document_storage_key,
    resolve_document_path,
    write_document_atomic,
)

logger = logging.getLogger(__name__)


def _original_import_excel_bytes(job: ExportJob) -> bytes | None:
    """Return the untouched Excel source for an imported first revision."""
    if job.quotation.source_type != QuotationSourceType.DOCUMENT_IMPORT:
        return None
    first_version_no = (
        job.quotation.versions.order_by("version_no")
        .values_list("version_no", flat=True)
        .first()
    )
    if job.quotation_version_no != first_version_no:
        return None
    parse_result = (
        DocumentParseResult.objects.select_related("asset")
        .filter(
            quotation_id=job.quotation_id,
            asset__quotation_id=job.quotation_id,
            asset__doc_type=DocumentType.EXCEL,
            asset__source__in=("feishu", "local"),
            status__in=(
                DocumentParseStatus.CONFIRMED,
                DocumentParseStatus.SUPERSEDED,
            ),
        )
        .order_by("confirmed_at", "created_at", "id")
        .first()
    )
    if parse_result is None:
        raise TemplateValidationError(
            "Original imported Excel file is unavailable",
            code="original_import_unavailable",
        )
    path = resolve_document_path(parse_result.asset.storage_key)
    if not path.is_file():
        raise TemplateValidationError(
            "Original imported Excel file is unavailable",
            code="original_import_unavailable",
        )
    return path.read_bytes()


def _asset_id(job_id: str, doc_type: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"quotation-export:{job_id}:{doc_type}"))


def _safe_file_stem(job: ExportJob) -> str:
    quote_no = str(job.quotation_version.snapshot_json.get("quote_no") or "")
    safe_quote_no = re.sub(r"[^A-Za-z0-9._-]+", "-", quote_no).strip("-.")
    return safe_quote_no or f"quotation-{job.quotation_version_no}"


def _persist_assets(
    job: ExportJob,
    outputs: dict[str, bytes],
) -> list[DocumentAsset]:
    created_keys = []
    definitions = {
        DocumentType.EXCEL: (
            "xlsx",
            "application/vnd.openxmlformats-" "officedocument.spreadsheetml.sheet",
        ),
        DocumentType.PDF: ("pdf", "application/pdf"),
    }
    try:
        with transaction.atomic():
            assets = []
            for doc_type, content in outputs.items():
                extension, mime_type = definitions[doc_type]
                asset_id = _asset_id(job.id, doc_type)
                storage_key = document_storage_key(
                    asset_id,
                    job.quotation_id,
                )
                write_document_atomic(content, storage_key)
                created_keys.append(storage_key)
                asset, _ = DocumentAsset.objects.update_or_create(
                    export_job=job,
                    doc_type=doc_type,
                    defaults={
                        "id": asset_id,
                        "quotation": job.quotation,
                        "quotation_version": job.quotation_version,
                        "template": job.template,
                        "file_name": (
                            f"{_safe_file_stem(job)}-v"
                            f"{job.quotation_version_no}.{extension}"
                        ),
                        "mime_type": mime_type,
                        "storage_key": storage_key,
                        "size_bytes": len(content),
                        "content_hash": sha256(content).hexdigest(),
                        "template_version": job.template_version,
                        "renderer_version": job.renderer_version,
                        "source": "generated",
                        "created_by_email": (
                            job.requested_by.email if job.requested_by_id else None
                        ),
                    },
                )
                assets.append(asset)
            return assets
    except Exception:
        for storage_key in created_keys:
            delete_document(storage_key)
        raise


def queue_replica_uploads(
    job: ExportJob,
    assets: list[DocumentAsset],
) -> None:
    from quotation.tasks import sync_document_replica_task

    try:
        trackers = prepare_export_upload_tracking(job, assets)
    except DatabaseError:
        logger.exception(
            "quotation_archive_tracking_init_failed",
            extra={"export_job_id": job.id},
        )
        ExportJob.objects.filter(pk=job.id).exclude(
            status=ExportJobStatus.COMPLETED
        ).update(
            status=ExportJobStatus.UPLOAD_FAILED,
            error_code="archive_tracking_init_failed",
            error_message=("Quotation archive tracking could not be initialized"),
            finished_at=timezone.now(),
        )
        return
    for asset in assets:
        tracker = trackers[asset.id]
        try:
            task = sync_document_replica_task.apply_async(
                args=[job.id, asset.id, tracker.id],
                queue="quotation_sync",
            )
        except Exception:
            update_export_upload_tracking(
                tracker.id,
                SyncJobStatus.FAILED,
                error_code="archive_enqueue_failed",
            )
            logger.exception(
                "quotation_archive_enqueue_failed",
                extra={
                    "export_job_id": job.id,
                    "asset_id": asset.id,
                },
            )
            ExportJob.objects.filter(pk=job.id).exclude(
                status=ExportJobStatus.COMPLETED
            ).update(
                status=ExportJobStatus.UPLOAD_FAILED,
                error_code="archive_enqueue_failed",
                error_message="Quotation archive could not be queued",
                finished_at=timezone.now(),
            )
        else:
            try:
                SyncJob.objects.filter(pk=tracker.id).update(
                    celery_task_id=task.id,
                )
            except DatabaseError:
                logger.exception(
                    "quotation_archive_task_id_persist_failed",
                    extra={
                        "export_job_id": job.id,
                        "asset_id": asset.id,
                        "tracking_job_id": tracker.id,
                    },
                )


def render_export_job(job_id: str) -> dict:
    """Render and persist all requested formats for one pinned export."""
    started = timezone.now()
    claimable_statuses = {
        ExportJobStatus.QUEUED,
        ExportJobStatus.RENDER_FAILED,
        ExportJobStatus.RENDERING_EXCEL,
        ExportJobStatus.CONVERTING_PDF,
    }
    quotation_id = ExportJob.objects.values_list(
        "quotation_id",
        flat=True,
    ).get(pk=job_id)
    with transaction.atomic():
        Quotation.objects.select_for_update().get(
            pk=quotation_id,
        )
        job = ExportJob.objects.select_for_update().get(pk=job_id)
        if job.status not in claimable_statuses:
            return {"job_id": job.id, "status": job.status}
        if job.renderer_version != CURRENT_RENDERER_VERSION:
            raise TemplateValidationError(
                "Pinned quotation renderer version is unsupported",
                code="renderer_version_unsupported",
            )
        job.status = ExportJobStatus.RENDERING_EXCEL
        job.started_at = started
        job.finished_at = None
        job.error_code = ""
        job.error_message = ""
        job.save(
            update_fields=[
                "status",
                "started_at",
                "finished_at",
                "error_code",
                "error_message",
                "updated_at",
            ]
        )

    excel_bytes = _original_import_excel_bytes(job)
    if excel_bytes is None:
        excel_bytes = render_quotation_xlsx(
            job.template,
            job.quotation_version.snapshot_json,
        )
    outputs = {}
    if "xlsx" in job.formats:
        outputs[DocumentType.EXCEL] = excel_bytes
    if "pdf" in job.formats:
        ExportJob.objects.filter(pk=job.id).update(
            status=ExportJobStatus.CONVERTING_PDF
        )
        outputs[DocumentType.PDF] = convert_xlsx_to_pdf(
            excel_bytes,
            job_id=job.id,
        )

    assets = _persist_assets(job, outputs)
    now = timezone.now()
    if job.archive_to_feishu:
        if settings.QUOTATION_DOCUMENT_REPLICA_ENABLED:
            next_status = ExportJobStatus.UPLOAD_QUEUED
            error_code = ""
            error_message = ""
            finished_at = None
        else:
            next_status = ExportJobStatus.UPLOAD_FAILED
            error_code = "replica_archiving_disabled"
            error_message = "Remote quotation archiving is disabled"
            finished_at = now
    else:
        next_status = ExportJobStatus.COMPLETED
        error_code = ""
        error_message = ""
        finished_at = now
    with transaction.atomic():
        ExportJob.objects.filter(pk=job.id).update(
            status=next_status,
            error_code=error_code,
            error_message=error_message,
            finished_at=finished_at,
        )
        if next_status == ExportJobStatus.UPLOAD_QUEUED:
            transaction.on_commit(lambda: queue_replica_uploads(job, assets))
    current_status = (
        ExportJob.objects.filter(pk=job.id)
        .values_list(
            "status",
            flat=True,
        )
        .get()
    )
    return {"job_id": job.id, "status": current_status}


def mark_render_failed(job_id: str, exc: Exception) -> None:
    code = getattr(exc, "code", "render_failed")
    ExportJob.objects.filter(pk=job_id).update(
        status=ExportJobStatus.RENDER_FAILED,
        error_code=str(code)[:100],
        error_message=str(exc)[:500],
        finished_at=timezone.now(),
    )


def reset_render_for_retry(job_id: str, exc: Exception) -> None:
    code = getattr(exc, "code", "render_retry")
    ExportJob.objects.filter(pk=job_id).update(
        status=ExportJobStatus.QUEUED,
        error_code=str(code)[:100],
        error_message="Transient render failure; retry queued",
        finished_at=None,
    )
