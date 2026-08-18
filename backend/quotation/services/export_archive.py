from __future__ import annotations

from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from quotation.access import UploadAuthorizationError, can_upload_to_folder
from quotation.models import (
    EXPORT_ARCHIVE_SYNC_STAGE,
    DocumentAsset,
    ExportJob,
    ExportJobStatus,
    Quotation,
    SyncJob,
    SyncJobStatus,
    SyncJobType,
)
from quotation.services.storage_control import (
    StorageRouter,
    active_replica_for_asset,
    create_replica,
)

TRANSIENT_FEISHU_CODES = {
    99991400,
    99991403,
    99991663,
}

FEISHU_IP_ALLOWLIST_ERROR = 99991401


def prepare_export_upload_tracking(
    job: ExportJob,
    assets: list[DocumentAsset],
) -> dict[str, SyncJob]:
    """Persist one dispatch marker for every asset before enqueueing."""
    trackers = {}
    with transaction.atomic():
        Quotation.objects.select_for_update().get(pk=job.quotation_id)
        for asset in assets:
            tracker = (
                SyncJob.objects.select_for_update()
                .filter(
                    job_type=SyncJobType.UPLOAD,
                    asset=asset,
                    stage=EXPORT_ARCHIVE_SYNC_STAGE,
                )
                .order_by("-created_at", "-id")
                .first()
            )
            if tracker is None:
                tracker = SyncJob.objects.create(
                    job_type=SyncJobType.UPLOAD,
                    status=SyncJobStatus.QUEUED,
                    quotation=job.quotation,
                    asset=asset,
                    actor=job.requested_by,
                    request_id=job.request_id,
                    trace_id=job.trace_id,
                    stage=EXPORT_ARCHIVE_SYNC_STAGE,
                )
            else:
                tracker.status = SyncJobStatus.QUEUED
                tracker.celery_task_id = ""
                tracker.error_code = ""
                tracker.error_message = ""
                tracker.started_at = None
                tracker.finished_at = None
                tracker.save(
                    update_fields=[
                        "status",
                        "celery_task_id",
                        "error_code",
                        "error_message",
                        "started_at",
                        "finished_at",
                        "updated_at",
                    ]
                )
            trackers[asset.id] = tracker
    return trackers


def begin_export_upload_tracking(
    export_job_id: str,
    asset_id: str,
    tracking_job_id: str | None = None,
) -> str:
    """Mark a queued asset upload as running, including old task messages."""
    tracker = None
    if tracking_job_id:
        tracker = SyncJob.objects.filter(
            pk=tracking_job_id,
            job_type=SyncJobType.UPLOAD,
            asset_id=asset_id,
            asset__export_job_id=export_job_id,
            stage=EXPORT_ARCHIVE_SYNC_STAGE,
        ).first()
    if tracker is None:
        job = ExportJob.objects.select_related("requested_by").get(
            pk=export_job_id,
        )
        asset = DocumentAsset.objects.get(pk=asset_id, export_job=job)
        trackers = prepare_export_upload_tracking(job, [asset])
        tracker = trackers[asset.id]
    tracker.status = SyncJobStatus.RUNNING
    tracker.started_at = tracker.started_at or timezone.now()
    tracker.finished_at = None
    tracker.save(
        update_fields=[
            "status",
            "started_at",
            "finished_at",
            "updated_at",
        ]
    )
    return tracker.id


def update_export_upload_tracking(
    tracking_job_id: str,
    status: str,
    *,
    error_code: str = "",
) -> None:
    """Persist the terminal or retry state of one archive task."""
    terminal = status in {
        SyncJobStatus.SUCCESS,
        SyncJobStatus.FAILED,
    }
    SyncJob.objects.filter(
        pk=tracking_job_id,
        stage=EXPORT_ARCHIVE_SYNC_STAGE,
    ).update(
        status=status,
        error_code=error_code[:100],
        finished_at=timezone.now() if terminal else None,
        updated_at=timezone.now(),
    )


def _task_request(job: ExportJob):
    return SimpleNamespace(
        user=job.requested_by,
        audit_request_id=job.request_id,
        audit_trace_id=job.trace_id,
        META={"HTTP_X_QUOTATION_AUDIT_SOURCE": "automatic"},
    )


def sync_export_asset(export_job_id: str, asset_id: str) -> dict:
    """Upload one asset and finalize the job after every replica is synced."""
    quotation_id = ExportJob.objects.values_list(
        "quotation_id",
        flat=True,
    ).get(pk=export_job_id)
    with transaction.atomic():
        Quotation.objects.select_for_update().get(pk=quotation_id)
        job = (
            ExportJob.objects.select_for_update()
            .select_related("requested_by")
            .get(pk=export_job_id)
        )
        asset = DocumentAsset.objects.select_related(
            "quotation",
            "quotation_version",
        ).get(pk=asset_id, export_job=job)
        if job.status in {
            ExportJobStatus.UPLOAD_QUEUED,
            ExportJobStatus.UPLOADING,
        }:
            job.status = ExportJobStatus.UPLOADING
            job.finished_at = None
            job.save(update_fields=["status", "finished_at", "updated_at"])
        if job.requested_by_id and not can_upload_to_folder(
            job.requested_by,
            job.archive_folder_token,
        ):
            raise UploadAuthorizationError(
                "Directory upload permission is no longer active"
            )
    route = StorageRouter().resolve(
        scope_key=job.quotation.product_line,
        document_type=asset.doc_type,
    )
    create_replica(
        request=_task_request(job),
        asset=asset,
        route=route,
        folder_token=job.archive_folder_token,
    )
    assets = list(
        job.assets.select_related(
            "quotation",
            "quotation_version",
        ).prefetch_related("replicas")
    )
    replicas = [active_replica_for_asset(candidate) for candidate in assets]
    all_synced = all(
        replica is not None and replica.content_hash == candidate.content_hash
        for candidate, replica in zip(assets, replicas)
    )
    if all_synced:
        ExportJob.objects.filter(pk=job.id).update(
            status=ExportJobStatus.COMPLETED,
            error_code="",
            error_message="",
            finished_at=timezone.now(),
        )
    next_status = (
        ExportJob.objects.filter(pk=job.id)
        .values_list(
            "status",
            flat=True,
        )
        .get()
    )
    return {"job_id": job.id, "status": next_status}


def mark_upload_failed(job_id: str, exc: Exception) -> str:
    raw_code = getattr(exc, "code", None)
    code = f"feishu_{raw_code}" if raw_code is not None else "upload_failed"
    if raw_code == FEISHU_IP_ALLOWLIST_ERROR:
        error_message = (
            "Feishu rejected the server IP. Add the server public IPv4 "
            "address to the Feishu app IP allowlist, then retry the upload."
        )
    else:
        error_message = "Remote quotation archiving failed"
    ExportJob.objects.filter(pk=job_id).exclude(
        status=ExportJobStatus.COMPLETED
    ).update(
        status=ExportJobStatus.UPLOAD_FAILED,
        error_code=code[:100],
        error_message=error_message,
        finished_at=timezone.now(),
    )
    return code


def reset_upload_for_retry(job_id: str, exc: Exception) -> None:
    raw_code = getattr(exc, "code", None)
    code = f"feishu_{raw_code}" if raw_code is not None else "upload_retry"
    ExportJob.objects.filter(
        pk=job_id,
        status__in={
            ExportJobStatus.UPLOAD_QUEUED,
            ExportJobStatus.UPLOADING,
        },
    ).update(
        status=ExportJobStatus.UPLOAD_QUEUED,
        error_code=code[:100],
        error_message="Transient archive failure; retry queued",
        finished_at=None,
    )


def is_transient_feishu_error(exc: Exception) -> bool:
    return getattr(exc, "code", None) in TRANSIENT_FEISHU_CODES
