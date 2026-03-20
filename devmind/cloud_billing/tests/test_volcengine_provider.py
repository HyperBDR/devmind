"""Tests for the Volcengine cloud billing provider."""

from unittest.mock import Mock, patch

import pytest
from requests.exceptions import RequestException

from cloud_billing.clouds.volcengine_provider import (
    VolcengineCloud,
    VolcengineConfig,
)


@pytest.mark.django_db
class TestVolcengineConfig:
    def test_config_from_values(self):
        config = VolcengineConfig(
            api_key="ak",
            api_secret="sk",
            region="cn-north-1",
        )
        assert config.api_key == "ak"
        assert config.api_secret == "sk"
        assert config.region == "cn-north-1"
        assert config.endpoint == "https://billing.volcengineapi.com"


@pytest.mark.django_db
class TestVolcengineCloud:
    def _make_provider(self):
        config = VolcengineConfig(
            api_key="ak",
            api_secret="sk",
            region="cn-north-1",
            payer_id="2100052604",
        )
        return VolcengineCloud(config)

    @patch("cloud_billing.clouds.volcengine_provider.requests.Session.get")
    def test_get_billing_info_parses_response(self, mock_get):
        provider = self._make_provider()
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "ResponseMetadata": {
                "RequestId": "req-1",
                "Action": "ListBill",
                "Version": "20220101",
                "Service": "billing",
                "Region": "cn-north-1",
            },
            "Result": {
                "List": [
                    {
                        "BillPeriod": "2025-01",
                        "PayerID": "2100052604",
                        "Product": "ECS",
                        "ProductZh": "云服务器",
                        "PayableAmount": "12.34",
                        "PaidAmount": "12.34",
                        "Currency": "CNY",
                        "PayStatus": "已结清",
                        "BillID": "Bill-001",
                    },
                    {
                        "BillPeriod": "2025-01",
                        "PayerID": "2100052604",
                        "Product": "OBS",
                        "ProductZh": "对象存储",
                        "PayableAmount": "7.66",
                        "PaidAmount": "7.66",
                        "Currency": "CNY",
                        "PayStatus": "已结清",
                        "BillID": "Bill-002",
                    },
                ],
                "Total": 2,
                "Limit": 100,
                "Offset": 0,
            },
        }
        mock_get.return_value = response

        result = provider.get_billing_info("2025-01")

        assert result["status"] == "success"
        data = result["data"]
        assert data["total_cost"] == 20.0
        assert data["currency"] == "CNY"
        assert data["account_id"] == "2100052604"
        assert data["service_costs"]["云服务器"] == 12.34
        assert data["service_costs"]["对象存储"] == 7.66
        assert len(data["items"]) == 2
        assert data["items"][0]["bill_id"] == "Bill-001"

    def test_sign_headers_uses_raw_secret(self):
        provider = self._make_provider()
        with patch.object(
            provider, "_hmac_sha256", wraps=provider._hmac_sha256
        ) as mock_hmac:
            provider._sign_headers(
                "GET",
                "billing.volcengineapi.com",
                {"Action": "ListBill", "Version": "2022-01-01"},
                "20240311T104027Z",
            )

        first_key = mock_hmac.call_args_list[0].args[0]
        assert first_key == b"sk"

    @patch("cloud_billing.clouds.volcengine_provider.requests.Session.get")
    def test_validate_credentials_success(self, mock_get):
        provider = self._make_provider()
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "ResponseMetadata": {
                "RequestId": "req-1",
                "Action": "ListBill",
                "Version": "20220101",
                "Service": "billing",
                "Region": "cn-north-1",
            },
            "Result": {
                "List": [],
                "Total": 0,
                "Limit": 100,
                "Offset": 0,
            },
        }
        mock_get.return_value = response

        assert provider.validate_credentials() is True

    @patch("cloud_billing.clouds.volcengine_provider.requests.Session.get")
    def test_get_billing_info_retries_request_error(self, mock_get):
        provider = self._make_provider()
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "ResponseMetadata": {
                "RequestId": "req-1",
                "Action": "ListBill",
                "Version": "20220101",
                "Service": "billing",
                "Region": "cn-north-1",
            },
            "Result": {
                "List": [],
                "Total": 0,
                "Limit": 100,
                "Offset": 0,
            },
        }
        mock_get.side_effect = [
            RequestException("temporary error"),
            response,
        ]

        result = provider.get_billing_info("2025-01")

        assert result["status"] == "success"
        assert mock_get.call_count == 2

    def test_get_account_id_uses_payer_id(self):
        provider = self._make_provider()
        assert provider.get_account_id() == "2100052604"
