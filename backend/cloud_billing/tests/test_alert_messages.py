"""Tests for cloud_billing alert message generation."""

from types import SimpleNamespace

import pytest
from cloud_billing.alert_messages import (
    _format_resource_cost_lines,
    build_alert_message,
    build_alert_message_from_record,
    build_alert_sections,
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
        assert "当月累计费用明细" in lines[0]
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
        assert "Monthly Cost Breakdown" in lines[0]

    def test_chinese_language(self):
        """Should use Chinese header for zh language."""
        lines = _format_resource_cost_lines(
            [{"name": "x", "cost": 1}], "CNY", "zh_Hans",
        )
        assert "当月累计费用明细" in lines[0]

    def test_english_language(self):
        """Should use English header for en language."""
        lines = _format_resource_cost_lines(
            [{"name": "x", "cost": 1}], "USD", "en",
        )
        assert "Monthly Cost Breakdown" in lines[0]


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
        assert "当月累计" in message
        assert "金额阈值" in message
        assert "上一小时" in message
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
        assert "Month total" in message
        assert "Amount threshold" in message
        assert "Previous hour" in message
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
        assert "当月累计" in message
        assert "上一小时" in message
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
        assert "Month total" in message
        assert "Previous hour" in message
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
        assert "当月累计费用明细" in message
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
        assert "Monthly Cost Breakdown" in message
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

    def test_growth_alert_displays_metrics(self, alert_rule):
        """Growth alert should display key metrics in two-column format."""
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
        assert "Month total" in message
        assert "Previous hour" in message
        assert "200.00 USD" in message
        assert "50.00 USD" in message

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
        assert "Monthly Cost Breakdown" in message
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


# ── build_alert_sections: metrics and highlights ───────────────────


class TestBuildAlertSections:
    """Test build_alert_sections for notification service payload generation."""

    @pytest.fixture
    def common_params(self, alert_rule):
        """Common parameters for alert section tests."""
        return dict(
            provider_name="AWS",
            provider_notes="生产环境",
            provider_tags=["核心"],
            account_id="123456789",
            current_cost=1500.00,
            previous_cost=800.00,
            increase_cost=700.00,
            increase_percent=87.5,
            current_balance=500.00,
            current_days_remaining=None,
            currency="USD",
            alert_rule=alert_rule,
        )

    def test_cost_alert_metrics_highlight_current_total(self, common_params):
        """Cost threshold alert should highlight current total."""
        sections = build_alert_sections(
            **common_params,
            cost_threshold_triggered=True,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="zh-Hans",
        )
        metrics = sections["metrics"]
        # First metric (current total) should be highlighted
        assert metrics[0]["highlight"] is True
        # Second metric (previous hour) should NOT be highlighted
        assert metrics[1]["highlight"] is False

    def test_cost_alert_metrics_include_growth_info(self, common_params):
        """Cost threshold alert should include growth rate and increase amount."""
        sections = build_alert_sections(
            **common_params,
            cost_threshold_triggered=True,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="zh-Hans",
        )
        metrics = sections["metrics"]
        # Should have 4 metrics: current total, previous hour, growth rate, increase
        assert len(metrics) == 4
        # Growth rate should NOT be highlighted
        assert metrics[2]["highlight"] is False
        # Increase amount should NOT be highlighted
        assert metrics[3]["highlight"] is False

    def test_growth_alert_metrics_highlight_triggered(self, common_params):
        """Growth alert should highlight growth rate and increase amount."""
        sections = build_alert_sections(
            **common_params,
            cost_threshold_triggered=False,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="zh-Hans",
        )
        metrics = sections["metrics"]
        # First metric (current total) should NOT be highlighted
        assert metrics[0]["highlight"] is False
        # Second metric (previous hour) should NOT be highlighted
        assert metrics[1]["highlight"] is False
        # Third metric (increase amount) should be highlighted
        assert metrics[2]["highlight"] is True
        # Fourth metric (growth rate) should be highlighted
        assert metrics[3]["highlight"] is True

    def test_cost_alert_thresholds(self, common_params):
        """Cost threshold alert should include cost threshold."""
        sections = build_alert_sections(
            **common_params,
            cost_threshold_triggered=True,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="zh-Hans",
        )
        thresholds = sections["thresholds"]
        # Should have at least cost threshold
        threshold_labels = [t["label"] for t in thresholds]
        assert "Cost" in threshold_labels or "花费" in threshold_labels
        threshold_values = [t["value"] for t in thresholds]
        assert any("100.00 USD" in v for v in threshold_values)

    def test_growth_alert_thresholds(self, common_params):
        """Growth alert should include growth and amount thresholds."""
        sections = build_alert_sections(
            **common_params,
            cost_threshold_triggered=False,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="zh-Hans",
        )
        thresholds = sections["thresholds"]
        threshold_labels = [t["label"] for t in thresholds]
        threshold_values = [t["value"] for t in thresholds]
        # Should have growth percentage threshold
        assert "Growth %" in threshold_labels or "百分比阈值" in threshold_labels
        # Should have amount threshold
        assert "Amount" in threshold_labels or "金额阈值" in threshold_labels
        # Verify the number of thresholds (should have growth %, amount, cost)
        assert len(thresholds) >= 2

    def test_labels_cost_breakdown_localization(self, common_params):
        """cost_breakdown label should be localized correctly."""
        # Chinese
        sections_zh = build_alert_sections(
            **common_params,
            cost_threshold_triggered=True,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="zh-Hans",
        )
        assert sections_zh["labels"]["cost_breakdown"] == "当月累计费用明细"

        # English
        sections_en = build_alert_sections(
            **common_params,
            cost_threshold_triggered=True,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="en",
        )
        assert sections_en["labels"]["cost_breakdown"] == "Monthly Cost Breakdown"

    def test_trigger_info_included(self, common_params):
        """Sections should include trigger icon and text."""
        # Cost alert
        sections = build_alert_sections(
            **common_params,
            cost_threshold_triggered=True,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="zh-Hans",
        )
        assert sections["trigger_icon"] == "📊"
        assert "alert_type" in sections

    def test_balance_alert_metrics_structure(self, alert_rule):
        """Balance alert should have correct metrics structure."""
        sections = build_alert_sections(
            provider_name="AWS",
            provider_notes="",
            provider_tags=[],
            account_id="123",
            current_cost=80.00,
            previous_cost=70.00,
            increase_cost=10.00,
            increase_percent=14.29,
            current_balance=30.00,
            current_days_remaining=None,
            currency="USD",
            alert_rule=alert_rule,
            cost_threshold_triggered=False,
            balance_threshold_triggered=True,
            days_remaining_threshold_triggered=False,
            language="en",
        )
        assert sections["alert_type"] == "Balance Alert"
        assert sections["trigger_icon"] == "💰"
        assert sections["balance"] is not None
        assert sections["balance"]["value"] == 30.00

    def test_days_remaining_alert_structure(self, alert_rule):
        """Days remaining alert should have correct structure."""
        sections = build_alert_sections(
            provider_name="AWS",
            provider_notes="",
            provider_tags=[],
            account_id="123",
            current_cost=80.00,
            previous_cost=70.00,
            increase_cost=10.00,
            increase_percent=14.29,
            current_balance=500.00,
            current_days_remaining=5,
            currency="USD",
            alert_rule=alert_rule,
            cost_threshold_triggered=False,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=True,
            language="en",
        )
        assert sections["alert_type"] == "Days Remaining Alert"
        assert sections["trigger_icon"] == "⏳"

    def test_metrics_have_required_fields(self, common_params):
        """All metrics should have label, value, and highlight fields."""
        sections = build_alert_sections(
            **common_params,
            cost_threshold_triggered=True,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="en",
        )
        for metric in sections["metrics"]:
            assert "label" in metric
            assert "value" in metric
            assert "highlight" in metric
            assert isinstance(metric["highlight"], bool)

    def test_thresholds_have_required_fields(self, common_params):
        """All thresholds should have label and value fields."""
        sections = build_alert_sections(
            **common_params,
            cost_threshold_triggered=True,
            balance_threshold_triggered=False,
            days_remaining_threshold_triggered=False,
            language="en",
        )
        for threshold in sections["thresholds"]:
            assert "label" in threshold
            assert "value" in threshold
