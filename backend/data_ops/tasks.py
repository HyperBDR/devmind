from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


class SyncTaskDispatchError(Exception):
    """Raised when a Celery sync task cannot be dispatched."""

    def __init__(self, job, original_error: Exception):
        self.job = job
        self.original_error = original_error
        super().__init__(str(original_error))


def mark_sync_job_dispatch_failed(job, exc: Exception) -> None:
    """Persist dispatch failures so pending jobs do not block scheduling."""
    from .models import SyncStatus

    job.status = SyncStatus.FAILED
    job.finished_at = timezone.now()
    job.error_message = f"同步任务投递失败：{exc}"[:2000]
    job.save(
        update_fields=[
            "status",
            "finished_at",
            "error_message",
        ]
    )


def dispatch_sync_task(task, job, **kwargs):
    """Dispatch a Celery sync task and mark the job failed on broker errors."""
    try:
        async_result = task.delay(**kwargs)
    except Exception as exc:
        mark_sync_job_dispatch_failed(job, exc)
        raise SyncTaskDispatchError(job, exc) from exc

    job.celery_task_id = async_result.id
    job.save(update_fields=["celery_task_id"])
    return async_result


@shared_task(
    name="data_ops.tasks.run_full_sync",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
    acks_late=True,
)
def run_full_sync_task(self, *, job_id: str | None = None) -> dict:
    from .services.feishu.sync import run_full_sync

    logger.info("data_ops.run_full_sync start", extra={"job_id": job_id})
    try:
        result = run_full_sync(job_id=job_id)
    except Exception as exc:
        logger.exception("data_ops.run_full_sync failed")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        raise
    logger.info("data_ops.run_full_sync done: %s", result)
    return result


@shared_task(
    name="data_ops.tasks.run_incremental_sync",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
    acks_late=True,
)
def run_incremental_sync_task(
    self,
    *,
    source_key: str,
    job_id: str | None = None,
) -> dict:
    from .services.feishu.sync import run_incremental_sync

    logger.info(
        "data_ops.run_incremental_sync start",
        extra={"source_key": source_key, "job_id": job_id},
    )
    try:
        result = run_incremental_sync(source_key=source_key, job_id=job_id)
    except Exception as exc:
        logger.exception("data_ops.run_incremental_sync failed")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        raise
    logger.info("data_ops.run_incremental_sync done: %s", result)
    return result


@shared_task(
    name="data_ops.tasks.run_table_sync",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
    acks_late=True,
)
def run_table_sync_task(
    self,
    *,
    source_key: str,
    table_key: str,
    job_id: str | None = None,
    mark_scheduled: bool = False,
) -> dict:
    from .models import SyncStatus
    from .services.feishu.config import (
        get_bitable_collection_config_by_key,
        mark_config_scheduled,
    )
    from .services.feishu.sync import run_table_sync

    logger.info(
        "data_ops.run_table_sync start",
        extra={
            "source_key": source_key,
            "table_key": table_key,
            "job_id": job_id,
        },
    )
    try:
        result = run_table_sync(
            source_key=source_key,
            table_key=table_key,
            job_id=job_id,
        )
        if (
            mark_scheduled
            and not result.get("skipped")
            and result.get("status") in {SyncStatus.OK, SyncStatus.WARNING}
        ):
            config = get_bitable_collection_config_by_key(
                source_key,
                table_key,
            )
            mark_config_scheduled(config)
    except Exception as exc:
        logger.exception("data_ops.run_table_sync failed")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        raise
    logger.info("data_ops.run_table_sync done: %s", result)
    return result


@shared_task(
    name="data_ops.tasks.run_scheduled_sync",
    bind=True,
    max_retries=0,
    acks_late=True,
)
def run_scheduled_sync_task(self) -> dict:
    from .models import SyncJob, SyncStatus
    from .services.feishu.config import due_bitable_collection_configs

    queued = []
    failed = []
    for config in due_bitable_collection_configs():
        job = SyncJob.objects.create(
            source_key=config.source_key,
            table_key=config.table_key,
            status=SyncStatus.PENDING,
        )
        try:
            dispatch_sync_task(
                run_table_sync_task,
                job,
                source_key=config.source_key,
                table_key=config.table_key,
                job_id=str(job.id),
                mark_scheduled=True,
            )
        except SyncTaskDispatchError:
            failed.append(
                {
                    "source_key": config.source_key,
                    "table_key": config.table_key,
                    "job_id": str(job.id),
                }
            )
            continue
        queued.append(
            {
                "source_key": config.source_key,
                "table_key": config.table_key,
                "job_id": str(job.id),
            }
        )
    return {"queued": queued, "failed": failed}
