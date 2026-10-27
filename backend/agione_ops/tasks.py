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


def submit_recent_sync(connection, user, end):
    """Submit a bounded, auditable seven-day prefetch for one connection."""
    from datetime import timedelta

    from agione_ops.sync import submit_sync

    return submit_sync(
        connection, user, end - timedelta(days=7), end, 'Asia/Shanghai',
        'agione-prefetch-' + end.date().isoformat(),
    )


@shared_task(name='agione_ops.tasks.prefetch_recent_native_data')
def prefetch_recent_native_data():
    """Use an active authorized grant; busy or unconfigured sources are skipped."""
    import logging
    from zoneinfo import ZoneInfo

    from django.conf import settings
    from django.utils import timezone
    from rest_framework.exceptions import APIException

    from agione_ops.models import ConnectionGrant, SourceConnection
    from agione_ops.permissions import has_action

    if not getattr(settings, 'AGIONE_OPS_NATIVE_ENABLED', False):
        return
    end = timezone.now().astimezone(ZoneInfo('Asia/Shanghai')).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    connections = SourceConnection.objects.filter(
        enabled=True, source_kind='native', verified_at__isnull=False,
    )
    for connection in connections.iterator():
        grants = ConnectionGrant.objects.filter(
            connection=connection, can_view=True, can_sync=True,
            user__is_active=True,
        ).select_related('user').order_by('user_id')
        for grant in grants:
            if not (has_action(grant.user, 'view_business') and
                    has_action(grant.user, 'run_sync')):
                continue
            try:
                submit_recent_sync(connection, grant.user, end)
            except APIException as error:
                logging.getLogger(__name__).info(
                    'AGIOne prefetch skipped: %s',
                    getattr(error, 'code', 'unavailable'),
                )
            break


@shared_task(name='agione_ops.tasks.cleanup_native_staging')
def cleanup_native_staging():
    """Remove old terminal staging, preserving published snapshots."""
    from datetime import timedelta

    from django.conf import settings
    from django.db.models import Q
    from django.utils import timezone

    from agione_ops.native_sync_models import NativeStagedRecord

    days = getattr(settings, 'AGIONE_OPS_STAGING_RETENTION_DAYS', 30)
    if type(days) is not int or days < 7:
        days = 30
    cutoff = timezone.now() - timedelta(days=days)
    rows = NativeStagedRecord.objects.filter(
        Q(run__status='succeeded',
          run__published_version__native_snapshot__isnull=False)
        | Q(run__status__in=['failed', 'revoked', 'interrupted',
                             'dispatch_failed']),
        run__finished_at__lt=cutoff,
    )
    total = 0
    while True:
        ids = list(rows.order_by('pk').values_list('pk', flat=True)[:1000])
        if not ids:
            return total
        count, _ = NativeStagedRecord.objects.filter(pk__in=ids).delete()
        total += count
