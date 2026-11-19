from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import logging
import re
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from quotation.audit import quotation_audit_label, record_audit_event
from quotation.models import (
    AuditEvent,
    DocumentAsset,
    DocumentLifecycleState,
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
    SUPPORTED_RENDERER_VERSIONS,
    PdfConversionError,
    TemplateValidationError,
    convert_attachment_to_pdf,
    convert_xlsx_to_pdf,
    render_quotation_xlsx,
)
from quotation.services.storage import (
    attachment_pdf_cache_key,
    delete_document,
    document_storage_key,
    resolve_document_path,
    write_document_atomic,
)

logger = logging.getLogger(__name__)


def _record_export_audit(job_id: str) -> None:
    """Record one terminal quotation export result."""
    job = ExportJob.objects.select_related(
        "quotation",
        "requested_by",
    ).get(pk=job_id)
    if job.status not in {
        ExportJobStatus.COMPLETED,
        ExportJobStatus.UPLOAD_QUEUED,
        ExportJobStatus.UPLOAD_FAILED,
        ExportJobStatus.RENDER_FAILED,
    }:
        return
    succeeded = job.status != ExportJobStatus.RENDER_FAILED
    result = (
        AuditEvent.RESULT_SUCCEEDED
        if succeeded
        else AuditEvent.RESULT_FAILED
    )
    request_id = job.request_id
    trace_id = job.trace_id or request_id
    request = SimpleNamespace(
        user=job.requested_by,
        META={
            "HTTP_X_REQUEST_ID": request_id,
            "HTTP_X_TRACE_ID": trace_id,
            "HTTP_IDEMPOTENCY_KEY": (
                f"quotation-export:{job.id}:{result}"
            ),
        },
        audit_request_id=request_id,
        audit_trace_id=trace_id,
    )
    try:
        record_audit_event(
            request=request,
            module="quotation",
            action="export",
            result=result,
            target_type="quotation",
            target_id=job.quotation_id,
            target_label=quotation_audit_label(job.quotation),
            summary="" if succeeded else "Quotation export failed",
            reason_code="" if succeeded else "export_failed",
            error_code="" if succeeded else job.error_code,
            metadata={
                "formats": job.formats,
                "status_code": 200 if succeeded else 500,
            },
        )
    except DatabaseError:
        logger.exception(
            "quotation_export_audit_failed",
            extra={"export_job_id": job.id},
        )


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
        DocumentType.MERGED_PDF: ("pdf", "application/pdf"),
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
                        "file_name": _asset_file_name(
                            job,
                            doc_type,
                            extension,
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


def _asset_file_name(
    job: ExportJob,
    doc_type: str,
    extension: str,
) -> str:
    """Build distinct names for original and merged export artifacts."""
    suffix = "-with-attachments" if doc_type == DocumentType.MERGED_PDF else ""
    return (
        f"{_safe_file_stem(job)}-v{job.quotation_version_no}"
        f"{suffix}.{extension}"
    )


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


def _reusable_quotation_pdf(job: ExportJob) -> bytes | None:
    """Read a completed PDF for the same pinned export inputs."""
    asset = DocumentAsset.objects.filter(
        quotation_id=job.quotation_id,
        quotation_version_id=job.quotation_version_id,
        template_id=job.template_id,
        template_version=job.template_version,
        renderer_version=job.renderer_version,
        doc_type=DocumentType.PDF,
        lifecycle_state=DocumentLifecycleState.ACTIVE,
        export_job__status__in=[
            ExportJobStatus.COMPLETED, ExportJobStatus.UPLOAD_FAILED,
        ],
    ).exclude(export_job_id=job.id).first()
    if asset is None:
        return None
    try:
        content = resolve_document_path(asset.storage_key).read_bytes()
    except OSError:
        return None
    if content.startswith(b"%PDF-") and (
        sha256(content).hexdigest() == asset.content_hash
    ):
        return content
    return None


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
        if job.renderer_version not in SUPPORTED_RENDERER_VERSIONS:
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

    quotation_pdf = None
    if job.attachment_selection and "pdf" in job.formats:
        quotation_pdf = _reusable_quotation_pdf(job)
    excel_bytes = None
    needs_excel = "xlsx" in job.formats or quotation_pdf is None
    if needs_excel and ("xlsx" in job.formats or "pdf" in job.formats):
        excel_bytes = _original_import_excel_bytes(job)
        if excel_bytes is None:
            excel_bytes = render_quotation_xlsx(
                job.template,
                job.quotation_version.snapshot_json,
                renderer_version=job.renderer_version,
            )
    outputs = {}
    if "xlsx" in job.formats:
        outputs[DocumentType.EXCEL] = excel_bytes
    if "pdf" in job.formats:
        ExportJob.objects.filter(pk=job.id).update(
            status=ExportJobStatus.CONVERTING_PDF
        )
        if quotation_pdf is None:
            quotation_pdf = convert_xlsx_to_pdf(excel_bytes, job_id=job.id)
        outputs[DocumentType.PDF] = quotation_pdf
        if job.attachment_selection:
            outputs[DocumentType.MERGED_PDF] = _merge_public_attachments(
                job,
                outputs[DocumentType.PDF],
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
    _record_export_audit(job.id)
    return {"job_id": job.id, "status": current_status}


def _merge_public_attachments(job: ExportJob, quotation_pdf: bytes) -> bytes:
    """Append selected active public files to the quotation PDF."""
    from quotation.models import PublicAttachment, PublicAttachmentStatus

    attachments = list(
        PublicAttachment.objects.select_related("asset").filter(
            id__in=job.attachment_selection,
            status=PublicAttachmentStatus.ACTIVE,
        )
    )
    by_id = {item.id: item for item in attachments}
    writer = PdfWriter()
    for page in PdfReader(BytesIO(quotation_pdf)).pages:
        writer.add_page(page)
    deadline = monotonic() + 90
    for item_id in job.attachment_selection:
        if item_id not in by_id:
            raise TemplateValidationError(
                "A selected public attachment is no longer available.",
                code="public_attachment_unavailable",
            )
        asset = by_id[item_id].asset
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TemplateValidationError(
                "Public attachment export timed out. Select fewer files.",
                code="public_attachments_timeout",
            )
        try:
            content = _attachment_pdf_bytes(asset, job.id, timeout=remaining)
            reader = PdfReader(BytesIO(content))
            for page in reader.pages:
                writer.add_page(page)
        except PdfConversionError as exc:
            message = (
                f"{asset.file_name}: {exc}. "
                "Try again or download fewer files."
            )
            raise TemplateValidationError(
                message,
                code=exc.code,
            ) from exc
        except (OSError, PdfReadError) as exc:
            raise TemplateValidationError(
                f"Cannot read public attachment: {asset.file_name}",
                code="invalid_public_attachment",
            ) from exc
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _attachment_pdf_bytes(
    asset: DocumentAsset, job_id: str, *, timeout: float | None = None,
) -> bytes:
    """Read a public PDF or convert a supported Office attachment."""
    content = resolve_document_path(asset.storage_key).read_bytes()
    extension = Path(asset.file_name).suffix.lower()
    if extension == ".pdf" and content.startswith(b"%PDF-"):
        return content
    if extension in {".doc", ".docx", ".xls", ".xlsx"}:
        cache_key = attachment_pdf_cache_key(asset.storage_key)
        digest = sha256(content).digest()
        try:
            cached = resolve_document_path(cache_key).read_bytes()
        except OSError:
            cached = b""
        if cached.startswith(digest + b"%PDF-"):
            return cached[len(digest):]
        pdf = convert_attachment_to_pdf(
            content,
            asset.file_name,
            job_id=job_id,
            timeout=timeout,
        )
        try:
            write_document_atomic(digest + pdf, cache_key)
        except OSError:
            logger.warning(
                "Could not cache public attachment PDF",
                exc_info=True,
            )
        return pdf
    raise TemplateValidationError(
        "Public attachment format is not supported",
        code="invalid_public_attachment",
    )


def mark_render_failed(job_id: str, exc: Exception) -> None:
    code = getattr(exc, "code", "render_failed")
    ExportJob.objects.filter(pk=job_id).update(
        status=ExportJobStatus.RENDER_FAILED,
        error_code=str(code)[:100],
        error_message=str(exc)[:500],
        finished_at=timezone.now(),
    )
    _record_export_audit(job_id)


def reset_render_for_retry(job_id: str, exc: Exception) -> None:
    code = getattr(exc, "code", "render_retry")
    ExportJob.objects.filter(pk=job_id).update(
        status=ExportJobStatus.QUEUED,
        error_code=str(code)[:100],
        error_message="Transient render failure; retry queued",
        finished_at=None,
    )
