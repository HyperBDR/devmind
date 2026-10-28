"""Register the AGIOne recent-data prefetch with the existing scheduler."""

from celery.schedules import crontab

from core.periodic_registry import TASK_REGISTRY


def register_periodic_tasks():
    """Refresh the last seven complete Shanghai days once a day."""
    TASK_REGISTRY.add(
        name='agione_recent_data_prefetch',
        task='agione_ops.tasks.prefetch_recent_native_data',
        schedule=crontab(hour=1, minute=20),
        enabled=True,
    )
    TASK_REGISTRY.add(
        name='agione_staging_cleanup',
        task='agione_ops.tasks.cleanup_native_staging',
        schedule=crontab(hour=2, minute=20),
        enabled=True,
    )
    TASK_REGISTRY.add(
        name='agione_snapshot_cleanup',
        task='agione_ops.tasks.cleanup_native_snapshots',
        schedule=crontab(hour=2, minute=40),
        enabled=True,
    )
