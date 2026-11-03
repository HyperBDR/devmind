"""Verify abandoned syncs are fenced and visible to their owner."""

from datetime import timedelta
from unittest.mock import Mock, patch
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from agione_ops.models import (
    ConnectionGrant, NotificationDelivery, NotificationRules,
    SourceConnection, SyncRun,
)


class ProgressCountTests(TestCase):
    def test_collection_workers_have_hard_time_limits(self):
        from agione_ops.tasks import refresh_native_finance, run_sync

        self.assertIsNotNone(run_sync.time_limit)
        self.assertEqual(refresh_native_finance.time_limit, 1260)
        self.assertLess(run_sync.soft_time_limit, run_sync.time_limit)
        self.assertLess(refresh_native_finance.soft_time_limit,
                        refresh_native_finance.time_limit)

    def test_progress_count_is_reused_between_heartbeats(self):
        from types import SimpleNamespace

        from agione_ops.native_sync import _make_progress_counter

        count = Mock(side_effect=[10, 20, 30])
        run = SimpleNamespace(native_staging=SimpleNamespace(count=count))
        with patch("agione_ops.native_sync.time.monotonic", side_effect=[0, 2, 16, 17]):
            progress = _make_progress_counter(run)
            self.assertEqual(progress("calls"), 10)
            self.assertEqual(progress("calls"), 10)
            self.assertEqual(progress("calls"), 20)
            self.assertEqual(progress("staging"), 30)
        self.assertEqual(count.call_count, 3)

    def test_two_minute_heartbeat_loop_counts_at_most_eight_times(self):
        from types import SimpleNamespace

        from agione_ops.native_sync import _make_progress_counter

        count = Mock(return_value=10)
        run = SimpleNamespace(native_staging=SimpleNamespace(count=count))
        with patch("agione_ops.native_sync.time.monotonic", side_effect=range(120)):
            progress = _make_progress_counter(run)
            for _ in range(120):
                progress("calls")
        self.assertEqual(count.call_count, 8)


@override_settings(AGIONE_OPS_ALLOWED_ENDPOINT_HOSTS=["rules.example"])
class RecoveryConcurrencyTests(TransactionTestCase):
    def test_celery_worker_processes_watchdog_against_database(self):
        from celery import Celery
        from celery.contrib.testing.worker import start_worker
        from django.db import connection

        from agione_ops.tasks import recover_abandoned_native_syncs

        if connection.vendor != "postgresql":
            self.skipTest("Worker requires a shared PostgreSQL test database")
        user = get_user_model().objects.create_user(username="worker-owner")
        source = SourceConnection.objects.create(
            name="Worker", platform="pro", principal_kind="provider",
            source_kind="native", endpoint="https://rules.example",
            expected_tenant_id="tenant", enabled=True, created_by=user,
        )
        now = timezone.now()
        run = SyncRun.objects.create(
            connection=source, initiated_by=user,
            window_start=now - timedelta(days=7), window_end=now,
            idempotency_key="worker-test", request_hash="a" * 64,
            credential_version=source.credential_version,
            config_version=source.config_version, grant_revision=1,
            lease_epoch=1, status="running", phase="calls",
            heartbeat_at=now - timedelta(minutes=8),
        )
        SourceConnection.objects.filter(pk=source.pk).update(
            active_run_id=run.pk, lease_token=uuid4(), lease_epoch=1,
            lease_expires_at=now - timedelta(minutes=4),
        )
        app = Celery("isolated-recovery", broker="memory://",
                     backend="cache+memory://")
        app.conf.task_always_eager = False
        task = app.task(name="test.watchdog")(recover_abandoned_native_syncs.run)
        with start_worker(app, pool="solo", perform_ping_check=False):
            result = task.apply_async().get(timeout=15)
        self.assertEqual(result, 1)
        run.refresh_from_db()
        self.assertEqual((run.status, run.error_code),
                         ("interrupted", "LEASE_EXPIRED"))

    def test_concurrent_watchdogs_recover_only_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import close_old_connections, connection

        from agione_ops.sync import recover_expired_run

        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row locking is required")
        user = get_user_model().objects.create_user(username="race-owner")
        source = SourceConnection.objects.create(
            name="Race", platform="pro", principal_kind="provider",
            source_kind="native", endpoint="https://rules.example",
            expected_tenant_id="tenant", enabled=True, created_by=user,
        )
        now = timezone.now()
        run = SyncRun.objects.create(
            connection=source, initiated_by=user,
            window_start=now - timedelta(days=7), window_end=now,
            idempotency_key="race-test", request_hash="a" * 64,
            credential_version=source.credential_version,
            config_version=source.config_version, grant_revision=1,
            lease_epoch=1, status="running", phase="calls",
            heartbeat_at=now - timedelta(minutes=8),
        )
        SourceConnection.objects.filter(pk=source.pk).update(
            active_run_id=run.pk, lease_token=uuid4(), lease_epoch=1,
            lease_expires_at=now - timedelta(minutes=4),
        )
        barrier = Barrier(2)

        def recover():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                return recover_expired_run(source.pk, run.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: recover(), range(2)))
        self.assertEqual(sorted(results), [False, True])
        run.refresh_from_db()
        self.assertEqual(run.status, "interrupted")


@override_settings(AGIONE_OPS_ALLOWED_ENDPOINT_HOSTS=["rules.example"])
class ExpiredSyncTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="recovery-owner")
        for action in ("view_business", "run_sync"):
            self.user.user_permissions.add(Permission.objects.get(
                content_type__app_label="agione_ops", codename=action,
            ))
        self.connection = SourceConnection.objects.create(
            name="Recovery", platform="pro", principal_kind="provider",
            source_kind="native", endpoint="https://rules.example",
            expected_tenant_id="tenant", enabled=True, created_by=self.user,
        )
        self.grant = ConnectionGrant.objects.create(
            connection=self.connection, user=self.user, can_view=True, can_sync=True,
        )
        self.now = timezone.now().replace(microsecond=0)

    def make_active(self, *, expired=True, kind="auto"):
        key = ("agione-auto-20261103T004900Z-7" if kind == "auto"
               else "agione-scheduled-2026-11-03-7")
        run = SyncRun.objects.create(
            connection=self.connection, initiated_by=self.user,
            window_start=self.now - timedelta(days=7), window_end=self.now,
            idempotency_key=key, request_hash="a" * 64,
            credential_version=self.connection.credential_version,
            config_version=self.connection.config_version,
            grant_revision=self.grant.revision, lease_epoch=1,
            status="running", phase="calls", heartbeat_at=self.now - timedelta(minutes=8),
        )
        SourceConnection.objects.filter(pk=self.connection.pk).update(
            active_run_id=run.pk, lease_token=uuid4(), lease_epoch=1,
            lease_expires_at=self.now + timedelta(minutes=-4 if expired else 4),
        )
        return run

    def test_collection_failure_alert_is_deduplicated_and_opt_in(self):
        from agione_ops.notification_delivery import notify_collection_failure

        rules = NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            config={"enabled": True, "channel_id": str(uuid4())},
        )
        with patch("agione_ops.tasks.deliver_notification.delay") as send:
            with self.captureOnCommitCallbacks(execute=True):
                self.assertTrue(notify_collection_failure(
                    rules, "finance", "SOURCE_TIMEOUT",
                ))
                self.assertFalse(notify_collection_failure(
                    rules, "finance", "SOURCE_TIMEOUT",
                ))
            self.assertEqual(send.call_count, 1)
        delivery = NotificationDelivery.objects.get(rules=rules)
        self.assertIn("财务数据更新失败", delivery.payload["text"])
        rules.config["enabled"] = False
        self.assertFalse(notify_collection_failure(rules, "calls", "TIMEOUT"))

    def test_expired_run_is_interrupted_and_auto_status_updated(self):
        from agione_ops.sync import recover_expired_run
        run = self.make_active()
        rules = NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            last_auto_started_at=self.now - timedelta(minutes=8),
            last_auto_status="running",
        )
        with patch("django.utils.timezone.now", return_value=self.now):
            self.assertTrue(recover_expired_run(self.connection.pk))
        run.refresh_from_db()
        self.connection.refresh_from_db()
        rules.refresh_from_db()
        self.assertEqual((run.status, run.error_code), ("interrupted", "LEASE_EXPIRED"))
        self.assertIsNone(self.connection.active_run_id)
        self.assertEqual(rules.last_auto_status, "interrupted")
        self.assertEqual(rules.last_auto_error_code, "LEASE_EXPIRED")

    def test_live_lease_is_never_interrupted(self):
        from agione_ops.sync import recover_expired_run
        run = self.make_active(expired=False)
        with patch("django.utils.timezone.now", return_value=self.now):
            self.assertFalse(recover_expired_run(self.connection.pk))
        run.refresh_from_db()
        self.assertEqual(run.status, "running")

    def test_late_old_worker_cannot_overwrite_interrupted_status(self):
        from agione_ops.sync import recover_expired_run
        from agione_ops.tasks import _record_auto_run_result

        run = self.make_active()
        rules = NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            last_auto_started_at=self.now - timedelta(minutes=8),
            last_auto_status="running",
        )
        with patch("django.utils.timezone.now", return_value=self.now):
            recover_expired_run(self.connection.pk)
            _record_auto_run_result(run.pk, {"status": "skipped", "errorCode": "LEASE_LOST"})
        rules.refresh_from_db()
        self.assertEqual(rules.last_auto_status, "interrupted")
        self.assertEqual(rules.last_auto_error_code, "LEASE_EXPIRED")

    def test_duplicate_completion_does_not_hide_completed_inspection(self):
        from agione_ops.tasks import _record_auto_run_result

        run = self.make_active()
        SyncRun.objects.filter(pk=run.pk).update(status="succeeded")
        rules = NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            last_auto_started_at=self.now - timedelta(minutes=8),
            last_auto_status="succeeded",
        )
        _record_auto_run_result(run.pk, {"status": "succeeded"})
        rules.refresh_from_db()
        self.assertEqual(rules.last_auto_status, "succeeded")

    def test_orphaned_run_is_fenced_without_releasing_new_run(self):
        from agione_ops.sync import recover_expired_run
        run = self.make_active()
        new_id = uuid4()
        SourceConnection.objects.filter(pk=self.connection.pk).update(
            active_run_id=new_id, lease_token=uuid4(),
            lease_expires_at=self.now + timedelta(minutes=2),
        )
        with patch("django.utils.timezone.now", return_value=self.now):
            self.assertTrue(recover_expired_run(self.connection.pk, run.pk))
        run.refresh_from_db()
        self.connection.refresh_from_db()
        self.assertEqual(run.status, "interrupted")
        self.assertEqual(self.connection.active_run_id, new_id)

    def test_watchdog_fences_expired_run_before_next_auto_period(self):
        from agione_ops.tasks import recover_abandoned_native_syncs

        run = self.make_active()
        NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            last_auto_started_at=self.now - timedelta(minutes=8),
            last_auto_status="running",
            next_auto_refresh_at=self.now + timedelta(hours=2),
        )
        with patch("django.utils.timezone.now", return_value=self.now):
            self.assertEqual(recover_abandoned_native_syncs(), 1)
        run.refresh_from_db()
        self.assertEqual(run.status, "interrupted")

    def test_watchdog_scans_older_interrupted_runs_on_each_pass(self):
        from agione_ops.tasks import recover_abandoned_native_syncs

        runs = [
            SyncRun(
                connection=self.connection, initiated_by=self.user,
                window_start=self.now - timedelta(days=7), window_end=self.now,
                idempotency_key=f"agione-auto-{index}", request_hash="a" * 64,
                credential_version=self.connection.credential_version,
                config_version=self.connection.config_version,
                grant_revision=self.grant.revision, lease_epoch=1,
                status="interrupted", error_code="LEASE_EXPIRED",
                finished_at=self.now - timedelta(seconds=index),
            )
            for index in range(201)
        ]
        SyncRun.objects.bulk_create(runs)
        def handle(run_id):
            SyncRun.objects.filter(pk=run_id).update(recovery_handled=True)

        with patch("agione_ops.tasks.retry_abandoned_auto_sync",
                   side_effect=handle) as retry:
            recover_abandoned_native_syncs()
            self.assertEqual(retry.call_count, 200)
            recover_abandoned_native_syncs()
            recover_abandoned_native_syncs()
        self.assertEqual(retry.call_count, 201)
        self.assertEqual(
            sum(call.args[0] == runs[-1].pk for call in retry.call_args_list),
            1,
        )

    def test_exhausted_run_does_not_alert_again_after_midnight(self):
        from agione_ops.tasks import recover_abandoned_native_syncs

        run = self.make_active()
        SyncRun.objects.filter(pk=run.pk).update(
            status="interrupted", error_code="LEASE_EXPIRED", attempt=3,
            finished_at=self.now,
        )
        NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            config={"auto_refresh_enabled": True, "enabled": True,
                    "channel_id": str(uuid4())},
        )
        midnight = self.now.astimezone(ZoneInfo("Asia/Shanghai")).replace(
            hour=0, minute=0, second=0, microsecond=0,
        ) + timedelta(days=1)
        with patch("django.utils.timezone.now", return_value=midnight - timedelta(minutes=1)):
            recover_abandoned_native_syncs()
        with patch("django.utils.timezone.now", return_value=midnight + timedelta(minutes=1)):
            recover_abandoned_native_syncs()
        self.assertEqual(NotificationDelivery.objects.count(), 1)

    def test_dispatch_failure_updates_auto_status_and_queues_alert(self):
        from agione_ops.sync import _dispatch

        run = self.make_active()
        SyncRun.objects.filter(pk=run.pk).update(status="queued")
        rules = NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            config={"enabled": True, "channel_id": str(uuid4())},
            last_auto_started_at=self.now - timedelta(minutes=8),
            last_auto_status="queued",
        )
        with patch("agione_ops.tasks.run_sync.apply_async", side_effect=RuntimeError):
            _dispatch(run.pk)
        rules.refresh_from_db()
        self.assertEqual(rules.last_auto_status, "dispatch_failed")
        self.assertEqual(rules.last_auto_error_code, "DISPATCH_FAILED")
        self.assertEqual(NotificationDelivery.objects.count(), 1)

    def test_retry_dispatch_failure_updates_auto_status(self):
        from agione_ops.tasks import run_sync

        run = self.make_active()
        SyncRun.objects.filter(pk=run.pk).update(status="retrying")
        rules = NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            config={"enabled": True, "channel_id": str(uuid4())},
            last_auto_started_at=self.now - timedelta(minutes=8),
            last_auto_status="running",
        )
        with patch("agione_ops.tasks.execute_sync", return_value={
            "status": "retrying", "retryAfter": 2,
        }), patch.object(run_sync, "retry", side_effect=RuntimeError):
            run_sync.run(run.pk)
        rules.refresh_from_db()
        self.assertEqual(rules.last_auto_status, "dispatch_failed")
        self.assertEqual(NotificationDelivery.objects.count(), 1)

    def test_abandoned_auto_run_retries_without_waiting_for_next_period(self):
        from agione_ops.tasks import retry_abandoned_auto_sync

        run = self.make_active()
        run.status = "interrupted"
        run.error_code = "LEASE_EXPIRED"
        run.attempt = 1
        run.save(update_fields=["status", "error_code", "attempt"])
        NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            config={"auto_refresh_enabled": True},
        )
        with patch("agione_ops.sync.submit_sync", return_value=(run, True)) as submit:
            self.assertTrue(retry_abandoned_auto_sync(run.pk))
        self.assertEqual(submit.call_args.args[2:4], (run.window_start, run.window_end))
        self.assertTrue(submit.call_args.args[-1].endswith("-retry-1"))

    def test_busy_connection_defers_recovery_without_losing_it(self):
        from agione_ops.client import AgioneOpsError
        from agione_ops.tasks import recover_abandoned_native_syncs

        run = self.make_active()
        SyncRun.objects.filter(pk=run.pk).update(
            status="interrupted", error_code="LEASE_EXPIRED", attempt=1,
            finished_at=self.now,
        )
        NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            config={"auto_refresh_enabled": True},
        )
        with patch("django.utils.timezone.now", return_value=self.now), patch(
            "agione_ops.sync.submit_sync",
            side_effect=AgioneOpsError("CONNECTION_BUSY"),
        ) as submit:
            recover_abandoned_native_syncs()
            recover_abandoned_native_syncs()
        run.refresh_from_db()
        self.assertFalse(run.recovery_handled)
        self.assertEqual(run.recovery_next_check_at,
                         self.now + timedelta(minutes=5))
        self.assertEqual(submit.call_count, 1)

    @override_settings(AGIONE_OPS_NATIVE_ENABLED=True)
    def test_unclaimed_queued_runs_stop_after_three_expirations(self):
        from agione_ops.sync import recover_expired_run
        from agione_ops.tasks import retry_abandoned_auto_sync

        run = self.make_active()
        SyncRun.objects.filter(pk=run.pk).update(
            status="queued", attempt=0, heartbeat_at=None,
            created_at=self.now - timedelta(minutes=1),
        )
        NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            config={"auto_refresh_enabled": True},
            last_auto_started_at=self.now - timedelta(minutes=8),
        )
        for index in range(3):
            current = self.now + timedelta(minutes=index * 6)
            with patch("django.utils.timezone.now", return_value=current):
                SourceConnection.objects.filter(pk=self.connection.pk).update(
                    lease_expires_at=current - timedelta(minutes=4),
                )
                self.assertTrue(recover_expired_run(self.connection.pk, run.pk))
                self.assertEqual(retry_abandoned_auto_sync(run.pk), index < 2, f"expiration {index}")
                if index < 2:
                    run = SyncRun.objects.get(
                        idempotency_key=f"agione-auto-20261103T004900Z-7-retry-{index + 1}",
                    )
        self.assertEqual(SyncRun.objects.filter(connection=self.connection).count(), 3)

    def test_abandoned_auto_run_stops_after_three_attempts(self):
        from agione_ops.tasks import retry_abandoned_auto_sync

        run = self.make_active()
        run.status = "interrupted"
        run.error_code = "LEASE_EXPIRED"
        run.attempt = 3
        run.save(update_fields=["status", "error_code", "attempt"])
        NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            config={"auto_refresh_enabled": True},
        )
        with patch("agione_ops.sync.submit_sync") as submit:
            self.assertFalse(retry_abandoned_auto_sync(run.pk))
        submit.assert_not_called()

    @override_settings(AGIONE_OPS_NATIVE_ENABLED=True)
    def test_watchdog_creates_only_one_real_retry_without_notification(self):
        from agione_ops.sync import recover_expired_run
        from agione_ops.tasks import retry_abandoned_auto_sync

        run = self.make_active()
        SyncRun.objects.filter(pk=run.pk).update(attempt=1)
        NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            config={"auto_refresh_enabled": True},
            last_auto_started_at=self.now - timedelta(minutes=8),
        )
        with patch("django.utils.timezone.now", return_value=self.now):
            self.assertTrue(recover_expired_run(self.connection.pk))
            self.assertTrue(retry_abandoned_auto_sync(run.pk))
            self.assertFalse(retry_abandoned_auto_sync(run.pk))
        retry = SyncRun.objects.get(idempotency_key=run.idempotency_key + "-retry-1")
        self.assertEqual(retry.attempt, 1)
        self.assertEqual(retry.status, "queued")
        self.assertEqual(retry.window_start, run.window_start)
        self.assertEqual(retry.window_end, run.window_end)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.active_run_id, retry.pk)
        self.assertFalse(NotificationDelivery.objects.exists())

    def test_scheduled_retry_does_not_wait_forever_on_expired_run(self):
        from agione_ops.tasks import submit_recent_sync

        end = self.now.astimezone(ZoneInfo('Asia/Shanghai')).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        run = self.make_active(kind="scheduled")
        run.idempotency_key = f"agione-scheduled-{end.date().isoformat()}-7"
        run.save(update_fields=["idempotency_key"])
        with patch("django.utils.timezone.now", return_value=self.now):
            returned, created = submit_recent_sync(
                self.connection, self.user, end, scheduled=True,
            )
        self.assertFalse(created)
        returned.refresh_from_db()
        self.assertEqual(returned.status, "interrupted")
        with (patch("django.utils.timezone.now", return_value=self.now + timedelta(minutes=6)),
              patch("agione_ops.sync.submit_sync", return_value=(run, True)) as submit):
            _, created = submit_recent_sync(self.connection, self.user, end, scheduled=True)
        self.assertTrue(created)
        self.assertTrue(submit.call_args.args[-1].endswith("-retry-1"))

    def test_scheduled_collection_stops_after_three_worker_attempts(self):
        from agione_ops.tasks import submit_recent_sync

        end = self.now.astimezone(ZoneInfo('Asia/Shanghai')).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        run = self.make_active(kind="scheduled")
        SyncRun.objects.filter(pk=run.pk).update(
            idempotency_key=f"agione-scheduled-{end.date().isoformat()}-7",
            status="failed", error_code="SOURCE_TIMEOUT", attempt=3,
            finished_at=self.now - timedelta(minutes=30),
        )
        with (patch("django.utils.timezone.now", return_value=self.now),
              patch("agione_ops.sync.submit_sync") as submit):
            _, created = submit_recent_sync(self.connection, self.user, end, scheduled=True)
        self.assertFalse(created)
        submit.assert_not_called()

    @override_settings(AGIONE_OPS_NATIVE_ENABLED=True)
    def test_daily_report_marks_unclaimed_last_attempt_failed(self):
        from agione_ops.tasks import dispatch_scheduled_rule_syncs

        run = self.make_active(kind="scheduled")
        end = self.now.astimezone(ZoneInfo("Asia/Shanghai")).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        SyncRun.objects.filter(pk=run.pk).update(
            idempotency_key=f"agione-scheduled-{end.date().isoformat()}-7-retry-1",
            status="interrupted", error_code="LEASE_EXPIRED", attempt=2,
            heartbeat_at=None, finished_at=self.now - timedelta(minutes=30),
        )
        SourceConnection.objects.filter(pk=self.connection.pk).update(
            active_run_id=None, lease_token=None, lease_expires_at=None,
            verified_at=self.now,
        )
        rules = NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            config={"enabled": True, "schedule_time": "00:00"},
        )
        with patch("django.utils.timezone.now", return_value=self.now):
            dispatch_scheduled_rule_syncs()
        rules.refresh_from_db()
        self.assertEqual(rules.last_report_status, "failed")
        self.assertEqual(SyncRun.objects.filter(connection=self.connection).count(), 1)

    def test_rules_expose_recent_owner_run_without_payload(self):
        run = self.make_active()
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get(f"/api/v1/agione-ops/connections/{self.connection.pk}/notification-rules/")
        self.assertEqual(response.status_code, 200)
        rows = response.data["data"]["recentRuns"]
        self.assertEqual(rows[0]["runId"], str(run.pk))
        self.assertEqual(rows[0]["phase"], "calls")
        self.assertNotIn("request_hash", rows[0])

    def test_recent_runs_include_only_owners_finance_history(self):
        from agione_ops.native_sync_models import NativeFinanceRun

        run = self.make_active()
        other = get_user_model().objects.create_user(username="other-history")
        NativeFinanceRun.objects.create(
            connection=self.connection, user=other, run=run,
            generation=uuid4().hex, status="failed", error_code="PRIVATE",
        )
        own = NativeFinanceRun.objects.create(
            connection=self.connection, user=self.user, run=run,
            generation=uuid4().hex, status="succeeded", attempt=1,
            started_at=self.now, finished_at=self.now + timedelta(seconds=30),
        )
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get(f"/api/v1/agione-ops/connections/{self.connection.pk}/notification-rules/")
        rows = response.data["data"]["recentRuns"]
        finance = next(item for item in rows if item["trigger"] == "finance")
        self.assertEqual(finance["runId"], f"finance-{own.pk}")
        self.assertEqual(finance["status"], "succeeded")
        self.assertNotIn("PRIVATE", str(rows))
