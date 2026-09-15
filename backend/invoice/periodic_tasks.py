from django.conf import settings

from core.periodic_registry import TASK_REGISTRY


def register_periodic_tasks() -> None:
    """Register read-only Invoice synchronization."""
    TASK_REGISTRY.add(
        name="invoice_feishu_periodic_sync",
        task="invoice.tasks.dispatch_feishu_sync",
        schedule=max(settings.INVOICE_FEISHU_SYNC_INTERVAL_SECONDS, 60),
        args=(),
        kwargs={},
        queue="quotation_sync",
        enabled=settings.INVOICE_FEISHU_PERIODIC_SYNC_ENABLED,
    )
