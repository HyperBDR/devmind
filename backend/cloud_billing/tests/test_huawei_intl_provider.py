"""Tests for the Huawei International cloud billing provider."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from cloud_billing.clouds.huawei_intl_provider import (
    HuaweiIntlCloud,
    HuaweiIntlConfig,
)


@pytest.mark.django_db
class TestHuaweiIntlCloud:
    """Tests for HuaweiIntlCloud."""

    def _make_provider(self):
        config = HuaweiIntlConfig(
            api_key="test-ak",
            api_secret="test-sk",
            region="ap-southeast-1",
            project_id="project-1",
        )
        provider = HuaweiIntlCloud(config)
        provider._client = Mock()
        return provider

    @patch("cloud_billing.clouds.huawei_intl_provider.model")
    def test_get_billing_info_supports_show_customer_monthly_sum(
        self, mock_model
    ):
        provider = self._make_provider()
        request = SimpleNamespace(bill_cycle=None)
        mock_model.ShowCustomerMonthlySumRequest = Mock(return_value=request)
        mock_model.ListMonthlyExpendituresRequest = None
        provider._client.show_customer_monthly_sum.return_value = (
            SimpleNamespace(
                currency="USD",
                bill_sums=[
                    SimpleNamespace(
                        measure_id=1,
                        consume_amount=10.5,
                        service_type_name="compute",
                        resource_type_name="ecs",
                    )
                ],
            )
        )

        result = provider.get_billing_info("2025-01")

        assert result["status"] == "success"
        assert result["data"]["total_cost"] == 10.5
        assert request.bill_cycle == "2025-01"

    @patch("cloud_billing.clouds.huawei_intl_provider.model")
    def test_get_billing_info_includes_balance(self, mock_model):
        provider = self._make_provider()
        billing_request = SimpleNamespace(bill_cycle=None)
        balance_request = SimpleNamespace()

        def _resolve_request():
            if getattr(_resolve_request, "count", 0) == 0:
                _resolve_request.count = 1
                return billing_request
            return balance_request

        mock_model.ShowCustomerMonthlySumRequest = Mock(
            side_effect=_resolve_request
        )
        mock_model.ShowCustomerAccountBalancesRequest = Mock(
            return_value=balance_request
        )
        mock_model.ListMonthlyExpendituresRequest = None

        provider._client.show_customer_monthly_sum.return_value = (
            SimpleNamespace(
                currency="USD",
                bill_sums=[
                    SimpleNamespace(
                        measure_id=1,
                        consume_amount=9.5,
                        service_type_name="compute",
                        resource_type_name="ecs",
                    )
                ],
            )
        )
        provider._client.show_customer_account_balances.return_value = (
            SimpleNamespace(
                currency="USD",
                measure_id=1,
                debt_amount=0,
                account_balances=[
                    SimpleNamespace(
                        account_id="acc-1",
                        account_type=2,
                        amount=321.12,
                        currency="USD",
                        designated_amount=0,
                        credit_amount=321.12,
                        measure_id=1,
                    )
                ],
            )
        )

        result = provider.get_billing_info("2025-01")

        assert result["status"] == "success"
        assert result["data"]["balance"] == 321.12
        assert result["data"]["balance_debug"]["status"] == "success"
        assert result["data"]["balance_debug"]["selected_account_type"] == 2
        assert result["data"]["balance_debug"]["balance_type"] == (
            "credit_amount"
        )
        assert result["data"]["balance_debug"]["account_balances"][0]["converted_amount"] == 321.12

    @patch("cloud_billing.clouds.huawei_intl_provider.model")
    def test_get_billing_info_converts_balance_measure_id(self, mock_model):
        provider = self._make_provider()
        billing_request = SimpleNamespace(bill_cycle=None)
        balance_request = SimpleNamespace()

        def _resolve_request():
            if getattr(_resolve_request, "count", 0) == 0:
                _resolve_request.count = 1
                return billing_request
            return balance_request

        mock_model.ShowCustomerMonthlySumRequest = Mock(
            side_effect=_resolve_request
        )
        mock_model.ShowCustomerAccountBalancesRequest = Mock(
            return_value=balance_request
        )
        mock_model.ListMonthlyExpendituresRequest = None

        provider._client.show_customer_monthly_sum.return_value = (
            SimpleNamespace(
                currency="USD",
                bill_sums=[],
            )
        )
        provider._client.show_customer_account_balances.return_value = (
            SimpleNamespace(
                currency="USD",
                measure_id=3,
                debt_amount=50,
                account_balances=[
                    SimpleNamespace(
                        account_id="acc-1",
                        account_type=2,
                        amount=12345,
                        currency="USD",
                        designated_amount=0,
                        credit_amount=12345,
                        measure_id=3,
                    ),
                    SimpleNamespace(
                        account_id="acc-2",
                        account_type=1,
                        amount=20000,
                        currency="USD",
                        designated_amount=0,
                        credit_amount=0,
                        measure_id=3,
                    ),
                ],
            )
        )

        result = provider.get_billing_info("2025-01")

        assert result["status"] == "success"
        assert result["data"]["balance"] == 123.45
        assert result["data"]["balance_debug"]["measure_id"] == 3
        assert result["data"]["balance_debug"]["debt_amount"] == 0.5
        assert result["data"]["balance_debug"]["selected_account_type"] == 2
        assert (
            result["data"]["balance_debug"]["account_balances"][0][
                "converted_amount"
            ]
            == 123.45
        )
