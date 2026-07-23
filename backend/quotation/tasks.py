from __future__ import annotations

import logging
from time import perf_counter
from types import SimpleNamespace

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.cache import cache
from django.db import OperationalError
from django.utils import timezone

from quotation.models import (
    DocumentAsset,
    DocumentParseStatus,
    SyncJob,
    SyncJobStatus,
    SyncJobType,
)
from quotation.services.document_parsing.service import (
    parse_and_create_quotation,
)

logger = logging.getLogger(__name__)

FEISHU_SYNC_LOCK_KEY = "quotation:feishu:archive-folder-sync"


def _duration_ms(started: float) -> int:
    return max(round((perf_counter() - started) * 1000), 0)


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
    asset = DocumentAsset.objects.select_related("quotation").get(
        pk=asset_id
    )
    if asset.source == "feishu" and asset.feishu_file_token:
        peers = list(
            DocumentAsset.objects.filter(
                source="feishu",
                feishu_file_token=asset.feishu_file_token,
            ).select_related("quotation").prefetch_related("parse_results")
        )

        def duplicate_priority(item):
            """Prefer a final classification over an older linked asset."""
            latest = max(
                item.parse_results.all(),
                key=lambda result: (result.created_at, result.id),
                default=None,
            )
            classified = bool(
                latest
                and latest.status == DocumentParseStatus.NOT_QUOTATION
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
            active_ocr.save(
                update_fields=["celery_task_id", "updated_at"]
            )
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
    from quotation.services.document_parsing.ocr_parser import (
        extract_pdf_text_with_ocr,
    )
    from quotation.services.document_parsing.pdf_parser import (
        parse_quotation_pdf_text,
    )
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
        text = extract_pdf_text_with_ocr(
            resolve_document_path(asset.storage_key)
        )
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
            else DocumentParseStatus.READY
        )
        result.normalized_json = parsed.quotation.model_dump(mode="json")
        result.source_totals_json = parsed.source_totals
        result.field_confidence_json = parsed.field_confidence
        result.validation_errors_json = []
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
        raise
    finally:
        if job.status != SyncJobStatus.RETRYING:
            cache.delete(FEISHU_SYNC_LOCK_KEY)
