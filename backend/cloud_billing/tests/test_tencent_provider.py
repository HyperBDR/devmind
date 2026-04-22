"""Tests for the Tencent Cloud billing provider."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from cloud_billing.clouds.tencent_provider import (
    DEFAULT_ENDPOINT,
    TencentCloud,
    TencentConfig,
)
from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
    TencentCloudSDKException,
)


@pytest.mark.django_db
class TestTencentConfig:
    """Tests for TencentConfig."""

    def test_config_from_values(self):
        config = TencentConfig(
            access_key_id="ak",
            access_key_secret="sk",
            app_id="10001",
            region="ap-guangzhou",
        )
        assert config.access_key_id == "ak"
        assert config.access_key_secret == "sk"
        assert config.app_id == "10001"
        assert config.endpoint == DEFAULT_ENDPOINT


@pytest.mark.django_db
class TestTencentCloud:
    """Tests for TencentCloud."""

    def _make_provider(self):
        config = TencentConfig(
            access_key_id="ak",
            access_key_secret="sk",
            app_id="10001",
            region="ap-guangzhou",
            timeout=12,
            endpoint="billing.tencentcloudapi.com",
        )
        provider = TencentCloud(config)
        provider._client = Mock()
        return provider

    def test_client_uses_http_profile_timeout_and_endpoint(self):
        provider = TencentCloud(
            TencentConfig(
                access_key_id="ak",
                access_key_secret="sk",
                app_id="10001",
                region="ap-guangzhou",
                timeout=12,
                endpoint="billing.tencentcloudapi.com",
            )
        )
        with patch(
            "cloud_billing.clouds.tencent_provider."
            "billing_client.BillingClient"
        ) as mock_client_cls:
            _ = provider.client

        _, region, profile = mock_client_cls.call_args.args
        assert region == "ap-guangzhou"
        assert profile.httpProfile.endpoint == "billing.tencentcloudapi.com"
        assert profile.httpProfile.reqTimeout == 12

    def test_get_account_id_uses_uin(self):
        provider = self._make_provider()
        provider._client.DescribeAccountBalance.return_value = SimpleNamespace(
            Uin=123456789012
        )

        assert provider.get_account_id() == "123456789012"

    def test_get_account_id_returns_empty_string_when_uin_missing(self):
        provider = self._make_provider()
        provider._client.DescribeAccountBalance.return_value = (
            SimpleNamespace()
        )

        assert provider.get_account_id() == ""

    def test_validate_credentials_success(self):
        provider = self._make_provider()
        provider._client.DescribeAccountBalance.return_value = SimpleNamespace(
            Uin=123456789012
        )

        assert provider.validate_credentials() is True

    def test_get_billing_info_parses_response(self):
        provider = self._make_provider()
        provider._client.DescribeAccountBalance.return_value = SimpleNamespace(
            Uin=123456789012,
            AvailableBalance="25688",
        )
        provider._client.DescribeBillSummary.return_value = SimpleNamespace(
            Ready=1,
            SummaryDetail=[
                SimpleNamespace(RealTotalCost="12.34", GroupValue="ECS"),
                SimpleNamespace(TotalCost="7.66", ProductCodeName="OBS"),
            ],
        )

        result = provider.get_billing_info("2025-01")

        assert result["status"] == "success"
        data = result["data"]
        assert data["total_cost"] == 20.0
        assert data["balance"] == 256.88
        assert data["currency"] == "CNY"
        assert data["account_id"] == "123456789012"
        assert data["service_costs"]["ECS"] == 12.34
        assert data["service_costs"]["OBS"] == 7.66
        assert len(data["items"]) == 2
        assert data["balance_debug"]["status"] == "success"
        assert data["balance_debug"]["available_balance_raw"] == "25688"
        assert data["balance_debug"]["available_balance"] == "256.88"
        assert data["balance_debug"]["unit"] == "yuan_from_cent"
        request = provider._client.DescribeBillSummary.call_args.args[0]
        assert request.Month == "2025-01"
        assert request.GroupType == "business"

    def test_get_billing_info_returns_error_when_summary_not_ready(self):
        provider = self._make_provider()
        provider._client.DescribeBillSummary.side_effect = (
            TencentCloudSDKException("SummaryDataNotReady", "data not ready")
        )

        result = provider.get_billing_info("2025-01")

        assert result["status"] == "error"
        assert "SummaryDataNotReady" in result["error"]
