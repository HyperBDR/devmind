"""Register the AGIOne recent-data prefetch with the existing scheduler."""

from celery.schedules import crontab, schedule

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
    TASK_REGISTRY.add(
        name="agione_notification_history_cleanup",
        task="agione_ops.tasks.cleanup_notification_history",
        schedule=crontab(hour=3, minute=0),
        enabled=True,
    )
    TASK_REGISTRY.add(
        name='agione_notification_delivery_retry',
        task='agione_ops.tasks.retry_notification_deliveries',
        schedule=schedule(300),
        enabled=True,
    )
    TASK_REGISTRY.add(
        name="agione_rule_schedule_dispatch",
        task="agione_ops.tasks.dispatch_scheduled_rule_syncs",
        schedule=schedule(60),
        enabled=True,
    )
    TASK_REGISTRY.add(
        name="agione_auto_refresh_dispatch",
        task="agione_ops.tasks.dispatch_auto_refresh_syncs",
        schedule=schedule(60),
        enabled=True,
    )
    TASK_REGISTRY.add(
        name="agione_recover_abandoned_native_syncs",
        task="agione_ops.tasks.recover_abandoned_native_syncs",
        schedule=schedule(60),
        enabled=True,
    )
