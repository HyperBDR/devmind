"""Tests for cloud_billing alert message generation."""

from types import SimpleNamespace

import pytest
from cloud_billing.alert_messages import (
    _format_resource_cost_lines,
    build_alert_message,
    build_alert_message_from_record,
)


@pytest.fixture
def alert_rule():
    return SimpleNamespace(
        cost_threshold=100.00,
        balance_threshold=50.00,
        days_remaining_threshold=7,
        growth_threshold=10.00,
        growth_amount_threshold=50.00,
    )


# ── _format_resource_cost_lines ────────────────────────────────


class TestFormatResourceCostLines:
    """Test the _format_resource_cost_lines helper."""

    def test_basic_items(self):
        """Should format items as table with Resource/Cost columns."""
        items = [
            {"name": "ECS", "cost": 100.0},
            {"name": "RDS", "cost": 50.0},
        ]
        lines = _format_resource_cost_lines(
            items, "CNY", "zh_Hans",
        )
        # header + table header + separator + 2 data rows
        assert len(lines) == 5
        assert "费用明细" in lines[0]
        assert "资源" in lines[1]
        assert "ECS" in lines[3]
        assert "100.00 CNY" in lines[3]
        assert "RDS" in lines[4]

    def test_owner_info_displayed(self):
        """Should include owner column when any item has owner."""
        items = [
            {
                "name": "ECS",
                "cost": 100.0,
                "owner": "zhangsan",
            },
            {"name": "RDS", "cost": 50.0},
        ]
        lines = _format_resource_cost_lines(
            items, "CNY", "zh_Hans",
        )
        assert "创建者" in lines[1]
        assert "zhangsan" in lines[3]

    def test_max_items_limit(self):
        """Should limit items to max_items."""
        items = [
            {"name": f"svc_{i}", "cost": float(i)}
            for i in range(10)
        ]
        lines = _format_resource_cost_lines(
            items, "USD", "en", max_items=3,
        )
        # header + table header + separator + 3 data rows
        assert len(lines) == 6

    def test_service_name_fallback(self):
        """Should use service_name if name is missing."""
        items = [{"service_name": "EC2", "cost": 80.0}]
        lines = _format_resource_cost_lines(
            items, "USD", "en",
        )
        # data row is line index 3
        assert "EC2" in lines[3]

    def test_unknown_fallback(self):
        """Should use 'Unknown' if both name and service_name missing."""
        items = [{"cost": 10.0}]
        lines = _format_resource_cost_lines(
            items, "USD", "en",
        )
        assert "Unknown" in lines[3]

    def test_empty_items(self):
        """Should handle empty items list."""
        lines = _format_resource_cost_lines([], "USD", "en")
        assert len(lines) == 1  # header only
        assert "Cost breakdown" in lines[0]

    def test_chinese_language(self):
        """Should use Chinese header for zh language."""
        lines = _format_resource_cost_lines(
            [{"name": "x", "cost": 1}], "CNY", "zh_Hans",
        )
        assert "费用明细" in lines[0]

    def test_english_language(self):
        """Should use English header for en language."""
        lines = _format_resource_cost_lines(
            [{"name": "x", "cost": 1}], "USD", "en",
        )
        assert "Cost breakdown" in lines[0]


# ── build_alert_message: localization ──────────────────────────


class TestAlertMessageLocalization:
    """Test alert messages are properly localized."""

    def test_cost_alert_chinese(self, alert_rule):
        """Cost alert should be in Chinese when language is zh-Hans."""
        message = build_alert_message(
            provider_name="AWS",
            provider_notes="生产环境",
            provider_tags=["核心"],
            account_id="123456789",
            current_cost=150.00,
            previous_cost=80.00,
            increase_cost=70.00,
            increase_percent=87.50,
            current_balance=500.00,
            current_days_remaining=None,
            currency="CNY",
            alert_rule=alert_rule,
            cost_threshold_triggered=True,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="zh-Hans",
        )
        assert "告警类型" in message
        assert "成本阈值告警" in message
        assert "当前累计成本" in message
        assert "告警阈值" in message
        assert "当前余额" in message
        assert "告警说明" in message

    def test_cost_alert_english(self, alert_rule):
        """Cost alert should be in English when language is en."""
        message = build_alert_message(
            provider_name="AWS",
            provider_notes="Production",
            provider_tags=["core"],
            account_id="123456789",
            current_cost=150.00,
            previous_cost=80.00,
            increase_cost=70.00,
            increase_percent=87.50,
            current_balance=500.00,
            current_days_remaining=None,
            currency="USD",
            alert_rule=alert_rule,
            cost_threshold_triggered=True,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="en",
        )
        assert "Alert type" in message
        assert "Cost threshold alert" in message
        assert "Current total cost" in message
        assert "Alert threshold" in message
        assert "Current balance" in message
        assert "Alert description" in message

    def test_growth_alert_chinese(self, alert_rule):
        """Growth alert should be in Chinese when language is zh-Hans."""
        message = build_alert_message(
            provider_name="华为云",
            provider_notes="",
            provider_tags=[],
            account_id="default",
            current_cost=396.99,
            previous_cost=2.23,
            increase_cost=394.76,
            increase_percent=17702.24,
            current_balance=4432.51,
            current_days_remaining=None,
            currency="CNY",
            alert_rule=alert_rule,
            cost_threshold_triggered=False,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="zh-Hans",
        )
        assert "告警类型" in message
        assert "成本增长告警" in message
        assert "当前累计成本" in message
        assert "上一小时成本" in message
        assert "增加金额" in message
        assert "增长率" in message
        assert "百分比阈值" in message
        assert "告警说明" in message
        assert "账单增长已超过设定阈值" in message

    def test_growth_alert_english(self, alert_rule):
        """Growth alert should be in English when language is en."""
        message = build_alert_message(
            provider_name="Huawei Cloud",
            provider_notes="",
            provider_tags=[],
            account_id="default",
            current_cost=396.99,
            previous_cost=2.23,
            increase_cost=394.76,
            increase_percent=17702.24,
            current_balance=4432.51,
            current_days_remaining=None,
            currency="USD",
            alert_rule=alert_rule,
            cost_threshold_triggered=False,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="en",
        )
        assert "Alert type" in message
        assert "Cost growth alert" in message
        assert "Current total cost" in message
        assert "Previous hour cost" in message
        assert "Increase amount" in message
        assert "Growth rate" in message
        assert "Percentage threshold" in message
        assert "Alert description" in message
        assert "Billing growth exceeds the configured threshold" in message

    def test_balance_alert_chinese(self, alert_rule):
        """Balance alert should be in Chinese when language is zh-Hans."""
        message = build_alert_message(
            provider_name="AWS",
            provider_notes="",
            provider_tags=[],
            account_id="123456789",
            current_cost=80.00,
            previous_cost=70.00,
            increase_cost=10.00,
            increase_percent=14.29,
            current_balance=30.00,
            current_days_remaining=None,
            currency="CNY",
            alert_rule=alert_rule,
            cost_threshold_triggered=False,
            balance_threshold_triggered=True,
            days_remaining_threshold_triggered=False,
            language="zh-Hans",
        )
        assert "告警类型" in message
        assert "余额阈值告警" in message
        assert "当前余额" in message
        assert "告警阈值" in message

    def test_days_remaining_alert_chinese(self, alert_rule):
        """Days remaining alert should be in Chinese."""
        message = build_alert_message(
            provider_name="AWS",
            provider_notes="",
            provider_tags=[],
            account_id="123456789",
            current_cost=80.00,
            previous_cost=70.00,
            increase_cost=10.00,
            increase_percent=14.29,
            current_balance=500.00,
            current_days_remaining=5,
            currency="CNY",
            alert_rule=alert_rule,
            cost_threshold_triggered=False,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=True,
            language="zh-Hans",
        )
        assert "告警类型" in message
        assert "预计使用天数告警" in message
        assert "当前余额" in message
        assert "预计使用天数" in message
        assert "告警阈值" in message


# ── build_alert_message: resource cost items ───────────────────


class TestAlertResourceCostBreakdown:
    """Test resource cost breakdown display in alerts."""

    def test_cost_alert_with_resource_breakdown(self, alert_rule):
        """Cost alert should include resource breakdown."""
        resource_costs = [
            {"name": "ECS", "cost": 80.0},
            {"name": "RDS", "cost": 45.0},
            {"name": "OSS", "cost": 20.0},
        ]
        message = build_alert_message(
            provider_name="阿里云",
            provider_notes="",
            provider_tags=[],
            account_id="123456789",
            current_cost=150.00,
            previous_cost=80.00,
            increase_cost=70.00,
            increase_percent=87.50,
            current_balance=500.00,
            current_days_remaining=None,
            currency="CNY",
            alert_rule=alert_rule,
            cost_threshold_triggered=True,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="zh-Hans",
            resource_cost_items=resource_costs,
        )
        assert "费用明细" in message
        assert "ECS" in message
        assert "RDS" in message
        assert "OSS" in message

    def test_growth_alert_with_resource_breakdown(self, alert_rule):
        """Growth alert should include resource breakdown."""
        resource_costs = [
            {"name": "EC2", "cost": 100.0},
            {"name": "S3", "cost": 50.0},
        ]
        message = build_alert_message(
            provider_name="AWS",
            provider_notes="",
            provider_tags=[],
            account_id="123456789",
            current_cost=200.00,
            previous_cost=50.00,
            increase_cost=150.00,
            increase_percent=300.00,
            current_balance=1000.00,
            current_days_remaining=None,
            currency="USD",
            alert_rule=alert_rule,
            cost_threshold_triggered=False,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="en",
            resource_cost_items=resource_costs,
        )
        assert "Cost breakdown" in message
        assert "EC2" in message
        assert "S3" in message

    def test_resource_breakdown_with_owner(self, alert_rule):
        """Resource cost items should show owner when present."""
        resource_costs = [
            {"name": "ECS", "cost": 80.0, "owner": "zhangsan"},
            {"name": "RDS", "cost": 45.0},
        ]
        message = build_alert_message(
            provider_name="阿里云",
            provider_notes="",
            provider_tags=[],
            account_id="123456789",
            current_cost=150.00,
            previous_cost=80.00,
            increase_cost=70.00,
            increase_percent=87.50,
            current_balance=500.00,
            current_days_remaining=None,
            currency="CNY",
            alert_rule=alert_rule,
            cost_threshold_triggered=True,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="zh-Hans",
            resource_cost_items=resource_costs,
        )
        assert "zhangsan" in message
        assert "RDS" in message

    def test_growth_alert_has_balance(self, alert_rule):
        """Growth alert should display current balance."""
        message = build_alert_message(
            provider_name="AWS",
            provider_notes="",
            provider_tags=[],
            account_id="123456789",
            current_cost=200.00,
            previous_cost=50.00,
            increase_cost=150.00,
            increase_percent=300.00,
            current_balance=1000.00,
            current_days_remaining=None,
            currency="USD",
            alert_rule=alert_rule,
            cost_threshold_triggered=False,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="en",
        )
        assert "Current balance" in message
        assert "1000.00 USD" in message

    def test_no_resource_breakdown_when_empty(self, alert_rule):
        """Should not show cost breakdown when resource_cost_items is empty."""
        message = build_alert_message(
            provider_name="AWS",
            provider_notes="",
            provider_tags=[],
            account_id="123456789",
            current_cost=150.00,
            previous_cost=80.00,
            increase_cost=70.00,
            increase_percent=87.50,
            current_balance=500.00,
            current_days_remaining=None,
            currency="USD",
            alert_rule=alert_rule,
            cost_threshold_triggered=True,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="en",
            resource_cost_items=[],
        )
        assert "Cost breakdown" not in message

    def test_no_resource_breakdown_when_none(self, alert_rule):
        """Should not show cost breakdown when resource_cost_items is None."""
        message = build_alert_message(
            provider_name="AWS",
            provider_notes="",
            provider_tags=[],
            account_id="123456789",
            current_cost=150.00,
            previous_cost=80.00,
            increase_cost=70.00,
            increase_percent=87.50,
            current_balance=500.00,
            current_days_remaining=None,
            currency="USD",
            alert_rule=alert_rule,
            cost_threshold_triggered=True,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="en",
        )
        assert "Cost breakdown" not in message

    def test_no_balance_when_none(self, alert_rule):
        """Should not show balance when current_balance is None."""
        message = build_alert_message(
            provider_name="AWS",
            provider_notes="",
            provider_tags=[],
            account_id="123456789",
            current_cost=150.00,
            previous_cost=80.00,
            increase_cost=70.00,
            increase_percent=87.50,
            current_balance=None,
            current_days_remaining=None,
            currency="USD",
            alert_rule=alert_rule,
            cost_threshold_triggered=True,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="en",
        )
        assert "Current balance" not in message


# ── build_alert_message_from_record ────────────────────────────


class TestBuildAlertMessageFromRecord:
    """Test build_alert_message_from_record."""

    def test_passes_resource_cost_items(self, alert_rule):
        """Should pass resource_cost_items to build_alert_message."""
        resource_costs = [
            {"name": "EC2", "cost": 100.0, "owner": "alice"},
        ]
        record = SimpleNamespace(
            alert_rule=alert_rule,
            alert_type="cost",
            current_cost=150.00,
            previous_cost=80.00,
            increase_cost=70.00,
            increase_percent=87.50,
            current_balance=500.00,
            balance_threshold=None,
            current_days_remaining=None,
            days_remaining_threshold=None,
            currency="USD",
            alert_message="",
            provider=SimpleNamespace(
                display_name="AWS",
                notes="",
                tags=[],
                config={},
            ),
        )
        message = build_alert_message_from_record(
            record, "en", resource_cost_items=resource_costs,
        )
        assert "Cost breakdown" in message
        assert "EC2" in message
        assert "alice" in message

    def test_no_resource_costs_when_not_passed(self, alert_rule):
        """Should not show cost breakdown when not passed."""
        record = SimpleNamespace(
            alert_rule=alert_rule,
            alert_type="cost",
            current_cost=150.00,
            previous_cost=80.00,
            increase_cost=70.00,
            increase_percent=87.50,
            current_balance=500.00,
            balance_threshold=None,
            current_days_remaining=None,
            days_remaining_threshold=None,
            currency="USD",
            alert_message="",
            provider=SimpleNamespace(
                display_name="AWS",
                notes="",
                tags=[],
                config={},
            ),
        )
        message = build_alert_message_from_record(
            record, "en",
        )
        assert "Cost breakdown" not in message
