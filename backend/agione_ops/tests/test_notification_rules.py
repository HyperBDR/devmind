"""Validate persisted notification rules and completed-window analysis."""

from contextlib import ExitStack
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from agentcore_notifier.adapters.django.models import NotificationChannel
from agione_ops.models import (
    ConnectionGrant,
    NotificationDelivery,
    NotificationRules,
    SourceConnection,
)
from agione_ops.notification_rules import (
    NotificationRulesSerializer,
    analyze_rows,
    collect_interval_failure_events,
    collect_failure_alerts,
    extend_manual_window,
    notification_trigger_from_key,
    notification_trigger_for_run,
    required_collection_days,
    scheduled_date_from_key,
)

ZONE = ZoneInfo("Asia/Shanghai")


class NotificationRuleUnitTests(SimpleTestCase):
    """Exercise rule validation and complete-window calculations."""

    def test_default_window_and_enabled_channel_required(self):
        serializer = NotificationRulesSerializer(data={})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["analysis_days"], 7)
        self.assertEqual(serializer.validated_data["schedule_time"], "01:20")
        self.assertFalse(serializer.validated_data["enabled"])
        invalid = NotificationRulesSerializer(data={"enabled": True})
        self.assertFalse(invalid.is_valid())
        invalid_time = NotificationRulesSerializer(
            data={"schedule_time": "24:10"},
        )
        self.assertFalse(invalid_time.is_valid())
        self.assertEqual(
            serializer.validated_data["event_window_minutes"],
            120,
        )
        self.assertEqual(
            serializer.validated_data["failure_rate_percent"],
            80,
        )
        self.assertEqual(
            serializer.validated_data["min_balance_failure_count"],
            1,
        )
        self.assertEqual(serializer.validated_data["auto_refresh_hours"], 3)
        for hours in (2, 3, 4):
            candidate = NotificationRulesSerializer(
                data={"auto_refresh_hours": hours},
            )
            self.assertTrue(candidate.is_valid(), candidate.errors)
        invalid_period = NotificationRulesSerializer(
            data={"auto_refresh_hours": 5},
        )
        self.assertFalse(invalid_period.is_valid())

    def test_latest_complete_window_extends_to_manual_refresh_time(self):
        now = datetime(2026, 10, 29, 9, 16, 30, tzinfo=ZONE)
        window = {
            "start": datetime(2026, 10, 22, tzinfo=ZONE),
            "end_exclusive": datetime(2026, 10, 29, tzinfo=ZONE),
            "timezone": "Asia/Shanghai",
        }

        extended = extend_manual_window(window, now)

        self.assertEqual(extended["start"], window["start"])
        self.assertEqual(extended["end_exclusive"], now)
        self.assertEqual(window["end_exclusive"].hour, 0)

    def test_scheduled_date_is_only_read_from_scheduled_run_key(self):
        self.assertEqual(
            scheduled_date_from_key(
                "agione-scheduled-2026-10-29-7-retry-2",
            ),
            "2026-10-29",
        )
        self.assertIsNone(
            scheduled_date_from_key("agione-prefetch-2026-10-29-7"),
        )
        self.assertEqual(
            notification_trigger_from_key(
                "agione-scheduled-2026-10-29-7",
            ),
            "scheduled",
        )
        self.assertEqual(
            notification_trigger_from_key(
                "agione-prefetch-2026-10-29-7",
            ),
            "automatic",
        )
        self.assertEqual(
            notification_trigger_from_key("browser-generated-key"),
            "manual",
        )
        now = datetime(2026, 10, 29, 9, 30, tzinfo=ZONE)
        self.assertEqual(
            notification_trigger_for_run(
                "browser-generated-key",
                now - timedelta(days=1),
                now,
            ),
            "historical",
        )
        self.assertEqual(
            notification_trigger_for_run(
                "browser-generated-key",
                now - timedelta(minutes=2),
                now,
            ),
            "manual",
        )

    def test_failure_alert_uses_recent_window_and_rate_threshold(self):
        end = datetime(2026, 10, 29, 9, 30, tzinfo=ZONE)
        rows = [
            {
                "customer_id": "recent",
                "occurred_at": (
                    end - timedelta(minutes=index + 1)
                ).isoformat(),
                "result": "FAILURE" if index < 8 else "SUCCESS",
                "failureKey": "source:1",
            }
            for index in range(10)
        ]
        rows.extend(
            {
                "customer_id": "old",
                "occurred_at": (
                    end - timedelta(hours=2, minutes=index)
                ).isoformat(),
                "result": "FAILURE",
                "failureKey": "source:1",
            }
            for index in range(10)
        )

        result = analyze_rows(
            rows,
            {"recent", "old"},
            {
                "analysis_days": 7,
                "event_window_minutes": 60,
                "failure_rate_percent": 80,
                "min_failure_count": 6,
                "continuous_failure": True,
                "balance_failure": False,
            },
            end,
            event_only=True,
        )

        self.assertEqual(
            [item["customer_id"] for item in result["alerts"]],
            ["recent"],
        )
        self.assertEqual(result["alerts"][0]["failure_rate_percent"], 80.0)
        self.assertEqual(
            result["event_start"],
            (end - timedelta(minutes=60)).isoformat(),
        )

    def test_interval_scan_finds_anomaly_that_recovered_before_next_run(self):
        start = datetime(2026, 10, 29, 8, 0, tzinfo=ZONE)
        end = start + timedelta(hours=3)
        rows = [
            {
                "customer_id": "transient",
                "occurred_at": (
                    start + timedelta(minutes=60 + index * 3)
                ).isoformat(),
                "result": "FAILURE",
                "failureKey": "source:3",
            }
            for index in range(6)
        ]
        rows.extend([
            {
                "customer_id": "transient",
                "occurred_at": (
                    start + timedelta(minutes=100 + index)
                ).isoformat(),
                "result": "SUCCESS",
                "failureKey": "",
            }
            for index in range(20)
        ])

        events = collect_interval_failure_events(
            rows,
            {
                "event_window_minutes": 30,
                "min_failure_count": 6,
                "failure_rate_percent": 80,
                "continuous_failure": True,
                "balance_failure": True,
                "min_balance_failure_count": 1,
            },
            start,
            end,
            {"transient": "Transient tenant"},
        )

        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]["recovered"])
        self.assertEqual(events[0]["failure_count"], 6)
        self.assertIn("balance_failure", events[0]["reasons"])

    def test_failure_threshold_and_unknown_result(self):
        rows = [
            {
                "customer_id": "1",
                "result": "FAILURE",
                "failureKey": "source:3",
            }
            for _ in range(6)
        ]
        self.assertTrue(collect_failure_alerts(rows, {})[0]["blocked"])
        rows.append({"customer_id": "1", "result": "UNKNOWN"})
        alerts = collect_failure_alerts(
            rows,
            {
                "balance_failure": False,
                "failure_rate_percent": 100,
            },
        )
        self.assertEqual(alerts, [])

    def test_interval_scan_handles_large_successful_tenant(self):
        start = datetime(2026, 10, 29, 8, 0, tzinfo=ZONE)
        rows = [
            {
                "customer_id": "200",
                "occurred_at": (
                    start + timedelta(milliseconds=i * 500)
                ).isoformat(),
                "result": "SUCCESS",
            }
            for i in range(20000)
        ]
        with patch(
            "agione_ops.notification_rules.collect_failure_alerts",
            side_effect=AssertionError("Window was rescanned"),
        ):
            events = collect_interval_failure_events(
                rows, {}, start, start + timedelta(hours=3),
            )
        self.assertEqual(events, [])

    def test_interval_without_later_success_is_not_recovered(self):
        start = datetime(2026, 10, 29, 8, 0, tzinfo=ZONE)
        rows = [{
            "customer_id": "200",
            "occurred_at": (start + timedelta(minutes=i)).isoformat(),
            "result": "FAILURE", "failureKey": "source:3",
        } for i in range(6)]
        events = collect_interval_failure_events(
            rows, {"event_window_minutes": 30},
            start, start + timedelta(hours=2),
        )
        self.assertEqual(len(events), 1)
        self.assertFalse(events[0]["recovered"])

        rows.append({"customer_id": "200", "result": "SUCCESS",
                     "occurred_at": (start + timedelta(minutes=50)).isoformat()})
        events = collect_interval_failure_events(
            rows, {"event_window_minutes": 30},
            start, start + timedelta(hours=2),
        )
        self.assertTrue(events[0]["recovered"])

        rows.append({"customer_id": "200", "result": "FAILURE",
                     "occurred_at": (start + timedelta(minutes=100)).isoformat()})
        events = collect_interval_failure_events(
            rows, {"event_window_minutes": 30},
            start, start + timedelta(hours=2),
        )
        self.assertFalse(events[0]["recovered"])

    def test_interval_window_boundaries_and_duplicate_timestamps(self):
        start = datetime(2026, 10, 29, 8, 0, tzinfo=ZONE)
        end = start + timedelta(minutes=60)
        rows = [{
            "customer_id": "200",
            "occurred_at": (start + timedelta(minutes=minute)).isoformat(),
            "result": result,
            "failureKey": key,
        } for minute, result, key in [
            (-30, "FAILURE", "source:3"),
            (0, "FAILURE", "source:3"),
            (0, "FAILURE", "source:3"),
            (29, "UNKNOWN", ""),
            (30, "SUCCESS", ""),
            (60, "FAILURE", "source:3"),
        ]]
        events = collect_interval_failure_events(
            rows,
            {"event_window_minutes": 30, "min_failure_count": 2,
             "failure_rate_percent": 100, "balance_failure": False},
            start, end,
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["failure_count"], 2)
        self.assertEqual(events[0]["event_request_count"], 2)
        self.assertEqual(events[0]["event_end"], start.isoformat())
        self.assertTrue(events[0]["recovered"])

    def test_analysis_covers_all_four_rule_types(self):
        end = datetime(2026, 10, 29, tzinfo=ZONE)
        rows = []
        rows.extend(
            {
                "customer_id": "declining",
                "occurred_at": (
                    end - timedelta(days=13, minutes=index)
                ).isoformat(),
                "result": "SUCCESS",
                "failureKey": "NOT_APPLICABLE",
            }
            for index in range(10)
        )
        rows.extend(
            {
                "customer_id": "declining",
                "occurred_at": (
                    end - timedelta(days=6, minutes=index)
                ).isoformat(),
                "result": "SUCCESS",
                "failureKey": "NOT_APPLICABLE",
            }
            for index in range(5)
        )
        rows.extend(
            {
                "customer_id": "blocked",
                "occurred_at": (
                    end - timedelta(days=1, minutes=index)
                ).isoformat(),
                "result": "FAILURE",
                "failureKey": "source:3",
            }
            for index in range(6)
        )
        rows.append(
            {
                "customer_id": "inactive",
                "occurred_at": (end - timedelta(days=10)).isoformat(),
                "result": "SUCCESS",
                "failureKey": "NOT_APPLICABLE",
            }
        )
        config = {
            "analysis_days": 7,
            "inactivity_days": 7,
            "decline_percent": 40,
            "min_failure_count": 6,
            "continuous_failure": True,
            "balance_failure": True,
            "decline": True,
            "inactive": True,
        }

        result = analyze_rows(
            rows,
            {"declining", "blocked", "inactive"},
            config,
            end,
            customer_names={"blocked": "Blocked tenant"},
        )

        alerts = {item["customer_id"]: item for item in result["alerts"]}
        self.assertEqual(alerts["declining"]["reasons"], ["decline"])
        self.assertEqual(alerts["declining"]["decline_percent"], 50.0)
        self.assertEqual(
            alerts["blocked"]["reasons"],
            [
                "continuous_failure",
                "balance_failure",
            ],
        )
        self.assertEqual(alerts["blocked"]["customer_name"], "Blocked tenant")
        self.assertEqual(
            alerts["inactive"]["reasons"],
            [
                "decline",
                "inactive",
            ],
        )
        self.assertEqual(result["current_request_count"], 11)
        self.assertEqual(result["previous_request_count"], 11)

    def test_unknown_result_prevents_continuous_failure_alert(self):
        end = datetime(2026, 10, 29, tzinfo=ZONE)
        rows = [
            {
                "customer_id": "unknown",
                "occurred_at": (end - timedelta(hours=index + 1)).isoformat(),
                "result": "FAILURE" if index < 6 else "UNKNOWN",
                "failureKey": "source:1",
            }
            for index in range(7)
        ]

        result = analyze_rows(
            rows,
            {"unknown"},
            {
                "analysis_days": 7,
                "inactivity_days": 7,
                "min_failure_count": 6,
                "failure_rate_percent": 100,
                "continuous_failure": True,
                "balance_failure": False,
                "decline": False,
                "inactive": False,
            },
            end,
        )

        self.assertEqual(result["alerts"], [])

    def test_collection_window_covers_enabled_comparison_and_inactivity(self):
        self.assertEqual(
            required_collection_days(
                {
                    "analysis_days": 7,
                    "decline": True,
                    "inactivity_days": 30,
                    "inactive": True,
                }
            ),
            30,
        )
        self.assertEqual(
            required_collection_days(
                {
                    "analysis_days": 7,
                    "decline": True,
                    "inactivity_days": 30,
                    "inactive": False,
                }
            ),
            14,
        )
        self.assertEqual(
            required_collection_days(
                {
                    "analysis_days": 7,
                    "decline": False,
                    "inactivity_days": 30,
                    "inactive": False,
                }
            ),
            7,
        )


@override_settings(
    AGIONE_OPS_ALLOWED_ENDPOINT_HOSTS=["rules.example"],
    AGIONE_OPS_NATIVE_ONLY=True,
)
class NotificationRuleApiTests(TestCase):
    """Protect server persistence and channel ownership boundaries."""

    def setUp(self):
        users = get_user_model()
        self.user = users.objects.create_user(username="rules-owner")
        self.other = users.objects.create_user(username="rules-other")
        for action in ("view_business", "run_sync"):
            self.user.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label="agione_ops",
                    codename=action,
                )
            )
        self.connection = SourceConnection.objects.create(
            name="Rules source",
            platform="pro",
            principal_kind="operator",
            source_kind="native",
            endpoint="https://rules.example",
            created_by=self.user,
            expected_tenant_id="rules-tenant",
            enabled=True,
        )
        ConnectionGrant.objects.create(
            connection=self.connection,
            user=self.user,
            can_view=True,
            can_sync=True,
        )
        self.global_channel = NotificationChannel.objects.create(
            channel_type=NotificationChannel.TYPE_WEBHOOK,
            name="Global webhook",
            config={},
        )
        self.own_channel = NotificationChannel.objects.create(
            channel_type=NotificationChannel.TYPE_WEBHOOK,
            name="Own webhook",
            user=self.user,
            config={},
        )
        self.foreign_channel = NotificationChannel.objects.create(
            channel_type=NotificationChannel.TYPE_WEBHOOK,
            name="Foreign webhook",
            user=self.other,
            config={},
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = (
            "/api/v1/agione-ops/connections/"
            f"{self.connection.pk}/notification-rules/"
        )

    def test_acknowledged_gap_resumes_automatic_alerts(self):
        from agione_ops.notification_rules import (
            acknowledge_inspection_gap, analyze_completed_snapshot,
        )

        start = datetime(2026, 10, 29, 8, 0, tzinfo=ZONE)
        end = start + timedelta(hours=1)
        rows = [{
            "customer_id": "200", "result": "FAILURE",
            "failureKey": "source:3",
            "occurred_at": (start + timedelta(minutes=i + 1)).isoformat(),
        } for i in range(6)]
        snapshot = SimpleNamespace(
            data={"rows": rows, "customers": {"200": {"name": "Tenant"}},
                  "metadata": {}}, content_digest="test",
        )
        run = SimpleNamespace(
            pk="run", idempotency_key="agione-auto-20261029T030000Z-7",
            window_start=start - timedelta(hours=1), window_end=end,
            published_version=SimpleNamespace(native_snapshot=snapshot),
        )
        scope = SimpleNamespace(
            run_id="run", run=run, connection=self.connection,
            connection_id=self.connection.pk, user=self.user,
        )
        gap = {"start": (start - timedelta(days=2)).isoformat(),
               "end": (start - timedelta(days=1)).isoformat()}
        rules = NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            inspection_gap=gap, last_inspection_at=start - timedelta(days=2),
            config={**notification_rule_config(), "enabled": True,
                    "auto_refresh_enabled": True,
                    "channel_id": str(self.own_channel.uuid),
                    "event_window_minutes": 30},
        )
        with patch("django.utils.timezone.now", return_value=start):
            acknowledge_inspection_gap(
                self.connection, self.user, gap["start"], gap["end"],
            )
        with ExitStack() as stack:
            select = stack.enter_context(patch(
                "agione_ops.native_sync_models.NativeAccountScope.objects."
                "select_related"
            ))
            select.return_value.get.return_value = scope
            inspection_save = stack.enter_context(patch(
                "agione_ops.models.InspectionDecision.objects.update_or_create"
            ))
            stack.enter_context(patch("agione_ops.native_sync.authorize_native_run"))
            stack.enter_context(patch("agione_ops.native_sync.validate_snapshot_data"))
            stack.enter_context(patch(
                "agione_ops.native_account_refresh.scope_for",
                return_value=({}, "valid"),
            ))
            stack.enter_context(patch(
                "agione_ops.native_account_scope.external_rows", return_value=rows,
            ))
            stack.enter_context(patch(
                "agione_ops.tenant_directory.overrides_for", return_value={},
            ))
            run.window_end = start - timedelta(minutes=5)
            analyze_completed_snapshot(1, "run")
            rules.refresh_from_db()
            self.assertEqual(rules.last_inspection_at, start)
            self.assertFalse(NotificationDelivery.objects.exists())
            run.window_end = end
            with patch("agione_ops.tasks.deliver_notification.delay") as send:
                with self.captureOnCommitCallbacks(execute=True):
                    analyze_completed_snapshot(1, "run")
            send.assert_called_once()
            details = inspection_save.call_args.kwargs["defaults"]["details"]
            self.assertEqual(details["outcome"], "queued")
            self.assertEqual(datetime.fromisoformat(details["inspection_start"]), start)
            self.assertEqual(datetime.fromisoformat(details["inspection_end"]), end)
            self.assertEqual(len(details["deliveries"]), 1)
        rules.refresh_from_db()
        self.assertEqual(rules.last_inspection_at, end)
        self.assertEqual(rules.last_auto_status, "succeeded")
        self.assertIn("Tenant", NotificationDelivery.objects.get().payload["text"])

    def test_failed_notification_write_preserves_inspection_for_retry(self):
        from agione_ops.notification_rules import analyze_completed_snapshot

        start = datetime(2026, 10, 29, 8, 0, tzinfo=ZONE)
        end = start + timedelta(hours=3)
        rows = [{
            "customer_id": "200",
            "occurred_at": (start + timedelta(minutes=10 + i)).isoformat(),
            "result": "FAILURE",
            "failureKey": "source:3",
        } for i in range(6)]
        rows.append({
            "customer_id": "200", "result": "SUCCESS",
            "occurred_at": (start + timedelta(minutes=50)).isoformat(),
        })
        snapshot = SimpleNamespace(
            data={"rows": rows, "customers": {"200": {"name": "Tenant"}},
                  "metadata": {}},
            content_digest="test",
        )
        run = SimpleNamespace(
            pk="run", idempotency_key="agione-auto-20261029T030000Z-7",
            window_start=start - timedelta(hours=1), window_end=end,
            published_version=SimpleNamespace(native_snapshot=snapshot),
        )
        scope = SimpleNamespace(
            run_id="run", run=run, connection=self.connection,
            connection_id=self.connection.pk, user=self.user,
        )
        rules = NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            last_inspection_at=start,
            config={**notification_rule_config(), "enabled": True,
                    "channel_id": str(self.own_channel.uuid),
                    "event_window_minutes": 30},
        )
        with ExitStack() as stack:
            select = stack.enter_context(patch(
                "agione_ops.native_sync_models.NativeAccountScope.objects."
                "select_related"
            ))
            select.return_value.get.return_value = scope
            stack.enter_context(patch(
                "agione_ops.models.InspectionDecision.objects.update_or_create"
            ))
            stack.enter_context(patch(
                "agione_ops.native_sync.authorize_native_run"
            ))
            stack.enter_context(patch(
                "agione_ops.native_sync.validate_snapshot_data"
            ))
            stack.enter_context(patch(
                "agione_ops.native_account_refresh.scope_for",
                return_value=({}, "valid"),
            ))
            stack.enter_context(patch(
                "agione_ops.native_account_scope.external_rows",
                return_value=rows,
            ))
            stack.enter_context(patch(
                "agione_ops.tenant_directory.overrides_for", return_value={},
            ))
            with patch(
                "agione_ops.notification_delivery._create_delivery",
                side_effect=RuntimeError("write failed"),
            ), self.assertRaisesRegex(RuntimeError, "write failed"):
                analyze_completed_snapshot(1, "run")
            rules.refresh_from_db()
            self.assertEqual(rules.last_inspection_at, start)
            self.assertFalse(rules.last_analysis)
            self.assertFalse(NotificationDelivery.objects.exists())

            with patch("agione_ops.tasks.deliver_notification.delay") as send:
                with self.captureOnCommitCallbacks(execute=True):
                    analyze_completed_snapshot(1, "run")
                send.assert_called_once()
            rules.refresh_from_db()
            self.assertEqual(rules.last_inspection_at, end)
            delivery = NotificationDelivery.objects.get()
            self.assertEqual(delivery.kind, "recovered_history")
            self.assertIn("Tenant", delivery.payload["text"])

    def test_unconfirmed_history_recovers_on_later_inspection(self):
        from agione_ops.models import NotificationIssue
        from agione_ops.notification_rules import analyze_completed_snapshot

        start = datetime(2026, 10, 29, 8, 0, tzinfo=ZONE)
        end = start + timedelta(hours=2)
        rows = [{
            "customer_id": "200", "result": "FAILURE",
            "failureKey": "source:3",
            "occurred_at": (start + timedelta(minutes=i)).isoformat(),
        } for i in range(6)]
        snapshot = SimpleNamespace(
            data={"rows": rows, "customers": {"200": {"name": "Tenant"}},
                  "metadata": {}}, content_digest="test",
        )
        run = SimpleNamespace(
            pk="run", idempotency_key="agione-auto-20261029T030000Z-7",
            window_start=start - timedelta(hours=1), window_end=end,
            published_version=SimpleNamespace(native_snapshot=snapshot),
        )
        scope = SimpleNamespace(
            run_id="run", run=run, connection=self.connection,
            connection_id=self.connection.pk, user=self.user,
        )
        rules = NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            last_inspection_at=start,
            config={**notification_rule_config(), "enabled": True,
                    "channel_id": str(self.own_channel.uuid),
                    "event_window_minutes": 30},
        )
        with ExitStack() as stack:
            select = stack.enter_context(patch(
                "agione_ops.native_sync_models.NativeAccountScope.objects."
                "select_related"
            ))
            select.return_value.get.return_value = scope
            stack.enter_context(patch(
                "agione_ops.models.InspectionDecision.objects.update_or_create"
            ))
            stack.enter_context(patch(
                "agione_ops.native_sync.authorize_native_run"
            ))
            stack.enter_context(patch(
                "agione_ops.native_sync.validate_snapshot_data"
            ))
            stack.enter_context(patch(
                "agione_ops.native_account_refresh.scope_for",
                return_value=({}, "valid"),
            ))
            stack.enter_context(patch(
                "agione_ops.native_account_scope.external_rows",
                side_effect=lambda snapshot_rows, *_: snapshot_rows,
            ))
            stack.enter_context(patch(
                "agione_ops.tenant_directory.overrides_for", return_value={},
            ))
            send = stack.enter_context(patch(
                "agione_ops.tasks.deliver_notification.delay"
            ))
            with self.captureOnCommitCallbacks(execute=True):
                analyze_completed_snapshot(1, "run")
            rules.refresh_from_db()
            self.assertEqual(rules.last_inspection_at, end)
            self.assertEqual(
                NotificationIssue.objects.filter(active=True).count(), 2,
            )
            self.assertIn(
                "恢复状态待确认", NotificationDelivery.objects.get().payload["text"],
            )

            rows.append({
                "customer_id": "200", "result": "SUCCESS",
                "occurred_at": (end + timedelta(minutes=10)).isoformat(),
            })
            run.window_end = end + timedelta(hours=1)
            with self.captureOnCommitCallbacks(execute=True):
                analyze_completed_snapshot(1, "run")
            rules.refresh_from_db()
            self.assertEqual(rules.last_inspection_at, run.window_end)
            self.assertFalse(
                NotificationIssue.objects.filter(active=True).exists(),
            )
            self.assertEqual(
                NotificationDelivery.objects.filter(kind="recovery").count(), 1,
            )
            self.assertEqual(send.call_count, 2)

    def test_get_defaults_then_save_and_read_server_configuration(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        body = response.data["data"]
        self.assertFalse(body["configured"])
        self.assertEqual(body["analysisDays"], 7)
        self.assertEqual(
            {item["id"] for item in body["channels"]},
            {str(self.global_channel.uuid), str(self.own_channel.uuid)},
        )

        payload = {
            "analysisDays": 7,
            "inactivityDays": 9,
            "declinePercent": 35,
            "technicalFailurePercent": 2,
            "minTechnicalRequests": 20,
            "scheduleTime": "08:35",
            "minFailureCount": 5,
            "continuousFailure": True,
            "balanceFailure": True,
            "decline": True,
            "inactive": True,
            "enabled": True,
            "channelId": str(self.own_channel.uuid),
            "repeatHours": 4,
            "sendRecovery": True,
        }
        saved = self.client.put(self.url, payload, format="json")
        self.assertEqual(saved.status_code, 200, saved.data)
        row = NotificationRules.objects.get(
            connection=self.connection,
            user=self.user,
        )
        self.assertEqual(row.config["inactivity_days"], 9)
        self.assertEqual(row.config["channel_id"], str(self.own_channel.uuid))
        self.assertEqual(row.config["schedule_time"], "08:35")
        self.assertTrue(row.config["enabled"])
        reread = self.client.get(self.url).data["data"]
        self.assertTrue(reread["configured"])
        self.assertEqual(reread["inactivityDays"], 9)

    def test_inspection_history_exposes_current_delivery_status(self):
        from django.utils import timezone

        from agione_ops.models import InspectionDecision, SyncRun

        now = timezone.now()
        rules = NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            config=notification_rule_config(),
        )
        run = SyncRun.objects.create(
            connection=self.connection, initiated_by=self.user,
            window_start=now - timedelta(hours=3), window_end=now,
            idempotency_key="agione-auto-test", request_hash="a" * 64,
            credential_version=self.connection.credential_version,
            config_version=self.connection.config_version, grant_revision=1,
            status="succeeded",
        )
        delivery = NotificationDelivery.objects.create(
            rules=rules, event_key="b" * 64, issue_signature="c" * 64,
            kind="alert", status="retrying", attempts=2,
        )
        InspectionDecision.objects.create(
            rules=rules, run=run, details={
                "outcome": "queued", "issue_count": 1, "issues": [],
                "deliveries": [delivery.pk],
                "inspection_start": run.window_start.isoformat(),
                "inspection_end": run.window_end.isoformat(),
            },
        )
        body = self.client.get(self.url).data["data"]
        history = body["inspectionHistory"]
        self.assertEqual(history[0]["runId"], str(run.pk))
        self.assertEqual(history[0]["deliveries"][0]["status"], "retrying")
        delivery.status = "sent"
        delivery.save(update_fields=["status"])
        history = self.client.get(self.url).data["data"]["inspectionHistory"]
        self.assertEqual(history[0]["deliveries"][0]["status"], "sent")

    def test_foreign_channel_is_rejected(self):
        response = self.client.put(
            self.url,
            {
                "channelId": str(self.foreign_channel.uuid),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(NotificationRules.objects.exists())

    def test_auto_refresh_configuration_reschedules_and_can_be_disabled(self):
        payload = {
            "autoRefreshEnabled": True,
            "autoRefreshHours": 2,
            "financeRefreshHours": 6,
            "tenantRefreshHours": 24,
        }

        saved = self.client.put(self.url, payload, format="json")

        self.assertEqual(saved.status_code, 200, saved.data)
        row = NotificationRules.objects.get(
            connection=self.connection,
            user=self.user,
        )
        self.assertEqual(row.config["auto_refresh_hours"], 2)
        self.assertIsNotNone(row.next_auto_refresh_at)
        self.assertEqual(row.last_auto_status, "scheduled")

        payload["autoRefreshEnabled"] = False
        disabled = self.client.put(self.url, payload, format="json")

        self.assertEqual(disabled.status_code, 200, disabled.data)
        row.refresh_from_db()
        self.assertIsNone(row.next_auto_refresh_at)
        self.assertEqual(row.last_auto_status, "disabled")

    def test_daily_collection_covers_enabled_comparison_window(self):
        from agione_ops.tasks import submit_recent_sync

        NotificationRules.objects.create(
            connection=self.connection,
            user=self.user,
            config={
                **notification_rule_config(),
                "decline": True,
            },
        )
        end = datetime(2026, 10, 29, tzinfo=ZONE)

        with patch("agione_ops.sync.submit_sync") as submit:
            submit_recent_sync(self.connection, self.user, end)

        self.assertEqual(submit.call_args.args[2], end - timedelta(days=14))
        self.assertEqual(submit.call_args.args[3], end)

    def test_failed_daily_run_gets_a_new_retry_idempotency_key(self):
        from agione_ops.models import SyncRun
        from agione_ops.tasks import submit_recent_sync

        NotificationRules.objects.create(
            connection=self.connection,
            user=self.user,
            config=notification_rule_config(),
        )
        end = datetime(2026, 10, 29, tzinfo=ZONE)
        base = "agione-scheduled-2026-10-29-7"
        SyncRun.objects.create(
            connection=self.connection,
            initiated_by=self.user,
            window_start=end - timedelta(days=7),
            window_end=end,
            timezone="Asia/Shanghai",
            idempotency_key=base,
            request_hash="0" * 64,
            credential_version=self.connection.credential_version,
            config_version=self.connection.config_version,
            grant_revision=self.connection.grants.get(user=self.user).revision,
            status="failed",
            finished_at=end - timedelta(minutes=6),
        )

        with (
            patch("django.utils.timezone.now", return_value=end),
            patch(
                "agione_ops.sync.submit_sync",
                return_value=(None, True),
            ) as submit,
        ):
            submit_recent_sync(
                self.connection,
                self.user,
                end,
                scheduled=True,
            )

        self.assertEqual(
            submit.call_args.args[-1],
            "agione-scheduled-2026-10-29-7-retry-1",
        )

    def test_failed_daily_run_waits_for_retry_backoff(self):
        from agione_ops.models import SyncRun
        from agione_ops.tasks import submit_recent_sync

        NotificationRules.objects.create(
            connection=self.connection,
            user=self.user,
            config=notification_rule_config(),
        )
        end = datetime(2026, 10, 29, tzinfo=ZONE)
        run = SyncRun.objects.create(
            connection=self.connection,
            initiated_by=self.user,
            window_start=end - timedelta(days=7),
            window_end=end,
            timezone="Asia/Shanghai",
            idempotency_key="agione-scheduled-2026-10-29-7",
            request_hash="0" * 64,
            credential_version=self.connection.credential_version,
            config_version=self.connection.config_version,
            grant_revision=self.connection.grants.get(user=self.user).revision,
            status="failed",
            finished_at=end - timedelta(minutes=1),
        )

        with (
            patch("django.utils.timezone.now", return_value=end),
            patch("agione_ops.sync.submit_sync") as submit,
        ):
            returned, created = submit_recent_sync(
                self.connection,
                self.user,
                end,
                scheduled=True,
            )

        self.assertEqual(returned, run)
        self.assertFalse(created)
        submit.assert_not_called()

    def test_failed_daily_run_stops_after_three_attempts(self):
        from agione_ops.models import SyncRun
        from agione_ops.tasks import submit_recent_sync

        NotificationRules.objects.create(
            connection=self.connection,
            user=self.user,
            config=notification_rule_config(),
        )
        end = datetime(2026, 10, 29, tzinfo=ZONE)
        latest = None
        keys = [
            "agione-scheduled-2026-10-29-7",
            "agione-scheduled-2026-10-29-7-retry-1",
            "agione-scheduled-2026-10-29-7-retry-2",
        ]
        for index, key in enumerate(keys):
            latest = SyncRun.objects.create(
                connection=self.connection,
                initiated_by=self.user,
                window_start=end - timedelta(days=7),
                window_end=end,
                timezone="Asia/Shanghai",
                idempotency_key=key,
                request_hash=str(index) * 64,
                credential_version=self.connection.credential_version,
                config_version=self.connection.config_version,
                grant_revision=(
                    self.connection.grants.get(user=self.user).revision
                ),
                status="failed",
                finished_at=end - timedelta(minutes=30 - index),
            )

        with (
            patch("django.utils.timezone.now", return_value=end),
            patch("agione_ops.sync.submit_sync") as submit,
        ):
            returned, created = submit_recent_sync(
                self.connection,
                self.user,
                end,
                scheduled=True,
            )

        self.assertEqual(returned, latest)
        self.assertFalse(created)
        submit.assert_not_called()

    @override_settings(AGIONE_OPS_NATIVE_ENABLED=True)
    def test_existing_failed_schedule_not_marked_as_new_dispatch(self):
        from agione_ops.models import SyncRun
        from agione_ops.tasks import dispatch_scheduled_rule_syncs
        from django.utils import timezone

        SourceConnection.objects.filter(pk=self.connection.pk).update(
            verified_at=timezone.now(),
            verified_tenant_id="rules-tenant",
        )
        now = datetime(2026, 10, 29, 8, 36, tzinfo=ZONE)
        rules = NotificationRules.objects.create(
            connection=self.connection,
            user=self.user,
            config={
                **notification_rule_config(),
                "enabled": True,
                "channel_id": str(self.own_channel.uuid),
                "schedule_time": "08:35",
            },
            last_scheduled_at=now - timedelta(days=1),
        )
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        SyncRun.objects.create(
            connection=self.connection,
            initiated_by=self.user,
            window_start=end - timedelta(days=7),
            window_end=end,
            timezone="Asia/Shanghai",
            idempotency_key="agione-scheduled-2026-10-29-7",
            request_hash="0" * 64,
            credential_version=self.connection.credential_version,
            config_version=self.connection.config_version,
            grant_revision=self.connection.grants.get(user=self.user).revision,
            status="failed",
        )

        with (
            patch("django.utils.timezone.now", return_value=now),
            patch(
                "agione_ops.tasks.submit_recent_sync",
                return_value=(object(), False),
            ) as submit,
        ):
            dispatched = dispatch_scheduled_rule_syncs()

        rules.refresh_from_db()
        self.assertEqual(dispatched, 0)
        self.assertEqual(submit.call_count, 1)
        self.assertEqual(
            rules.last_scheduled_at,
            now - timedelta(days=1),
        )
        self.assertTrue(submit.call_args.kwargs["scheduled"])

    @override_settings(AGIONE_OPS_NATIVE_ENABLED=True)
    def test_daily_collection_skips_enabled_custom_schedule(self):
        from django.utils import timezone

        from agione_ops.tasks import prefetch_recent_native_data

        for action in ("view_business", "run_sync"):
            self.other.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label="agione_ops",
                    codename=action,
                )
            )
        ConnectionGrant.objects.create(
            connection=self.connection,
            user=self.other,
            can_view=True,
            can_sync=True,
        )
        NotificationRules.objects.create(
            connection=self.connection,
            user=self.other,
            config=notification_rule_config(),
        )
        SourceConnection.objects.filter(pk=self.connection.pk).update(
            verified_at=timezone.now(),
            verified_tenant_id="rules-tenant",
        )

        with patch("agione_ops.tasks.submit_recent_sync") as submit:
            prefetch_recent_native_data()

        self.assertEqual(submit.call_count, 1)
        self.assertEqual(submit.call_args.args[1].pk, self.user.pk)

    @override_settings(AGIONE_OPS_NATIVE_ENABLED=True)
    def test_rule_schedule_dispatches_once_after_configured_time(self):
        from django.utils import timezone

        from agione_ops.tasks import dispatch_scheduled_rule_syncs

        SourceConnection.objects.filter(pk=self.connection.pk).update(
            verified_at=timezone.now(),
            verified_tenant_id="rules-tenant",
        )
        rules = NotificationRules.objects.create(
            connection=self.connection,
            user=self.user,
            config={
                **notification_rule_config(),
                "enabled": True,
                "channel_id": str(self.own_channel.uuid),
                "schedule_time": "08:35",
            },
        )
        now = datetime(2026, 10, 29, 8, 36, tzinfo=ZONE)

        with (
            patch("django.utils.timezone.now", return_value=now),
            patch("agione_ops.tasks.submit_recent_sync") as submit,
        ):
            submit.side_effect = [
                (object(), True),
                (object(), False),
            ]
            first = dispatch_scheduled_rule_syncs()
            second = dispatch_scheduled_rule_syncs()

        rules.refresh_from_db()
        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(submit.call_count, 2)
        self.assertEqual(
            submit.call_args.args[2],
            now.replace(hour=0, minute=0),
        )
        self.assertTrue(submit.call_args.kwargs["scheduled"])
        self.assertEqual(
            rules.last_scheduled_at.astimezone(ZONE).date(),
            now.date(),
        )

    @override_settings(AGIONE_OPS_NATIVE_ENABLED=True)
    def test_auto_refresh_dispatch_uses_configured_period_and_due_time(self):
        from django.utils import timezone

        from agione_ops.tasks import dispatch_auto_refresh_syncs

        SourceConnection.objects.filter(pk=self.connection.pk).update(
            verified_at=timezone.now(),
            verified_tenant_id="rules-tenant",
        )
        now = datetime(2026, 10, 29, 8, 36, tzinfo=ZONE)
        rules = NotificationRules.objects.create(
            connection=self.connection,
            user=self.user,
            config={
                **notification_rule_config(),
                "auto_refresh_enabled": True,
                "auto_refresh_hours": 4,
            },
            next_auto_refresh_at=now - timedelta(minutes=1),
        )

        with (
            patch("django.utils.timezone.now", return_value=now),
            patch(
                "agione_ops.tasks.submit_auto_sync",
                return_value=(object(), True),
            ) as submit,
        ):
            dispatched = dispatch_auto_refresh_syncs()

        rules.refresh_from_db()
        self.assertEqual(dispatched, 1)
        self.assertEqual(submit.call_count, 1)
        self.assertEqual(rules.last_auto_status, "queued")
        self.assertEqual(rules.next_auto_refresh_at, now + timedelta(hours=4))

    @override_settings(AGIONE_OPS_NATIVE_ENABLED=True)
    def test_repeat_due_dispatches_fresh_inspection_without_moving_schedule(self):
        from django.utils import timezone

        from agione_ops.models import NotificationIssue
        from agione_ops.tasks import dispatch_auto_refresh_syncs

        SourceConnection.objects.filter(pk=self.connection.pk).update(
            verified_at=timezone.now(), verified_tenant_id="rules-tenant",
        )
        now = datetime(2026, 10, 29, 12, 0, tzinfo=ZONE)
        scheduled = now + timedelta(hours=2)
        rules = NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            config={**notification_rule_config(), "enabled": True,
                    "auto_refresh_enabled": True, "auto_refresh_hours": 3,
                    "repeat_hours": 4,
                    "channel_id": str(self.own_channel.uuid)},
            next_auto_refresh_at=scheduled,
            last_auto_started_at=now - timedelta(hours=1),
        )
        issue = NotificationIssue.objects.create(
            rules=rules, customer_id="200", reason="balance_failure",
            first_seen_at=now - timedelta(hours=4),
            last_seen_at=now - timedelta(hours=1),
            last_alerted_at=now - timedelta(hours=4),
        )
        with (patch("django.utils.timezone.now") as clock,
              patch("agione_ops.tasks.submit_auto_sync",
                    return_value=(object(), True)) as submit):
            clock.return_value = now - timedelta(minutes=1)
            self.assertEqual(dispatch_auto_refresh_syncs(), 0)
            clock.return_value = now
            self.assertEqual(dispatch_auto_refresh_syncs(), 1)
            self.assertEqual(dispatch_auto_refresh_syncs(), 0)
        rules.refresh_from_db()
        self.assertEqual(submit.call_count, 1)
        self.assertEqual(rules.next_auto_refresh_at, scheduled)
        self.assertEqual(rules.last_auto_started_at, now)
        self.assertTrue(issue.active)

    @override_settings(AGIONE_OPS_NATIVE_ENABLED=True)
    def test_failed_early_inspection_retries_after_recovery_is_exhausted(self):
        from django.utils import timezone

        from agione_ops.models import NotificationIssue, SyncRun
        from agione_ops.tasks import dispatch_auto_refresh_syncs

        SourceConnection.objects.filter(pk=self.connection.pk).update(
            verified_at=timezone.now(), verified_tenant_id="rules-tenant",
        )
        now = datetime(2026, 10, 29, 14, 13, tzinfo=ZONE)
        scheduled = now + timedelta(hours=1)
        rules = NotificationRules.objects.create(
            connection=self.connection, user=self.user,
            config={**notification_rule_config(), "enabled": True,
                    "auto_refresh_enabled": True, "auto_refresh_hours": 3,
                    "repeat_hours": 4,
                    "channel_id": str(self.own_channel.uuid)},
            next_auto_refresh_at=scheduled,
            last_auto_started_at=now - timedelta(minutes=13),
            last_auto_success_at=now - timedelta(hours=1),
            last_auto_status="failed",
        )
        NotificationIssue.objects.create(
            rules=rules, customer_id="200", reason="balance_failure",
            first_seen_at=now - timedelta(hours=4, minutes=13),
            last_seen_at=now - timedelta(hours=1),
            last_alerted_at=now - timedelta(hours=4, minutes=13),
        )
        run = SyncRun.objects.create(
            connection=self.connection, initiated_by=self.user,
            window_start=now - timedelta(hours=3), window_end=now,
            idempotency_key="agione-auto-test-retry-2", request_hash="a" * 64,
            credential_version=self.connection.credential_version,
            config_version=self.connection.config_version, grant_revision=1,
            status="failed", error_code="SOURCE_UNREACHABLE",
            finished_at=now - timedelta(minutes=5), recovery_handled=False,
        )
        with (patch("django.utils.timezone.now", return_value=now),
              patch("agione_ops.tasks.submit_auto_sync",
                    return_value=(object(), True)) as submit):
            SyncRun.objects.filter(pk=run.pk).update(status="running")
            self.assertEqual(dispatch_auto_refresh_syncs(), 0)
            SyncRun.objects.filter(pk=run.pk).update(status="failed")
            self.assertEqual(dispatch_auto_refresh_syncs(), 0)
            SyncRun.objects.filter(pk=run.pk).update(recovery_handled=True)
            SyncRun.objects.filter(pk=run.pk).update(
                finished_at=now - timedelta(minutes=4),
            )
            self.assertEqual(dispatch_auto_refresh_syncs(), 0)
            SyncRun.objects.filter(pk=run.pk).update(
                finished_at=now - timedelta(minutes=5),
            )
            SyncRun.objects.filter(pk=run.pk).update(
                error_code="SOURCE_AUTH_FAILED",
            )
            self.assertEqual(dispatch_auto_refresh_syncs(), 0)
            SyncRun.objects.filter(pk=run.pk).update(
                error_code="SOURCE_UNREACHABLE",
            )
            self.assertEqual(dispatch_auto_refresh_syncs(), 1)
            self.assertEqual(dispatch_auto_refresh_syncs(), 0)
            self.assertEqual(submit.call_count, 1)
        rules.refresh_from_db()
        self.assertEqual(rules.next_auto_refresh_at, scheduled)
        rules.last_auto_success_at = now
        rules.save(update_fields=["last_auto_success_at"])
        later = now + timedelta(minutes=6)
        with (patch("django.utils.timezone.now", return_value=later),
              patch("agione_ops.tasks.submit_auto_sync") as submit):
            self.assertEqual(dispatch_auto_refresh_syncs(), 0)
            submit.assert_not_called()

    @override_settings(AGIONE_OPS_NATIVE_ENABLED=True)
    def test_disabled_auto_refresh_is_not_dispatched(self):
        from agione_ops.tasks import dispatch_auto_refresh_syncs

        NotificationRules.objects.create(
            connection=self.connection,
            user=self.user,
            config={
                **notification_rule_config(),
                "auto_refresh_enabled": False,
                "auto_refresh_hours": 2,
            },
        )

        with patch("agione_ops.tasks.submit_auto_sync") as submit:
            self.assertEqual(dispatch_auto_refresh_syncs(), 0)
        submit.assert_not_called()

    @override_settings(AGIONE_OPS_NATIVE_ENABLED=True)
    def test_completed_classification_persists_analysis(self):
        from django.utils import timezone

        from agione_ops.models import DatasetVersion, SyncRun
        from agione_ops.native_sync import digest
        from agione_ops.native_sync_models import (
            NativeAccountScope,
            NativePublishedSnapshot,
            NativeStagedRecord,
            NativeSyncShard,
            NativeSyncState,
        )
        from agione_ops.notification_rules import analyze_completed_snapshot

        SourceConnection.objects.filter(pk=self.connection.pk).update(
            verified_tenant_id="rules-tenant",
            verified_at=timezone.now(),
        )
        self.connection.refresh_from_db()
        end = datetime(2026, 10, 29, tzinfo=ZONE)
        start = end - timedelta(days=7)
        run = SyncRun.objects.create(
            connection=self.connection,
            initiated_by=self.user,
            window_start=start,
            window_end=end,
            idempotency_key="agione-scheduled-2026-10-29-7",
            request_hash="0" * 64,
            credential_version=self.connection.credential_version,
            config_version=self.connection.config_version,
            grant_revision=self.connection.grants.get(user=self.user).revision,
            status="running",
        )
        customer_id = "200"
        rows = [
            {
                "record_id": str(index + 1),
                "customer_id": customer_id,
                "model_id": "300",
                "user_id": "400",
                "project_id": None,
                "subject_type": "USER",
                "occurred_at": (end - timedelta(hours=index + 1)).isoformat(),
                "result": "FAILURE",
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "failureKey": "source:3",
                "latencyState": "UNIT_UNCONFIRMED",
            }
            for index in range(6)
        ]
        NativeSyncState.objects.create(
            run=run,
            directory={
                customer_id: {"name": "Customer", "organizationName": None},
            },
            model_names={"300": "Model"},
            directory_complete=True,
            directory_count=1,
            role_state="verified",
        )
        shard = NativeSyncShard.objects.create(
            run=run,
            window_start=start,
            window_end=end,
            status="succeeded",
            record_count=len(rows),
        )
        for row in rows:
            NativeStagedRecord.objects.create(
                run=run,
                shard=shard,
                record_id=row["record_id"],
                occurred_at=row["occurred_at"],
                content_digest=digest(row),
                data=row,
            )
        data = {
            "metadata": {
                "configVersion": run.config_version,
                "credentialVersion": run.credential_version,
                "roleState": "verified",
                "collectedAt": end.isoformat(),
            },
            "rows": rows,
            "customers": {
                customer_id: {"name": "Customer", "organizationName": None},
            },
            "models": {"300": "Model"},
        }
        version = DatasetVersion.objects.create(
            connection=self.connection,
            run=run,
            window_start=start,
            window_end=end,
        )
        NativePublishedSnapshot.objects.create(
            version=version,
            data=data,
            content_digest=digest(data),
        )
        SyncRun.objects.filter(pk=run.pk).update(status="succeeded")
        types = {
            f"tenant:{customer_id}": "external",
            f"{customer_id}:400": "external",
        }
        scope = NativeAccountScope.objects.create(
            connection=self.connection,
            user=self.user,
            operator=self.connection,
            run=run,
            config_version=self.connection.config_version,
            credential_version=self.connection.credential_version,
            operator_config_version=self.connection.config_version,
            operator_credential_version=self.connection.credential_version,
            status="ready",
            data=types,
            content_digest=digest(types),
        )
        rules = NotificationRules.objects.create(
            connection=self.connection,
            user=self.user,
            last_analysis={"status": "ready", "trigger": "automatic",
                           "window_end": (end + timedelta(hours=5)).isoformat(),
                           "alerts": []},
            config={
                **notification_rule_config(),
                "enabled": True,
                "channel_id": str(self.own_channel.uuid),
                "schedule_time": "08:35",
            },
        )

        from agione_ops.tasks import dispatch_scheduled_rule_syncs

        with (
            patch(
                "django.utils.timezone.now",
                return_value=end.replace(hour=8, minute=36),
            ),
            patch(
                "agione_ops.tasks.submit_recent_sync",
                return_value=(run, True),
            ) as submit,
        ):
            self.assertEqual(dispatch_scheduled_rule_syncs(), 1)
        self.assertTrue(submit.call_args.kwargs["scheduled"])

        # A completed collection without a delivered report must be analyzed.
        run.refresh_from_db()
        newer_run = SyncRun.objects.create(
            connection=self.connection, initiated_by=self.user,
            window_start=start, window_end=end + timedelta(hours=5),
            idempotency_key="agione-auto-20261029T050000Z-7",
            request_hash="9" * 64, credential_version=run.credential_version,
            config_version=run.config_version, grant_revision=run.grant_revision,
            status="succeeded",
        )
        scope.run = newer_run
        scope.save(update_fields=["run"])
        rules.last_scheduled_at = None
        rules.save(update_fields=["last_scheduled_at"])
        with (
            patch("django.utils.timezone.now", return_value=end.replace(hour=9)),
            patch("agione_ops.tasks.submit_recent_sync", return_value=(run, False)),
            patch("agione_ops.tasks.analyze_native_snapshot.delay") as recover,
            self.captureOnCommitCallbacks(execute=True),
        ):
            dispatch_scheduled_rule_syncs()
            dispatch_scheduled_rule_syncs()
        recover.assert_called_once_with(scope.pk, str(run.pk))
        with (
            patch("django.utils.timezone.now") as clock,
            patch("agione_ops.tasks.submit_recent_sync", return_value=(run, False)),
            patch("agione_ops.tasks.analyze_native_snapshot.delay") as recover,
            self.captureOnCommitCallbacks(execute=True),
        ):
            for minute in (6, 12, 18):
                clock.return_value = end.replace(hour=9, minute=minute)
                dispatch_scheduled_rule_syncs()
        rules.refresh_from_db()
        self.assertEqual(recover.call_count, 2)
        self.assertEqual(rules.last_report_status, "failed")
        self.assertEqual(rules.last_report_attempts, 3)

        with patch(
            "agione_ops.tasks.deliver_notification.delay",
        ) as deliver, self.captureOnCommitCallbacks(execute=True):
            result = analyze_completed_snapshot(scope.pk, str(run.pk))
            analyze_completed_snapshot(scope.pk, str(run.pk))

        rules.refresh_from_db()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(rules.last_analysis["trigger"], "automatic")
        self.assertEqual(
            result["alerts"][0]["reasons"],
            [
                "continuous_failure",
                "balance_failure",
            ],
        )
        self.assertEqual(result["alerts"][0]["customer_name"], "Customer")
        delivery = NotificationDelivery.objects.get(rules=rules)
        self.assertEqual(delivery.payload["scheduled_date"], "2026-10-29")
        self.assertIn("Customer", delivery.payload["text"])
        self.assertEqual(deliver.call_count, 1)
        rules.last_report_status = "idle"
        rules.last_report_attempts = 0
        rules.last_report_updated_at = None
        rules.save(update_fields=["last_report_status", "last_report_attempts",
                                  "last_report_updated_at"])
        with (
            patch("django.utils.timezone.now", return_value=end.replace(hour=10)),
            patch("agione_ops.tasks.submit_recent_sync", return_value=(run, False)),
            patch("agione_ops.tasks.analyze_native_snapshot.delay") as recover,
            self.captureOnCommitCallbacks(execute=True),
        ):
            dispatch_scheduled_rule_syncs()
        recover.assert_not_called()


def notification_rule_config():
    """Return validated snake-case defaults for persistence tests."""
    serializer = NotificationRulesSerializer(data={})
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data
