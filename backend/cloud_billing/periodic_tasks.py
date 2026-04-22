"""
Register this app's periodic tasks with the scheduler registry.

Called by the main project's register_periodic_tasks management command.
"""
from celery.schedules import crontab

from core.periodic_registry import TASK_REGISTRY


def register_periodic_tasks():
    TASK_REGISTRY.add(
        name="cloud_billing_hourly_collection",
        task="cloud_billing.tasks.collect_billing_data",
        schedule=crontab(minute=10),
        args=(),
        kwargs={"user_id": 0},
        queue=None,
        enabled=True,
    )
