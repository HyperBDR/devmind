"""
Register SALS periodic tasks with the scheduler registry.

Called by the main project's register_periodic_tasks management command.
"""
from celery.schedules import crontab

from core.periodic_registry import TASK_REGISTRY


def register_periodic_tasks():
    TASK_REGISTRY.add(
        name="sals_incremental_sync",
        task="sals.tasks.sync_incidents_task",
        schedule=crontab(minute=30),
        args=(),
        kwargs={"full_sync": False},
        queue=None,
        enabled=True,
    )
