"""Tests for the Huawei cloud billing provider."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cloud_billing.clouds.huawei_provider import HuaweiCloud, HuaweiConfig


@pytest.mark.django_db
class TestHuaweiCloud:
    """Tests for HuaweiCloud."""

    def _make_provider(self):
        config = HuaweiConfig(
            api_key="test-ak",
            api_secret="test-sk",
            region="cn-north-1",
            project_id="project-1",
        )
        provider = HuaweiCloud(config)
        provider._client = Mock()
        return provider

    def test_get_billing_info_includes_balance(self):
        provider = self._make_provider()
        provider._query_billing_api = Mock(
            return_value=SimpleNamespace(
                currency="CNY",
                bill_sums=[
                    SimpleNamespace(
                        measure_id=1,
                        consume_amount=120.5,
                        service_type_name="compute",
                        resource_type_name="ecs",
                    )
                ],
            )
        )
        provider._query_balance_api = Mock(
            return_value=SimpleNamespace(
                currency="CNY",
                account_balances=[
                    SimpleNamespace(
                        account_id="acc-1",
                        account_type=1,
                        amount=888.88,
                        currency="CNY",
                    )
                ],
            )
        )

        result = provider.get_billing_info("2025-01")

        assert result["status"] == "success"
        assert result["data"]["total_cost"] == 120.5
        assert result["data"]["balance"] == 888.88
        assert result["data"]["balance_debug"]["status"] == "success"
