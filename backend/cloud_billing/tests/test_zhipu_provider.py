"""Tests for the Zhipu AI billing provider."""

from unittest.mock import Mock, patch

import pytest

from cloud_billing.clouds.zhipu_provider import ZhipuCloud, ZhipuConfig


@pytest.mark.django_db
class TestZhipuConfig:
    def test_config_from_values(self):
        config = ZhipuConfig(
            username="tester",
            password="secret",
        )
        assert config.username == "tester"
        assert config.password == "secret"


@pytest.mark.django_db
class TestZhipuCloud:
    def _make_provider(self):
        config = ZhipuConfig(
            username="tester",
            password="secret",
        )
        return ZhipuCloud(config)

    @patch("cloud_billing.clouds.zhipu_provider.requests.Session.request")
    def test_get_billing_info_parses_response(self, mock_request):
        provider = self._make_provider()

        login_response = Mock()
        login_response.raise_for_status.return_value = None
        login_response.json.return_value = {
            "data": {"accessToken": "a.b.c"}
        }

        bill_response = Mock()
        bill_response.raise_for_status.return_value = None
        bill_response.json.return_value = {
            "rows": [
                    {
                        "billingMonth": "2026-03",
                        "settlementAmount": "123.45",
                        "paidAmount": "123.45",
                        "currency": "CNY",
                    }
                ],
            "code": 200,
            "msg": "查询成功",
        }

        balance_response = Mock()
        balance_response.raise_for_status.return_value = None
        balance_response.json.return_value = {
            "data": {
                "availableBalance": "88.80",
                "currency": "CNY",
            }
        }

        mock_request.side_effect = [
            login_response,
            bill_response,
            balance_response,
        ]

        result = provider.get_billing_info("2026-03")

        assert result["status"] == "success"
        data = result["data"]
        assert data["total_cost"] == 123.45
        assert data["balance"] == 88.8
        assert data["currency"] == "CNY"
        assert data["service_costs"]["智谱 AI"] == 123.45
        assert data["items"][0]["amount"] == 123.45
        assert data["balance_debug"]["status"] == "success"

        login_call = mock_request.call_args_list[0]
        assert login_call.kwargs["url"] == "https://bigmodel.cn/api/auth/login"

        bill_call = mock_request.call_args_list[1]
        assert (
            bill_call.kwargs["url"]
            == "https://bigmodel.cn/api/finance/monthlyBill/aggregatedMonthlyBills"
        )
        assert bill_call.kwargs["params"]["billingMonthStart"] == "2026-03"
        assert "bigmodel-organization" not in bill_call.kwargs["headers"]

    @patch("cloud_billing.clouds.zhipu_provider.requests.Session.request")
    def test_validate_credentials_only_requires_login(self, mock_request):
        provider = self._make_provider()

        login_response = Mock()
        login_response.raise_for_status.return_value = None
        login_response.json.return_value = {
            "data": {"accessToken": "a.b.c"}
        }
        mock_request.return_value = login_response

        assert provider.validate_credentials() is True
        assert mock_request.call_count == 1
