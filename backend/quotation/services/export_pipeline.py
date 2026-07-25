from __future__ import annotations

import logging
import re
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from quotation.models import DocumentAsset, DocumentType, ExportJob, ExportJobStatus
from quotation.services.export_renderer import (
    convert_xlsx_to_pdf,
    render_quotation_xlsx,
)
from quotation.services.storage import (
    delete_document,
    document_storage_key,
    write_document_atomic,
)

logger = logging.getLogger(__name__)


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

    for asset in assets:
        try:
            sync_document_replica_task.apply_async(
                args=[job.id, asset.id],
                queue="quotation_sync",
            )
        except Exception:
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


def render_export_job(job_id: str) -> dict:
    """Render and persist all requested formats for one pinned export."""
    started = timezone.now()
    claimed = ExportJob.objects.filter(
        pk=job_id,
        status__in={
            ExportJobStatus.QUEUED,
            ExportJobStatus.RENDER_FAILED,
            ExportJobStatus.RENDERING_EXCEL,
            ExportJobStatus.CONVERTING_PDF,
        },
    ).update(
        status=ExportJobStatus.RENDERING_EXCEL,
        started_at=started,
        finished_at=None,
        error_code="",
        error_message="",
    )
    job = ExportJob.objects.select_related(
        "quotation",
        "quotation_version",
        "template",
        "requested_by",
    ).get(pk=job_id)
    if not claimed:
        return {"job_id": job.id, "status": job.status}

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
