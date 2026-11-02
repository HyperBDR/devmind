"""Optional safe projection into the existing shared task platform."""

import logging

from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


def _tracker():
    """Use the installed public adapter, never a parallel task framework."""

    from agentcore_task.adapters.django import TaskStatus, TaskTracker

    return TaskTracker, TaskStatus


def project_run(run_id):
    """Projection is opt-in and cannot change domain transaction outcomes."""

    if not getattr(settings, "AGIONE_OPS_TASK_PROJECTION_ENABLED", False):
        return False
    from agione_ops.models import SyncRun

    try:
        with transaction.atomic():
            run = SyncRun.objects.select_related("initiated_by").get(pk=run_id)
            tracker, statuses = _tracker()
            status = {
                "queued": statuses.PENDING,
                "running": statuses.STARTED,
                "retrying": statuses.RETRY,
                "succeeded": statuses.SUCCESS,
                "revoked": statuses.REVOKED,
                "failed": statuses.FAILURE,
                "interrupted": statuses.FAILURE,
                "dispatch_failed": statuses.FAILURE,
            }[run.status]
            metadata = {"domain_run_id": str(run.pk)}
            task_id = run.celery_id or str(run.pk)
            tracker.register_task(
                task_id=task_id,
                task_name="agione_ops.tasks.run_sync",
                module="agione_ops",
                task_kwargs={"run_id": str(run.pk)},
                created_by=run.initiated_by,
                metadata=metadata,
                initial_status=status,
            )
            tracker.update_task_status(
                task_id,
                status,
                metadata=metadata,
            )
        return True
    except Exception:
        logger.warning(
            "AGIOne task projection unavailable; domain run retained."
        )
        return False
