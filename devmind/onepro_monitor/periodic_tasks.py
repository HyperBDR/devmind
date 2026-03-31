from celery.schedules import crontab

from core.periodic_registry import TASK_REGISTRY


def register_periodic_tasks():
    TASK_REGISTRY.add(
        "onepro_monitor.collect_due_sources",
        task="onepro_monitor.tasks.collect_due_sources",
        schedule=crontab(minute="*/10"),
        kwargs={},
        enabled=True,
    )
