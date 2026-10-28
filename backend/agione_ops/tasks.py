"""UUID-only synthetic/native synchronization, never a periodic seed."""

from celery import shared_task
from celery.exceptions import Retry

from agione_ops.sync import execute_sync, mark_dispatch_failed


@shared_task(
    bind=True,
    name="agione_ops.tasks.run_sync",
    acks_late=True,
    max_retries=2,
)
def run_sync(self, run_id):
    """Execute one domain run and retry only its bounded temporary outcome."""

    result = execute_sync(run_id)
    if result.get("status") == "retrying" and "retryAfter" in result:
        try:
            raise self.retry(countdown=result["retryAfter"])
        except Retry:
            raise
        except Exception:
            mark_dispatch_failed(run_id)
            return {
                "status": "dispatch_failed",
                "errorCode": "DISPATCH_FAILED",
            }
    return result


@shared_task(name="agione_ops.tasks.refresh_native_finance", acks_late=True)
def refresh_native_finance(projection_id, run_id):
    """Refresh finance independently of the published call-log snapshot."""
    from agione_ops.native_finance_refresh import execute_finance

    return execute_finance(projection_id, run_id)
