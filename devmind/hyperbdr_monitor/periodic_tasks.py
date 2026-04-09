from celery.schedules import crontab

from core.periodic_registry import TASK_REGISTRY


def register_periodic_tasks():
    TASK_REGISTRY.add(
        "hyperbdr_monitor.collect_due_sources",
        task="hyperbdr_monitor.tasks.collect_due_sources",
        schedule=crontab(minute="*/10"),
        kwargs={},
        enabled=True,
    )
