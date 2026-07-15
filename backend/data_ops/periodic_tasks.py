"""Register Data Ops periodic sync dispatcher."""
from __future__ import annotations

import os

from celery.schedules import crontab

from core.periodic_registry import TASK_REGISTRY


DEFAULT_SCHEDULE_MINUTE = os.getenv(
    "DATA_OPS_SCHEDULED_SYNC_MINUTE",
    "*/15",
)


def register_periodic_tasks() -> None:
    """Register dispatcher that queues due Feishu Bitable syncs."""
    TASK_REGISTRY.add(
        name="data_ops_scheduled_sync",
        task="data_ops.tasks.run_scheduled_sync",
        schedule=crontab(minute=DEFAULT_SCHEDULE_MINUTE),
        args=(),
        kwargs={},
        queue=None,
        enabled=True,
    )
