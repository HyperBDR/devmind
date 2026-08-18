from celery.schedules import crontab

from core.periodic_registry import TASK_REGISTRY


def register_periodic_tasks() -> None:
    """Register document lifecycle cleanup tasks."""
    TASK_REGISTRY.add(
        name="quotation_remote_file_cleanup_dispatch",
        task="quotation.tasks.dispatch_remote_file_cleanups",
        schedule=crontab(minute="*"),
        args=(),
        kwargs={},
        queue="quotation_sync",
        enabled=True,
    )
    TASK_REGISTRY.add(
        name="quotation_document_retention_purge",
        task="quotation.tasks.purge_archived_documents",
        schedule=crontab(hour="3", minute="20"),
        args=(),
        kwargs={"dry_run": False},
        queue="quotation_sync",
        enabled=True,
    )
