"""Tests for the AWS cloud billing provider."""

from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from cloud_billing.clouds.aws_provider import AWSCloud, AWSConfig


@pytest.mark.django_db
class TestAWSCloud:
    """Tests for AWSCloud."""

    def _make_provider(self):
        config = AWSConfig(
            api_key="test-key",
            api_secret="test-secret",
            region="us-east-1",
        )
        provider = AWSCloud(config)
        provider._client = Mock()
        provider._sts_client = Mock()
        provider._mturk_client = Mock()
        provider._sts_client.get_caller_identity.return_value = {
            "Account": "123456789012"
        }
        return provider

    def test_get_billing_info_includes_balance_when_available(self):
        provider = self._make_provider()
        provider._client.get_cost_and_usage.return_value = {
            "ResultsByTime": [{
                "Total": {
                    "UnblendedCost": {
                        "Amount": "123.45",
                        "Unit": "USD",
                    }
                }
            }]
        }
        provider._mturk_client.get_account_balance.return_value = {
            "AvailableBalance": "200.50"
        }

        result = provider.get_billing_info("2025-01")

        assert result["status"] == "success"
        assert result["data"]["total_cost"] == 123.45
        assert result["data"]["balance"] == 200.50
        assert result["data"]["account_id"] == "123456789012"

    def test_get_billing_info_keeps_success_when_balance_unavailable(self):
        provider = self._make_provider()
        provider._client.get_cost_and_usage.return_value = {
            "ResultsByTime": [{
                "Total": {
                    "UnblendedCost": {
                        "Amount": "88.00",
                        "Unit": "USD",
                    }
                }
            }]
        }
        provider._mturk_client.get_account_balance.side_effect = ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "Not authorized",
                }
            },
            "GetAccountBalance",
        )

        result = provider.get_billing_info("2025-01")

        assert result["status"] == "success"
        assert result["data"]["total_cost"] == 88.0
        assert result["data"]["balance"] is None

    def test_get_billing_info_skips_balance_lookup_for_china_region(self):
        config = AWSConfig(
            api_key="test-key",
            api_secret="test-secret",
            region="cn-north-1",
        )
        provider = AWSCloud(config)
        provider._client = Mock()
        provider._sts_client = Mock()
        provider._mturk_client = Mock()
        provider._client.get_cost_and_usage.return_value = {
            "ResultsByTime": [{
                "Total": {
                    "UnblendedCost": {
                        "Amount": "66.00",
                        "Unit": "USD",
                    }
                }
            }]
        }
        provider._sts_client.get_caller_identity.return_value = {
            "Account": "123456789012"
        }

        result = provider.get_billing_info("2025-01")

        assert result["status"] == "success"
        assert result["data"]["balance"] is None
        assert result["data"]["balance_debug"]["status"] == "unsupported_partition"
        provider._mturk_client.get_account_balance.assert_not_called()
