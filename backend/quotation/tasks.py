from __future__ import annotations

import logging
from datetime import timedelta
from time import perf_counter
from types import SimpleNamespace

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.cache import cache
from django.db import OperationalError, transaction
from django.utils import timezone
from quotation.metrics import record_export_operation, record_storage_operation
from quotation.models import (
    DocumentAsset,
    DocumentParseStatus,
    RemoteFileCleanup,
    RemoteFileCleanupStatus,
    SyncJob,
    SyncJobStatus,
    SyncJobType,
)
from quotation.services.document_parsing.service import parse_and_create_quotation

logger = logging.getLogger(__name__)

FEISHU_SYNC_LOCK_KEY = "quotation:feishu:archive-folder-sync"


def _duration_ms(started: float) -> int:
    return max(round((perf_counter() - started) * 1000), 0)


def _record_export_stage(stage: str, result: str, started: float) -> None:
    record_export_operation(
        stage=stage,
        result=result,
        duration_seconds=max(perf_counter() - started, 0),
    )


def _record_feishu_sync_observability(
    job: SyncJob,
    *,
    result: str,
    error_code: str = "",
) -> None:
    """Record archive synchronization as operational telemetry."""
    sync_result = job.result_json if isinstance(job.result_json, dict) else {}
    errors = sync_result.get("errors")
    error_count = len(errors) if isinstance(errors, list) else 0
    folders = sync_result.get("folders")
    folder_names = [
        str(folder.get("name") or "").strip()
        for folder in folders
        if isinstance(folder, dict) and folder.get("name")
    ] if isinstance(folders, list) else []
    record_storage_operation(
        provider="feishu",
        operation="archive_sync",
        result=result,
        duration_seconds=max(job.duration_ms, 0) / 1000,
    )
    log_method = logger.error if result == "failure" else logger.info
    log_method(
        "quotation_feishu_sync_completed",
        extra={
            "created_count": sync_result.get("created_count", 0),
            "error_code": error_code,
            "error_count": error_count,
            "folder_count": len(folder_names),
            "parsed_count": sync_result.get("parsed_count", 0),
            "queued_parse_count": sync_result.get("queued_parse_count", 0),
            "result": result,
            "sync_job_id": str(job.id),
        },
    )


@shared_task(
    name="quotation.tasks.dispatch_remote_file_cleanups",
    acks_late=True,
)
def dispatch_remote_file_cleanups_task():
    """Dispatch durable pending cleanup intents to the sync queue."""
    now = timezone.now()
    lease_until = now + timedelta(minutes=5)
    with transaction.atomic():
        cleanup_ids = list(
            RemoteFileCleanup.objects.select_for_update(skip_locked=True)
            .filter(
                owned=True,
                status=RemoteFileCleanupStatus.PENDING,
                next_dispatch_at__lte=now,
            )
            .order_by("next_dispatch_at", "created_at", "id")
            .values_list("id", flat=True)[:200]
        )
        RemoteFileCleanup.objects.filter(id__in=cleanup_ids).update(
            next_dispatch_at=lease_until,
        )
    dispatched = 0
    for cleanup_id in cleanup_ids:
        try:
            delete_owned_remote_file_task.apply_async(
                args=[cleanup_id],
                queue="quotation_sync",
            )
        except Exception:
            RemoteFileCleanup.objects.filter(
                pk=cleanup_id,
                status=RemoteFileCleanupStatus.PENDING,
            ).update(next_dispatch_at=now)
            logger.exception(
                "quotation_remote_file_cleanup_dispatch_failed",
                extra={"remote_file_cleanup_id": cleanup_id},
            )
        else:
            dispatched += 1
    return {"pending": len(cleanup_ids), "dispatched": dispatched}


@shared_task(
    bind=True,
    name="quotation.tasks.render_quotation_export",
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=None,
    soft_time_limit=240,
    time_limit=300,
)
def render_quotation_export_task(
    self,
    job_id: str,
    failure_retries: int = 0,
):
    """Render one pinned quotation export in the unified worker."""
    from quotation.services.export_pipeline import (
        mark_render_failed,
        render_export_job,
        reset_render_for_retry,
    )
    from quotation.services.export_renderer import (
        PdfConversionBusyError,
        PdfConversionError,
        TemplateValidationError,
    )

    started = perf_counter()
    logger.info(
        "quotation_export_render_started",
        extra={
            "export_job_id": job_id,
            "attempt": self.request.retries + 1,
        },
    )
    try:
        result = render_export_job(job_id)
    except TemplateValidationError as exc:
        mark_render_failed(job_id, exc)
        _record_export_stage("render", "failure", started)
        logger.warning(
            "quotation_export_render_rejected",
            extra={
                "export_job_id": job_id,
                "error_code": exc.code,
                "duration_ms": _duration_ms(started),
            },
        )
        return {"job_id": job_id, "status": "render_failed"}
    except PdfConversionBusyError as exc:
        reset_render_for_retry(job_id, exc)
        _record_export_stage("render", "retry", started)
        logger.info(
            "quotation_export_render_capacity_busy",
            extra={
                "export_job_id": job_id,
                "duration_ms": _duration_ms(started),
            },
        )
        raise self.retry(
            args=(job_id, failure_retries),
            exc=exc,
            countdown=settings.QUOTATION_RENDER_RETRY_SECONDS,
        )
    except PdfConversionError as exc:
        if exc.retryable and failure_retries < 1:
            reset_render_for_retry(job_id, exc)
            _record_export_stage("render", "retry", started)
            raise self.retry(
                args=(job_id, failure_retries + 1),
                exc=exc,
                countdown=10 * (2**self.request.retries),
            )
        mark_render_failed(job_id, exc)
        _record_export_stage("render", "failure", started)
        return {"job_id": job_id, "status": "render_failed"}
    except (
        OperationalError,
        OSError,
        SoftTimeLimitExceeded,
        TimeoutError,
    ) as exc:
        if failure_retries < 1:
            reset_render_for_retry(job_id, exc)
            _record_export_stage("render", "retry", started)
            raise self.retry(
                args=(job_id, failure_retries + 1),
                exc=exc,
                countdown=10 * (2**self.request.retries),
            )
        mark_render_failed(job_id, exc)
        _record_export_stage("render", "failure", started)
        raise
    except Exception as exc:
        mark_render_failed(job_id, exc)
        _record_export_stage("render", "failure", started)
        logger.exception(
            "quotation_export_render_failed",
            extra={
                "export_job_id": job_id,
                "duration_ms": _duration_ms(started),
            },
        )
        raise
    _record_export_stage("render", "success", started)
    logger.info(
        "quotation_export_render_finished",
        extra={
            "export_job_id": job_id,
            "status": result["status"],
            "duration_ms": _duration_ms(started),
        },
    )
    return result


@shared_task(
    bind=True,
    name="quotation.tasks.sync_document_replica",
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
    soft_time_limit=180,
    time_limit=210,
)
def sync_document_replica_task(
    self,
    export_job_id: str,
    asset_id: str,
    tracking_job_id: str | None = None,
):
    """Archive one rendered asset without rerunning document rendering."""
    import httpx
    from quotation.services.export_archive import (
        begin_export_upload_tracking,
        is_transient_feishu_error,
        mark_upload_failed,
        reset_upload_for_retry,
        sync_export_asset,
        update_export_upload_tracking,
    )
    from quotation.services.feishu_client import FeishuAPIError

    started = perf_counter()
    logger.info(
        "quotation_export_archive_started",
        extra={
            "export_job_id": export_job_id,
            "asset_id": asset_id,
            "attempt": self.request.retries + 1,
        },
    )

    def persist_retry_state(exc: Exception) -> None:
        try:
            with transaction.atomic():
                reset_upload_for_retry(export_job_id, exc)
                update_export_upload_tracking(
                    tracking_job_id,
                    SyncJobStatus.RETRYING,
                )
        except OperationalError:
            logger.exception(
                "quotation_export_archive_retry_state_failed",
                extra={
                    "export_job_id": export_job_id,
                    "asset_id": asset_id,
                },
            )

    def persist_terminal_failure(exc: Exception) -> str:
        try:
            with transaction.atomic():
                error_code = mark_upload_failed(export_job_id, exc)
                update_export_upload_tracking(
                    tracking_job_id,
                    SyncJobStatus.FAILED,
                    error_code=error_code,
                )
        except OperationalError as state_exc:
            logger.exception(
                "quotation_export_archive_terminal_state_failed",
                extra={
                    "export_job_id": export_job_id,
                    "asset_id": asset_id,
                },
            )
            if self.request.retries < self.max_retries:
                raise self.retry(
                    exc=state_exc,
                    countdown=15 * (2**self.request.retries),
                )
            raise
        return error_code

    try:
        tracking_job_id = begin_export_upload_tracking(
            export_job_id,
            asset_id,
            tracking_job_id,
        )
        result = sync_export_asset(export_job_id, asset_id)
        update_export_upload_tracking(
            tracking_job_id,
            SyncJobStatus.SUCCESS,
        )
    except FeishuAPIError as exc:
        if is_transient_feishu_error(exc) and self.request.retries < self.max_retries:
            persist_retry_state(exc)
            _record_export_stage("archive", "retry", started)
            raise self.retry(
                exc=exc,
                countdown=15 * (2**self.request.retries),
            )
        error_code = persist_terminal_failure(exc)
        _record_export_stage("archive", "failure", started)
        logger.warning(
            "quotation_export_archive_failed",
            extra={
                "export_job_id": export_job_id,
                "asset_id": asset_id,
                "error_code": error_code,
                "duration_ms": _duration_ms(started),
            },
        )
        return {"job_id": export_job_id, "status": "upload_failed"}
    except (
        httpx.TransportError,
        OperationalError,
        OSError,
        SoftTimeLimitExceeded,
        TimeoutError,
    ) as exc:
        if self.request.retries < self.max_retries:
            persist_retry_state(exc)
            _record_export_stage("archive", "retry", started)
            raise self.retry(
                exc=exc,
                countdown=15 * (2**self.request.retries),
            )
        persist_terminal_failure(exc)
        _record_export_stage("archive", "failure", started)
        raise
    except (LookupError, ValueError) as exc:
        persist_terminal_failure(exc)
        _record_export_stage("archive", "failure", started)
        return {"job_id": export_job_id, "status": "upload_failed"}
    except Exception as exc:
        persist_terminal_failure(exc)
        _record_export_stage("archive", "failure", started)
        logger.exception(
            "quotation_export_archive_failed",
            extra={
                "export_job_id": export_job_id,
                "asset_id": asset_id,
                "duration_ms": _duration_ms(started),
            },
        )
        raise
    _record_export_stage("archive", "success", started)
    logger.info(
        "quotation_export_archive_finished",
        extra={
            "export_job_id": export_job_id,
            "asset_id": asset_id,
            "status": result["status"],
            "duration_ms": _duration_ms(started),
        },
    )
    return result


@shared_task(
    bind=True,
    name="quotation.tasks.delete_owned_remote_file",
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
    soft_time_limit=120,
    time_limit=150,
)
def delete_owned_remote_file_task(
    self,
    cleanup_id: str,
):
    """Delete an unreferenced application-owned remote file asynchronously."""
    from quotation.services.storage_control import delete_remote_file_if_unreferenced

    try:
        status = delete_remote_file_if_unreferenced(
            cleanup_id,
        )
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(
                exc=exc,
                countdown=15 * (2**self.request.retries),
            )
        logger.exception(
            "quotation_remote_file_cleanup_failed",
            extra={"remote_file_cleanup_id": cleanup_id},
        )
        raise
    return {"status": status}


@shared_task(
    bind=True,
    name="quotation.tasks.parse_document",
    acks_late=True,
    max_retries=2,
    soft_time_limit=90,
    time_limit=120,
)
def parse_document_task(self, asset_id: str, actor_id: int | None = None):
    """Parse one document in an isolated, idempotent Celery task."""
    started = perf_counter()
    asset = DocumentAsset.objects.select_related("quotation").get(pk=asset_id)
    if asset.source == "feishu" and asset.feishu_file_token:
        peers = list(
            DocumentAsset.objects.filter(
                source="feishu",
                feishu_file_token=asset.feishu_file_token,
            )
            .select_related("quotation")
            .prefetch_related("parse_results")
        )

        def duplicate_priority(item):
            """Prefer a final classification over an older linked asset."""
            latest = max(
                item.parse_results.all(),
                key=lambda result: (result.created_at, result.id),
                default=None,
            )
            classified = bool(
                latest and latest.status == DocumentParseStatus.NOT_QUOTATION
            )
            return (
                classified,
                bool(item.quotation_id),
                item.created_at,
                item.id,
            )

        keeper = max(
            peers,
            key=duplicate_priority,
        )
        if keeper.id != asset.id:
            logger.info(
                "quotation_parse_duplicate_skipped",
                extra={
                    "asset_id": asset.id,
                    "keeper_asset_id": keeper.id,
                },
            )
            return {
                "asset_id": asset.id,
                "status": "duplicate_skipped",
                "keeper_asset_id": keeper.id,
            }
    actor = None
    if actor_id is not None:
        from django.contrib.auth import get_user_model

        actor = get_user_model().objects.filter(pk=actor_id).first()
    logger.info(
        "quotation_parse_started",
        extra={
            "asset_id": asset.id,
            "doc_type": asset.doc_type,
            "size_bytes": asset.size_bytes,
            "attempt": self.request.retries + 1,
        },
    )
    try:
        result, reused = parse_and_create_quotation(asset, actor=actor)
    except (OperationalError, SoftTimeLimitExceeded, TimeoutError) as exc:
        logger.warning(
            "quotation_parse_retrying",
            extra={
                "asset_id": asset.id,
                "duration_ms": _duration_ms(started),
                "error_type": type(exc).__name__,
            },
        )
        if self.request.retries < self.max_retries:
            raise self.retry(
                exc=exc,
                countdown=5 * (2**self.request.retries),
            )
        raise
    except Exception:
        logger.exception(
            "quotation_parse_failed",
            extra={
                "asset_id": asset.id,
                "duration_ms": _duration_ms(started),
            },
        )
        raise
    warning_codes = {
        warning.get("code")
        for warning in result.validation_warnings_json
        if isinstance(warning, dict)
    }
    if not result.quotation_id and "ocr_required" in warning_codes:
        active_ocr = SyncJob.objects.filter(
            asset=asset,
            job_type=SyncJobType.OCR,
            status__in={
                SyncJobStatus.PENDING,
                SyncJobStatus.QUEUED,
                SyncJobStatus.RUNNING,
                SyncJobStatus.RETRYING,
                SyncJobStatus.SUCCESS,
            },
        ).first()
        if active_ocr is None:
            active_ocr = SyncJob.objects.create(
                job_type=SyncJobType.OCR,
                status=SyncJobStatus.QUEUED,
                stage="queued",
                actor=actor,
                asset=asset,
                max_attempts=2,
            )
            ocr_task = ocr_document_task.apply_async(
                args=[active_ocr.id],
                queue="quotation_ocr",
            )
            active_ocr.celery_task_id = ocr_task.id
            active_ocr.save(update_fields=["celery_task_id", "updated_at"])
        logger.info(
            "quotation_ocr_queued",
            extra={"asset_id": asset.id, "ocr_job_id": active_ocr.id},
        )
    logger.info(
        "quotation_parse_finished",
        extra={
            "asset_id": asset.id,
            "quotation_id": result.quotation_id or "",
            "parse_status": result.status,
            "reused": reused,
            "duration_ms": _duration_ms(started),
        },
    )
    return {
        "asset_id": asset.id,
        "parse_result_id": result.id,
        "quotation_id": result.quotation_id,
        "status": result.status,
        "reused": reused,
    }


@shared_task(
    bind=True,
    name="quotation.tasks.ocr_document",
    acks_late=True,
    max_retries=1,
    soft_time_limit=180,
    time_limit=210,
)
def ocr_document_task(self, job_id: str):
    """OCR one scanned PDF in the optional isolated worker image."""
    from quotation.services.document_parsing.flexible_parser import (
        complete_document_parse,
    )
    from quotation.services.document_parsing.ocr_parser import extract_pdf_text_with_ocr
    from quotation.services.document_parsing.pdf_parser import parse_quotation_pdf_text
    from quotation.services.storage import resolve_document_path

    started = perf_counter()
    job = SyncJob.objects.select_related("asset", "actor").get(pk=job_id)
    asset = job.asset
    if asset is None:
        raise ValueError("OCR asset is missing")
    job.status = SyncJobStatus.RUNNING
    job.stage = "ocr"
    job.attempt_count = self.request.retries + 1
    job.started_at = job.started_at or timezone.now()
    job.heartbeat_at = timezone.now()
    job.save(
        update_fields=[
            "status",
            "stage",
            "attempt_count",
            "started_at",
            "heartbeat_at",
            "updated_at",
        ]
    )
    try:
        text = extract_pdf_text_with_ocr(resolve_document_path(asset.storage_key))
        parsed = parse_quotation_pdf_text(text)
        parsed = complete_document_parse(
            asset,
            resolve_document_path(asset.storage_key),
            parsed,
            extract_content=False,
        )
        result = asset.parse_results.order_by("-created_at", "-id").first()
        if result is None:
            raise ValueError("OCR parse result is missing")
        result.status = (
            DocumentParseStatus.NOT_QUOTATION
            if parsed.document_kind == "not_quotation"
            else (
                DocumentParseStatus.REVIEW_REQUIRED
                if parsed.validation_errors
                else DocumentParseStatus.READY
            )
        )
        result.normalized_json = parsed.quotation.model_dump(mode="json")
        result.source_totals_json = parsed.source_totals
        result.field_confidence_json = parsed.field_confidence
        result.validation_errors_json = parsed.validation_errors
        result.validation_warnings_json = [
            warning
            for warning in parsed.validation_warnings
            if warning.get("code") != "ocr_required"
        ] + [
            {
                "field": "document",
                "code": "ocr_used",
                "detail": "Text was extracted by the isolated OCR worker",
            }
        ]
        result.confidence = parsed.confidence
        result.error_message = ""
        result.save()
        result, reused = parse_and_create_quotation(asset, actor=job.actor)
        if (
            not result.quotation_id
            and result.status != DocumentParseStatus.NOT_QUOTATION
        ):
            raise ValueError("OCR result did not create a quotation")
        job.status = SyncJobStatus.SUCCESS
        job.stage = "finished"
        job.result_json = {
            "asset_id": asset.id,
            "parse_result_id": result.id,
            "quotation_id": result.quotation_id,
            "parse_status": result.status,
            "reused": reused,
        }
    except Exception as exc:
        job.status = SyncJobStatus.FAILED
        job.stage = "failed"
        job.error_code = "ocr_failed"
        job.error_message = str(exc)[:500]
        raise
    finally:
        job.finished_at = timezone.now()
        job.duration_ms = _duration_ms(started)
        job.save(
            update_fields=[
                "status",
                "stage",
                "result_json",
                "error_code",
                "error_message",
                "finished_at",
                "duration_ms",
                "updated_at",
            ]
        )
    return job.result_json


@shared_task(
    bind=True,
    name="quotation.tasks.sync_feishu_folder",
    acks_late=True,
    max_retries=2,
    soft_time_limit=600,
    time_limit=660,
)
def sync_feishu_folder_task(self, job_id: str, actor_id: int):
    """Discover Feishu files and enqueue isolated parser tasks."""
    started = perf_counter()
    cache.set(FEISHU_SYNC_LOCK_KEY, True, timeout=1500)
    job = SyncJob.objects.select_related("actor").get(pk=job_id)
    job.status = SyncJobStatus.RUNNING
    job.stage = "discovering"
    job.attempt_count = self.request.retries + 1
    job.started_at = job.started_at or timezone.now()
    job.heartbeat_at = timezone.now()
    job.save(
        update_fields=[
            "status",
            "stage",
            "attempt_count",
            "started_at",
            "heartbeat_at",
            "updated_at",
        ]
    )
    try:
        from quotation.views.feishu.files import FeishuFolderSyncView

        request = SimpleNamespace(user=job.actor)
        response = FeishuFolderSyncView()._sync(
            request,
            enqueue_parsing=True,
        )
        if response.status_code >= 500:
            raise RuntimeError("Feishu folder synchronization failed")
        if response.status_code >= 400:
            job.status = SyncJobStatus.FAILED
            job.error_code = f"http_{response.status_code}"
            job.error_message = str(
                response.data.get("detail") or "folder sync failed"
            )[:500]
        else:
            job.status = SyncJobStatus.SUCCESS
            job.result_json = dict(response.data)
        job.stage = "finished"
        job.finished_at = timezone.now()
        job.duration_ms = _duration_ms(started)
        job.save(
            update_fields=[
                "status",
                "stage",
                "result_json",
                "error_code",
                "error_message",
                "finished_at",
                "duration_ms",
                "updated_at",
            ]
        )
        if job.status == SyncJobStatus.FAILED:
            _record_feishu_sync_observability(
                job,
                result="failure",
                error_code=job.error_code,
            )
        elif job.result_json.get("errors"):
            _record_feishu_sync_observability(
                job,
                result="partial_failure",
            )
        else:
            _record_feishu_sync_observability(
                job,
                result="success",
            )
        return job.result_json or {"detail": job.error_message}
    except Exception as exc:
        if self.request.retries < self.max_retries:
            job.status = SyncJobStatus.RETRYING
            job.stage = "retrying"
            job.error_code = "folder_sync_retry"
            job.error_message = type(exc).__name__
            job.heartbeat_at = timezone.now()
            job.save(
                update_fields=[
                    "status",
                    "stage",
                    "error_code",
                    "error_message",
                    "heartbeat_at",
                    "updated_at",
                ]
            )
            raise self.retry(
                exc=exc,
                countdown=10 * (2**self.request.retries),
            )
        job.status = SyncJobStatus.FAILED
        job.stage = "failed"
        job.error_code = "folder_sync_failed"
        job.error_message = type(exc).__name__
        job.finished_at = timezone.now()
        job.duration_ms = _duration_ms(started)
        job.save(
            update_fields=[
                "status",
                "stage",
                "error_code",
                "error_message",
                "finished_at",
                "duration_ms",
                "updated_at",
            ]
        )
        _record_feishu_sync_observability(
            job,
            result="failure",
            error_code=job.error_code,
        )
        raise
    finally:
        if job.status != SyncJobStatus.RETRYING:
            cache.delete(FEISHU_SYNC_LOCK_KEY)
