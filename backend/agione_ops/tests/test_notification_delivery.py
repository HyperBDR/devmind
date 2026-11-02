"""Verify durable AGIOne notification delivery and recovery behavior."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings

from agentcore_notifier.adapters.django.models import NotificationChannel
from agione_ops.models import (
    ConnectionGrant,
    NotificationDelivery,
    NotificationIssue,
    NotificationRules,
    SourceConnection,
)
from agione_ops.notification_delivery import (
    delivery_events,
    enqueue_analysis_notifications,
)
from agione_ops.tasks import (
    deliver_notification,
    retry_notification_deliveries,
)

ZONE = ZoneInfo("Asia/Shanghai")


class NotificationDeliveryUnitTests(TestCase):
    """Cover alert and recovery event derivation without transport calls."""

    def test_events_include_new_alert_and_resolved_recovery(self):
        previous = {
            "status": "ready",
            "alerts": [
                {
                    "customer_id": "old",
                    "reasons": ["continuous_failure"],
                }
            ],
        }
        current = {
            "status": "ready",
            "window_end": "2026-10-29T00:00:00+08:00",
            "alerts": [
                {
                    "customer_id": "new",
                    "reasons": ["balance_failure"],
                }
            ],
        }

        events = delivery_events(
            previous,
            current,
            {
                "send_recovery": True,
            },
        )

        self.assertEqual(
            [item["kind"] for item in events],
            [
                "alert",
                "recovery",
            ],
        )
        self.assertEqual(events[0]["findings"][0]["customer_id"], "new")
        self.assertEqual(events[1]["findings"][0]["customer_id"], "old")


@override_settings(
    AGIONE_OPS_ALLOWED_ENDPOINT_HOSTS=["delivery.example"],
    AGIONE_OPS_NATIVE_ONLY=True,
    AGIONE_OPS_PUBLIC_URL="http://localhost:18000/agione#focus",
)
class NotificationDeliveryIntegrationTests(TestCase):
    """Protect deduplication, transport result state and retry attempts."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="delivery-owner",
        )
        for action in ("view_business", "run_sync"):
            self.user.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label="agione_ops",
                    codename=action,
                )
            )
        self.connection = SourceConnection.objects.create(
            name="Delivery source",
            platform="pro",
            principal_kind="operator",
            source_kind="native",
            endpoint="https://delivery.example",
            created_by=self.user,
            expected_tenant_id="delivery-tenant",
            enabled=True,
        )
        ConnectionGrant.objects.create(
            connection=self.connection,
            user=self.user,
            can_view=True,
            can_sync=True,
        )
        self.channel = NotificationChannel.objects.create(
            channel_type=NotificationChannel.TYPE_WEBHOOK,
            name="Delivery webhook",
            user=self.user,
            config={"provider_type": "feishu", "url": "https://hook.invalid"},
        )
        self.rules = NotificationRules.objects.create(
            connection=self.connection,
            user=self.user,
            config={
                "enabled": True,
                "channel_id": str(self.channel.uuid),
                "repeat_hours": 4,
                "send_recovery": True,
            },
        )
        self.analysis = {
            "status": "ready",
            "current_start": datetime(2026, 10, 22, tzinfo=ZONE).isoformat(),
            "event_start": datetime(
                2026,
                10,
                28,
                23,
                0,
                tzinfo=ZONE,
            ).isoformat(),
            "window_end": datetime(2026, 10, 29, tzinfo=ZONE).isoformat(),
            "collected_at": datetime(
                2026,
                10,
                29,
                9,
                50,
                tzinfo=ZONE,
            ).isoformat(),
            "alerts": [
                {
                    "customer_id": "200",
                    "customer_name": "Tenant owner",
                    "reasons": [
                        "continuous_failure",
                        "balance_failure",
                    ],
                    "failure_count": 1006,
                    "current_request_count": 1006,
                },
                {
                    "customer_id": "201",
                    "customer_name": "Tenant B",
                    "reasons": ["decline"],
                    "current_request_count": 30,
                    "previous_request_count": 100,
                    "decline_percent": 70,
                },
            ],
        }

    @patch("agione_ops.tasks.deliver_notification.delay")
    def test_enqueue_is_idempotent_for_same_analysis(self, delay):
        first = enqueue_analysis_notifications(
            self.rules,
            {},
            self.analysis,
        )
        second = enqueue_analysis_notifications(
            self.rules,
            {},
            self.analysis,
        )

        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertEqual(NotificationDelivery.objects.count(), 1)
        text = first[0].payload["text"]
        self.assertIn("【AGIOne 运营日报】发现 2 项需要关注", text)
        self.assertIn("持续调用失败 · 1 位租户", text)
        self.assertIn(
            "Tenant owner（ID：200）：失败 1,006 次，成功 0 次；"
            "已识别原因：余额不足。",
            text,
        )
        self.assertIn("使用下降 · 1 位租户", text)
        self.assertIn(
            "Tenant B（ID：201）：本期 30 次，前期 100 次，下降 70%。",
            text,
        )
        self.assertIn(
            "统计范围：10 月 22 日—10 月 28 日",
            text,
        )
        self.assertIn("数据采集：10 月 29 日 09:50，北京时间", text)
        self.assertIn("http://localhost:18000/agione#focus", text)
        delay.assert_called_once_with(first[0].pk)

    @patch("agione_ops.tasks.deliver_notification.delay")
    def test_inflight_delivery_is_not_sent_twice(self, delay):
        from datetime import timedelta
        from django.utils import timezone

        delivery = enqueue_analysis_notifications(
            self.rules, {}, self.analysis, trigger="scheduled",
            scheduled_date="2026-10-29",
        )[0]
        delivery.status = "sending"
        delivery.attempts = 1
        delivery.next_retry_at = timezone.now() + timedelta(minutes=15)
        delivery.save(update_fields=["status", "attempts", "next_retry_at"])
        with patch("agentcore_notifier.adapters.django.tasks.send.send_notification.run") as send:
            result = deliver_notification.run(delivery.pk)
        self.assertEqual(result["status"], "sending")
        send.assert_not_called()

    @patch("agione_ops.tasks.deliver_notification.delay")
    def test_older_scheduled_report_keeps_recent_issue_state(self, delay):
        from django.utils import timezone

        now = timezone.now()
        issue = NotificationIssue.objects.create(
            rules=self.rules, customer_id="999", reason="continuous_failure",
            active=True, finding={}, first_seen_at=now, last_seen_at=now,
        )
        created = enqueue_analysis_notifications(
            self.rules, {}, self.analysis, trigger="scheduled",
            scheduled_date="2026-10-29", preserve_issue_state=True,
        )
        issue.refresh_from_db()
        self.assertTrue(issue.active)
        self.assertIsNone(issue.resolved_at)
        self.assertEqual(len(created), 1)
        self.assertEqual(NotificationIssue.objects.filter(rules=self.rules).count(), 1)
        delay.assert_called_once()

    @patch("agione_ops.tasks.deliver_notification.delay")
    def test_scheduled_digest_is_distinct_and_once_per_day(self, delay):
        digest = enqueue_analysis_notifications(
            self.rules,
            {},
            self.analysis,
            trigger="scheduled",
            scheduled_date="2026-10-29",
        )
        duplicate = enqueue_analysis_notifications(
            self.rules,
            {},
            self.analysis,
            trigger="scheduled",
            scheduled_date="2026-10-29",
        )
        manual = enqueue_analysis_notifications(
            self.rules,
            {},
            self.analysis,
            trigger="manual",
        )

        self.assertEqual(len(digest), 1)
        self.assertEqual(duplicate, [])
        self.assertEqual(manual, [])
        self.assertEqual(NotificationDelivery.objects.count(), 1)
        self.assertEqual(
            digest[0].payload["scheduled_date"],
            "2026-10-29",
        )
        self.assertEqual(delay.call_count, 1)

    @patch("agione_ops.tasks.deliver_notification.delay")
    def test_manual_refresh_only_sends_new_urgent_events(self, delay):
        created = enqueue_analysis_notifications(
            self.rules,
            {},
            self.analysis,
            trigger="manual",
        )

        self.assertEqual(len(created), 1)
        text = created[0].payload["text"]
        self.assertIn("【AGIOne 实时异常提醒】", text)
        self.assertIn("持续调用失败", text)
        self.assertIn(
            "Tenant owner（ID：200）：最近 120 分钟内失败 1,006 次，"
            "成功 0 次；已识别原因：余额不足。",
            text,
        )
        self.assertIn(
            "事件观察：10 月 28 日 23:00—10 月 29 日 00:00"
            "（60 分钟），北京时间",
            text,
        )
        self.assertNotIn("统计范围：", text)
        self.assertNotIn("使用下降", text)
        self.assertEqual(
            NotificationIssue.objects.filter(active=True).count(),
            2,
        )
        delay.assert_called_once_with(created[0].pk)

    @patch("agione_ops.tasks.deliver_notification.delay")
    def test_automatic_refresh_sends_only_urgent_notification(self, delay):
        created = enqueue_analysis_notifications(
            self.rules,
            {},
            self.analysis,
            trigger="automatic",
        )

        self.assertEqual(len(created), 1)
        self.assertIn("实时异常提醒", created[0].payload["text"])
        self.assertNotIn("使用下降", created[0].payload["text"])
        self.assertTrue(NotificationDelivery.objects.exists())
        self.assertTrue(NotificationIssue.objects.exists())
        delay.assert_called_once_with(created[0].pk)

    @patch("agione_ops.tasks.deliver_notification.delay")
    def test_recovered_historical_anomaly_sends_one_complete_notice(
        self,
        delay,
    ):
        current = {
            **self.analysis,
            "alerts": [],
            "historical_alerts": [{
                "customer_id": "200",
                "customer_name": "Tenant owner",
                "reasons": ["continuous_failure", "balance_failure"],
                "failure_count": 6,
                "event_request_count": 8,
                "failure_rate_percent": 75,
                "event_start": "2026-10-29T09:05:00+08:00",
                "event_end": "2026-10-29T09:30:00+08:00",
                "recovered": True,
            }],
        }
        self.rules.config["send_recovered_history"] = True
        self.rules.save(update_fields=["config"])

        created = enqueue_analysis_notifications(
            self.rules,
            {},
            current,
            trigger="automatic",
        )

        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].kind, "recovered_history")
        text = created[0].payload["text"]
        self.assertIn("已恢复的历史异常", text)
        self.assertIn("10-29 09:05—10-29 09:30", text)
        self.assertIn("失败 6 次，成功 2 次", text)
        self.assertIn("巡检时已恢复", text)
        self.assertFalse(NotificationIssue.objects.exists())
        delay.assert_called_once_with(created[0].pk)

    @patch("agione_ops.tasks.deliver_notification.delay")
    def test_unconfirmed_historical_anomaly_does_not_claim_recovery(self, delay):
        current = {
            **self.analysis,
            "alerts": [],
            "historical_alerts": [{
                "customer_id": "200", "customer_name": "Tenant owner",
                "reasons": ["continuous_failure", "balance_failure"],
                "failure_count": 6, "event_request_count": 6,
                "failure_rate_percent": 100,
                "event_start": "2026-10-29T09:05:00+08:00",
                "event_end": "2026-10-29T09:30:00+08:00",
                "recovered": False,
            }],
        }
        created = enqueue_analysis_notifications(
            self.rules, {}, current, trigger="automatic",
        )
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].kind, "alert")
        text = created[0].payload["text"]
        self.assertIn("恢复状态待确认", text)
        self.assertNotIn("已恢复", text)
        delay.assert_called_once()

    @patch("agione_ops.tasks.deliver_notification.delay")
    def test_manual_complete_window_sends_recovery_once(self, delay):
        enqueue_analysis_notifications(
            self.rules,
            {},
            self.analysis,
            trigger="manual",
        )
        NotificationIssue.objects.update(
            first_seen_at=datetime(2026, 10, 29, 9, 0, tzinfo=ZONE),
        )
        no_evidence = enqueue_analysis_notifications(
            self.rules, self.analysis,
            {**self.analysis, "alerts": []}, trigger="manual",
        )
        self.assertEqual(no_evidence, [])
        self.assertTrue(NotificationIssue.objects.filter(active=True).exists())
        failed_again = enqueue_analysis_notifications(
            self.rules, self.analysis,
            {**self.analysis, "alerts": [], "recovery_evidence": {
                "200": {"success": "2026-10-29T10:35:00+08:00",
                        "failure": "2026-10-29T10:40:00+08:00"},
            }}, trigger="manual",
        )
        self.assertEqual(failed_again, [])
        self.assertTrue(NotificationIssue.objects.filter(active=True).exists())
        recovered = enqueue_analysis_notifications(
            self.rules,
            self.analysis,
            {
                **self.analysis,
                "window_end": datetime(
                    2026,
                    10,
                    29,
                    10,
                    50,
                    tzinfo=ZONE,
                ).isoformat(),
                "alerts": [],
                "recovery_evidence": {
                    "200": {"success": "2026-10-29T10:40:00+08:00"},
                },
            },
            trigger="manual",
        )
        duplicate = enqueue_analysis_notifications(
            self.rules,
            self.analysis,
            {
                **self.analysis,
                "window_end": datetime(
                    2026,
                    10,
                    29,
                    10,
                    51,
                    tzinfo=ZONE,
                ).isoformat(),
                "alerts": [],
            },
            trigger="manual",
        )

        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].kind, "recovery")
        self.assertIn(
            "【AGIOne 恢复提醒】",
            recovered[0].payload["text"],
        )
        self.assertEqual(duplicate, [])
        self.assertFalse(
            NotificationIssue.objects.filter(active=True).exists(),
        )
        self.assertEqual(delay.call_count, 2)

    @patch(
        "agione_ops.tasks.deliver_notification.delay",
        side_effect=ConnectionError("broker unavailable"),
    )
    def test_dispatch_failure_leaves_durable_pending_delivery(self, delay):
        created = enqueue_analysis_notifications(
            self.rules,
            {},
            {
                **self.analysis,
                "window_end": datetime(
                    2026,
                    10,
                    30,
                    tzinfo=ZONE,
                ).isoformat(),
            },
        )

        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].status, "pending")
        delay.assert_called_once()

    @patch("agione_ops.tasks.deliver_notification.delay")
    def test_periodic_retry_requeues_pending_delivery(self, delay):
        delivery = NotificationDelivery.objects.create(
            rules=self.rules,
            event_key="pending-key",
            issue_signature="pending-signature",
            kind="alert",
            payload={"text": "运营提醒"},
        )

        count = retry_notification_deliveries()

        self.assertEqual(count, 1)
        delay.assert_called_once_with(delivery.pk)

    @patch(
        "agentcore_notifier.adapters.django.tasks.send."
        "send_notification.run",
        return_value={"success": True, "response": {"code": 0}},
    )
    def test_delivery_records_success(self, send):
        delivery = NotificationDelivery.objects.create(
            rules=self.rules,
            event_key="success-key",
            issue_signature="signature",
            kind="alert",
            payload={"text": "运营提醒"},
        )

        result = deliver_notification(delivery.pk)

        delivery.refresh_from_db()
        self.assertEqual(result["status"], "sent")
        self.assertEqual(delivery.status, "sent")
        self.assertEqual(delivery.attempts, 1)
        self.assertIsNotNone(delivery.sent_at)
        self.assertEqual(
            send.call_args.kwargs["channel_uuid"],
            str(
                self.channel.uuid,
            ),
        )

    @patch(
        "agentcore_notifier.adapters.django.tasks.send."
        "send_notification.run",
        return_value={"success": False, "error": "temporary"},
    )
    def test_failed_delivery_is_retryable_without_losing_attempt(self, send):
        delivery = NotificationDelivery.objects.create(
            rules=self.rules,
            event_key="failure-key",
            issue_signature="signature",
            kind="alert",
            payload={"text": "运营提醒"},
        )

        result = deliver_notification(delivery.pk)

        delivery.refresh_from_db()
        self.assertEqual(result["status"], "retrying")
        self.assertEqual(delivery.status, "retrying")
        self.assertEqual(delivery.attempts, 1)
        self.assertTrue(delivery.error_message)
        self.assertIsNotNone(delivery.next_retry_at)

        deliver_notification(delivery.pk)
        final = deliver_notification(delivery.pk)

        delivery.refresh_from_db()
        self.assertEqual(final["status"], "failed")
        self.assertEqual(delivery.attempts, 3)
        self.assertEqual(send.call_count, 3)
