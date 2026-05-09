"""Tests for the Alibaba Cloud billing provider."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from cloud_billing.clouds.alibaba_provider import (
    AlibabaCloud,
    AlibabaConfig,
)


@pytest.mark.django_db
class TestAlibabaCloud:
    """Tests for AlibabaCloud."""

    def _make_provider(self):
        config = AlibabaConfig(
            api_key="test-ak",
            api_secret="test-sk",
            region="cn-hangzhou",
        )
        provider = AlibabaCloud(config)
        provider._client = Mock()
        return provider

    def test_extract_cash_balance_returns_cash_only(self):
        """Cash balance should be returned when credit is not present."""
        provider = self._make_provider()
        response = SimpleNamespace(
            body=SimpleNamespace(
                data=SimpleNamespace(
                    available_cash_amount=100.50,
                    credit_amount=None,
                )
            )
        )
        result = provider._extract_cash_balance(response)
        assert result == 100.50

    def test_extract_cash_balance_returns_cash_plus_credit(self):
        """Balance should be cash + credit for international accounts."""
        provider = self._make_provider()
        response = SimpleNamespace(
            body=SimpleNamespace(
                data=SimpleNamespace(
                    available_cash_amount=2840.65,
                    credit_amount=2000.00,
                )
            )
        )
        result = provider._extract_cash_balance(response)
        assert result == 4840.65

    def test_extract_cash_balance_returns_credit_only_when_no_cash(self):
        """Balance should be credit when cash is zero."""
        provider = self._make_provider()
        response = SimpleNamespace(
            body=SimpleNamespace(
                data=SimpleNamespace(
                    available_cash_amount=0,
                    credit_amount=500.00,
                )
            )
        )
        result = provider._extract_cash_balance(response)
        assert result == 500.00

    def test_extract_cash_balance_returns_none_when_both_missing(self):
        """Balance should be None when both cash and credit are missing."""
        provider = self._make_provider()
        response = SimpleNamespace(
            body=SimpleNamespace(
                data=SimpleNamespace()
            )
        )
        result = provider._extract_cash_balance(response)
        assert result is None

    def test_extract_cash_balance_no_duplicate_accumulation(self):
        """Balance should not be accumulated from multiple sources."""
        provider = self._make_provider()
        # Simulate multiple sources with different values
        response = SimpleNamespace(
            body=SimpleNamespace(
                data=SimpleNamespace(
                    available_cash_amount=100.00,
                    credit_amount=50.00,
                )
            )
        )
        # Call twice to ensure no side effects
        result1 = provider._extract_cash_balance(response)
        result2 = provider._extract_cash_balance(response)
        assert result1 == 150.00
        assert result2 == 150.00

    def test_build_balance_debug_info_includes_cash_and_credit(self):
        """Debug info should include cash and credit amounts."""
        provider = self._make_provider()
        response = SimpleNamespace(
            body=SimpleNamespace(
                data=SimpleNamespace(
                    available_cash_amount=2840.65,
                    credit_amount=2000.00,
                )
            )
        )
        result = provider._build_balance_debug_info(response)
        assert result["cash_amount"] == 2840.65
        assert result["credit_amount"] == 2000.00

    def test_get_resource_cost_breakdown_returns_formatted_items(self):
        """Resource cost breakdown should return formatted items."""
        provider = self._make_provider()
        provider._client.query_bill.return_value = SimpleNamespace(
            body=SimpleNamespace(
                data=SimpleNamespace(
                    items=SimpleNamespace(
                        item=[
                            SimpleNamespace(
                                pretax_amount=100.00,
                                product_name="ECS",
                                product_code="ecs",
                                currency="CNY",
                            ),
                            SimpleNamespace(
                                pretax_amount=50.00,
                                product_name="RDS",
                                product_code="rds",
                                currency="CNY",
                            ),
                        ]
                    )
                )
            )
        )
        result = provider.get_resource_cost_breakdown("2026-05")
        assert result["status"] == "success"
        assert len(result["items"]) == 2
        assert result["items"][0]["name"] == "ECS (ecs)"
        assert result["items"][0]["cost"] == 100.00
        assert result["items"][1]["name"] == "RDS (rds)"
        assert result["items"][1]["cost"] == 50.00

    def test_get_resource_cost_breakdown_filters_zero_cost(self):
        """Resource cost breakdown should filter out zero cost items."""
        provider = self._make_provider()
        provider._client.query_bill.return_value = SimpleNamespace(
            body=SimpleNamespace(
                data=SimpleNamespace(
                    items=SimpleNamespace(
                        item=[
                            SimpleNamespace(
                                pretax_amount=100.00,
                                product_name="ECS",
                                product_code="ecs",
                                currency="CNY",
                            ),
                            SimpleNamespace(
                                pretax_amount=0.00,
                                product_name="Free Tier",
                                product_code="free",
                                currency="CNY",
                            ),
                        ]
                    )
                )
            )
        )
        result = provider.get_resource_cost_breakdown("2026-05")
        assert result["status"] == "success"
        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "ECS (ecs)"

    def test_get_resource_cost_breakdown_accepts_yyyy_mm_dd(self):
        """get_resource_cost_breakdown should accept YYYY-MM-DD input."""
        provider = self._make_provider()
        provider._client.query_bill.return_value = SimpleNamespace(
            body=SimpleNamespace(
                data=SimpleNamespace(
                    items=SimpleNamespace(
                        item=[
                            SimpleNamespace(
                                pretax_amount=10.00,
                                product_name="CDN",
                                product_code="cdn",
                                currency="CNY",
                            ),
                        ]
                    )
                )
            )
        )
        result = provider.get_resource_cost_breakdown("2026-05-08")
        assert result["status"] == "success"
        assert len(result["items"]) == 1


class TestAlibabaOwnerExtraction:
    """Tests for owner extraction from Alibaba Cloud tags."""

    def _make_provider(self):
        config = AlibabaConfig(
            api_key="test-ak",
            api_secret="test-sk",
            region="cn-hangzhou",
        )
        provider = AlibabaCloud(config)
        provider._client = Mock()
        return provider

    def test_extract_owner_created_by(self):
        """Should extract owner from 'created_by' tag."""
        provider = self._make_provider()
        tags = {"created_by": "zhangsan", "env": "prod"}
        assert provider._extract_owner_from_tags(tags) == "zhangsan"

    def test_extract_owner_createdby_case_insensitive(self):
        """Should match 'CreatedBy' case-insensitively."""
        provider = self._make_provider()
        tags = {"CreatedBy": "lisi"}
        assert provider._extract_owner_from_tags(tags) == "lisi"

    def test_extract_owner_owner_tag(self):
        """Should extract owner from 'Owner' tag."""
        provider = self._make_provider()
        tags = {"Owner": "wangwu", "team": "backend"}
        assert provider._extract_owner_from_tags(tags) == "wangwu"

    def test_extract_owner_no_match(self):
        """Should return empty string when no owner tag found."""
        provider = self._make_provider()
        tags = {"env": "prod", "team": "backend"}
        assert provider._extract_owner_from_tags(tags) == ""

    def test_extract_owner_empty_tags(self):
        """Should return empty string for empty tags dict."""
        provider = self._make_provider()
        assert provider._extract_owner_from_tags({}) == ""

    def test_extract_owner_none_tags(self):
        """Should return empty string for None tags."""
        provider = self._make_provider()
        assert provider._extract_owner_from_tags(None) == ""
