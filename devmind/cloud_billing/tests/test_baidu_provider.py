"""Tests for the Baidu Cloud billing provider."""

from datetime import date
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import RequestException

from cloud_billing.clouds.baidu_provider import (
    BaiduCloud,
    BaiduConfig,
)


@pytest.mark.django_db
class TestBaiduConfig:
    def test_config_from_values(self):
        config = BaiduConfig(
            api_key="ak",
            api_secret="sk",
        )
        assert config.api_key == "ak"
        assert config.api_secret == "sk"


@pytest.mark.django_db
class TestBaiduCloud:
    def _make_provider(self):
        config = BaiduConfig(
            api_key="ak",
            api_secret="sk",
        )
        return BaiduCloud(config)

    @patch("cloud_billing.clouds.baidu_provider.requests.Session.request")
    def test_get_billing_info_parses_response(self, mock_request):
        provider = self._make_provider()
        postpay_response = Mock()
        postpay_response.raise_for_status.return_value = None
        postpay_response.json.return_value = {
            "result": {
                "items": [
                    {
                        "accountId": "10001",
                        "serviceTypeName": "云服务器BCC",
                        "financePrice": "12.34",
                        "currency": "CNY",
                        "billId": "bill-1",
                    }
                ],
                "totalCount": 1,
            }
        }
        prepay_response = Mock()
        prepay_response.raise_for_status.return_value = None
        prepay_response.json.return_value = {
            "result": {
                "items": [
                    {
                        "accountId": "10001",
                        "serviceTypeName": "对象存储BOS",
                        "financePrice": "7.66",
                        "currency": "CNY",
                        "billId": "bill-2",
                    }
                ],
                "totalCount": 1,
            }
        }
        balance_response = Mock()
        balance_response.raise_for_status.return_value = None
        balance_response.json.return_value = {
            "result": {
                "accountId": "10001",
                "cashBalance": "520.00",
                "availableBalance": "520.00",
                "currency": "CNY",
            }
        }
        mock_request.side_effect = [
            postpay_response,
            prepay_response,
            balance_response,
        ]

        result = provider.get_billing_info("2025-01")

        assert result["status"] == "success"
        data = result["data"]
        assert data["total_cost"] == 20.0
        assert data["balance"] == 520.0
        assert data["currency"] == "CNY"
        assert data["account_id"] == "10001"
        assert data["service_costs"]["云服务器BCC"] == 12.34
        assert data["service_costs"]["对象存储BOS"] == 7.66
        assert len(data["items"]) == 2
        assert data["balance_debug"]["status"] == "success"
        first_call = mock_request.call_args_list[0]
        assert first_call.kwargs["url"] == "https://billing.baidubce.com/v1/bill/resource/month"
        assert first_call.kwargs["params"]["beginTime"] == "2025-01-01"
        assert first_call.kwargs["params"]["endTime"] == "2025-01-31"
        assert "serviceType" not in first_call.kwargs["params"]

    @patch("cloud_billing.clouds.baidu_provider.requests.Session.request")
    def test_validate_credentials_uses_balance(self, mock_request):
        provider = self._make_provider()
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "result": {
                "accountId": "10001",
                "cashBalance": "0.00",
                "currency": "CNY",
            }
        }
        mock_request.return_value = response

        assert provider.validate_credentials() is True

    @patch("cloud_billing.clouds.baidu_provider.requests.Session.request")
    def test_get_billing_info_retries_request_error(self, mock_request):
        provider = self._make_provider()
        postpay_response = Mock()
        postpay_response.raise_for_status.return_value = None
        postpay_response.json.return_value = {"result": {"items": []}}
        prepay_response = Mock()
        prepay_response.raise_for_status.return_value = None
        prepay_response.json.return_value = {"result": {"items": []}}
        balance_response = Mock()
        balance_response.raise_for_status.return_value = None
        balance_response.json.return_value = {
            "result": {"cashBalance": "0.00", "currency": "CNY"}
        }
        mock_request.side_effect = [
            RequestException("temporary error"),
            postpay_response,
            prepay_response,
            balance_response,
        ]

        result = provider.get_billing_info("2025-01")

        assert result["status"] == "success"
        assert mock_request.call_count == 4

    def test_canonical_query_keeps_empty_string_params(self):
        query = BaiduCloud._canonical_query(
            {
                "month": "2026-03",
                "serviceType": "",
                "pageNo": 1,
            }
        )

        assert query == "month=2026-03&pageNo=1&serviceType="

    def test_sign_headers_matches_bce_v1_auth_format(self):
        provider = self._make_provider()

        signed_headers = provider._sign_headers(
            "GET",
            "/v1/bill/resource/month",
            {
                "month": "2026-03",
                "serviceType": "",
            },
            {
                "host": "billing.baidubce.com",
                "x-bce-date": "2026-03-25T09:00:00Z",
                "content-type": "application/json",
                "content-length": "0",
            },
        )

        assert signed_headers["Authorization"].startswith(
            "bce-auth-v1/ak/2026-03-25T09:00:00Z/1800//"
        )

    @patch("cloud_billing.clouds.baidu_provider.timezone.localdate")
    def test_get_period_dates_caps_current_month_end_at_today(
        self,
        mock_localdate,
    ):
        mock_localdate.return_value = date(2026, 3, 25)

        begin_time, end_time = BaiduCloud._get_period_dates("2026-03")

        assert begin_time == "2026-03-01"
        assert end_time == "2026-03-24"
