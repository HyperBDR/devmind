from celery.schedules import crontab

from core.periodic_registry import TASK_REGISTRY


def register_periodic_tasks() -> None:
    """Register the durable remote-file cleanup dispatcher."""
    TASK_REGISTRY.add(
        name="quotation_remote_file_cleanup_dispatch",
        task="quotation.tasks.dispatch_remote_file_cleanups",
        schedule=crontab(minute="*"),
        args=(),
        kwargs={},
        queue="quotation_sync",
        enabled=True,
    )
