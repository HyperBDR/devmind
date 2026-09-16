"""Background tasks for Invoice document synchronization."""

from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import OperationalError
from django.utils import timezone

from invoice.models import (
    InvoiceSyncRun,
    InvoiceSyncStatus,
    InvoiceSyncTrigger,
)
from invoice.services.feishu_sync import sync_invoice_feishu_folder
from quotation.services.feishu_client import FeishuAPIError


ACTIVE_SYNC_STATUSES = {
    InvoiceSyncStatus.PENDING,
    InvoiceSyncStatus.QUEUED,
    InvoiceSyncStatus.RUNNING,
}


def enqueue_invoice_feishu_sync(
    *,
    actor=None,
    trigger: str = InvoiceSyncTrigger.MANUAL,
) -> tuple[InvoiceSyncRun, bool]:
    """Queue one run or reuse the active run."""
    now = timezone.now()
    active = InvoiceSyncRun.objects.filter(
        status__in=ACTIVE_SYNC_STATUSES
    ).order_by("created_at").first()
    if (
        active is not None
        and active.status == InvoiceSyncStatus.RUNNING
        and active.started_at is not None
        and active.started_at
        < now - timedelta(
            seconds=max(settings.INVOICE_FEISHU_SYNC_STALE_SECONDS, 60)
        )
    ):
        active.status = InvoiceSyncStatus.FAILED
        active.error_message = "stale_run_recovered"
        active.finished_at = now
        active.save(
            update_fields=[
                "status",
                "error_message",
                "finished_at",
                "updated_at",
            ]
        )
        active = None
    if active is not None:
        return active, True
    run = InvoiceSyncRun.objects.create(
        trigger=trigger,
        requested_by=(
            actor if getattr(actor, "is_authenticated", False) else None
        ),
    )
    try:
        task = sync_invoice_feishu_task.apply_async(
            args=[run.id],
            queue="quotation_sync",
        )
    except Exception as exc:
        run.status = InvoiceSyncStatus.FAILED
        run.error_message = type(exc).__name__
        run.finished_at = timezone.now()
        run.save(
            update_fields=[
                "status",
                "error_message",
                "finished_at",
                "updated_at",
            ]
        )
        raise
    run.status = InvoiceSyncStatus.QUEUED
    run.save(update_fields=["status", "updated_at"])
    return run, False


@shared_task(
    bind=True,
    name="invoice.tasks.sync_feishu_folder",
    acks_late=True,
    max_retries=2,
    soft_time_limit=600,
    time_limit=660,
)
def sync_invoice_feishu_task(self, run_id: str):
    """Synchronize configured Feishu PDFs without remote mutations."""
    run = InvoiceSyncRun.objects.select_related("requested_by").get(
        pk=run_id
    )
    run.status = InvoiceSyncStatus.RUNNING
    run.started_at = run.started_at or timezone.now()
    run.error_message = ""
    run.save(
        update_fields=[
            "status",
            "started_at",
            "error_message",
            "updated_at",
        ]
    )
    try:
        counts = sync_invoice_feishu_folder(actor=run.requested_by)
    except (FeishuAPIError, OperationalError, OSError, TimeoutError) as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(
                exc=exc,
                countdown=15 * (2**self.request.retries),
            )
        run.status = InvoiceSyncStatus.FAILED
        run.error_message = type(exc).__name__
        run.finished_at = timezone.now()
        run.save(
            update_fields=[
                "status",
                "error_message",
                "finished_at",
                "updated_at",
            ]
        )
        raise
    for field, value in counts.items():
        setattr(run, field, value)
    run.status = InvoiceSyncStatus.SUCCESS
    run.finished_at = timezone.now()
    run.save(
        update_fields=[
            *counts.keys(),
            "status",
            "finished_at",
            "updated_at",
        ]
    )
    return {"run_id": run.id, **counts}


@shared_task(
    name="invoice.tasks.dispatch_feishu_sync",
    acks_late=True,
)
def dispatch_invoice_feishu_sync():
    """Queue the periodic system Invoice synchronization."""
    run, reused = enqueue_invoice_feishu_sync(
        trigger=InvoiceSyncTrigger.PERIODIC,
    )
    return {"run_id": run.id, "reused": reused}
