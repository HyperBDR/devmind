from __future__ import annotations

from types import SimpleNamespace

from django.utils import timezone
from quotation.models import DocumentAsset, ExportJob, ExportJobStatus
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


def _task_request(job: ExportJob):
    return SimpleNamespace(
        user=job.requested_by,
        audit_request_id=job.request_id,
        audit_trace_id=job.trace_id,
        META={"HTTP_X_QUOTATION_AUDIT_SOURCE": "automatic"},
    )


def sync_export_asset(export_job_id: str, asset_id: str) -> dict:
    """Upload one asset and finalize the job after every replica is synced."""
    job = ExportJob.objects.select_related(
        "quotation",
        "requested_by",
    ).get(pk=export_job_id)
    asset = DocumentAsset.objects.select_related(
        "quotation",
        "quotation_version",
    ).get(pk=asset_id, export_job=job)
    ExportJob.objects.filter(
        pk=job.id,
        status__in={
            ExportJobStatus.UPLOAD_QUEUED,
            ExportJobStatus.UPLOADING,
        },
    ).update(
        status=ExportJobStatus.UPLOADING,
        finished_at=None,
    )
    route = StorageRouter().resolve(
        scope_key=job.quotation.product_line,
        document_type=asset.doc_type,
    )
    create_replica(
        request=_task_request(job),
        asset=asset,
        route=route,
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
    ExportJob.objects.filter(pk=job_id).exclude(
        status=ExportJobStatus.COMPLETED
    ).update(
        status=ExportJobStatus.UPLOAD_FAILED,
        error_code=code[:100],
        error_message="Remote quotation archiving failed",
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
