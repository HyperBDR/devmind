"""Tests for the Azure cloud billing provider."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests

from cloud_billing.clouds.azure_provider import AzureCloud, AzureConfig


@pytest.mark.django_db
class TestAzureConfig:
    """Tests for AzureConfig."""

    def test_explicit_timeout_and_retries_are_preserved(self):
        with patch.dict(
            "os.environ",
            {
                "AZURE_TENANT_ID": "tenant-from-env",
                "AZURE_CLIENT_ID": "client-from-env",
                "AZURE_CLIENT_SECRET": "secret-from-env",
                "AZURE_SUBSCRIPTION_ID": "sub-from-env",
                "AZURE_TIMEOUT": "45",
                "AZURE_MAX_RETRIES": "8",
            },
            clear=True,
        ):
            config = AzureConfig(
                tenant_id="tenant",
                client_id="client",
                client_secret="secret",
                subscription_id="sub",
                timeout=30,
                max_retries=3,
            )

        assert config.timeout == 30
        assert config.max_retries == 3

    def test_missing_timeout_and_retries_use_env_defaults(self):
        with patch.dict(
            "os.environ",
            {
                "AZURE_TENANT_ID": "tenant",
                "AZURE_CLIENT_ID": "client",
                "AZURE_CLIENT_SECRET": "secret",
                "AZURE_SUBSCRIPTION_ID": "sub",
                "AZURE_TIMEOUT": "45",
                "AZURE_MAX_RETRIES": "8",
            },
            clear=True,
        ):
            config = AzureConfig(
                tenant_id="tenant",
                client_id="client",
                client_secret="secret",
                subscription_id="sub",
            )

        assert config.timeout == 45
        assert config.max_retries == 8


@pytest.mark.django_db
class TestAzureCloud:
    """Tests for AzureCloud."""

    def _make_provider(self):
        config = AzureConfig(
            tenant_id="tenant",
            client_id="client",
            client_secret="secret",
            subscription_id="sub",
        )
        provider = AzureCloud(config)
        provider._resource_client = Mock()
        provider._consumption_client = Mock()
        return provider

    def test_get_billing_info_uses_azure_cost_fields(self):
        provider = self._make_provider()
        provider._query_billing_api = Mock(
            return_value=[
                SimpleNamespace(
                    cost_in_billing_currency=12.34,
                    billing_currency_code="EUR",
                ),
                SimpleNamespace(
                    cost_in_billing_currency=7.66,
                    billing_currency_code="EUR",
                ),
            ]
        )

        result = provider.get_billing_info("2025-01")

        assert result["status"] == "success"
        data = result["data"]
        assert data["total_cost"] == 20.0
        assert data["currency"] == "EUR"
        assert data["account_id"] == "sub"

    def test_get_balance_prefers_available_balance_endpoint(self):
        provider = self._make_provider()
        provider._management_get = Mock(
            side_effect=[
                {
                    "value": [
                        {
                            "name": "BA-001",
                            "id": (
                                "/providers/Microsoft.Billing/"
                                "billingAccounts/BA-001"
                            ),
                        }
                    ]
                },
                {
                    "properties": {
                        "amount": {
                            "value": "1234.56",
                            "currency": "USD",
                        }
                    }
                },
            ]
        )

        balance = provider.get_balance()

        assert balance == 1234.56
        assert provider._last_balance_debug["source"] == (
            "billing.available_balance"
        )
        assert provider._last_balance_debug["billing_account_id"] == "BA-001"

    def test_get_balance_requires_explicit_scope_when_multiple_accounts_exist(
        self,
    ):
        provider = self._make_provider()
        provider._management_get = Mock(
            return_value={
                "value": [
                    {"name": "BA-001"},
                    {"name": "BA-002"},
                ]
            }
        )

        balance = provider.get_balance()

        assert balance is None
        assert provider._last_balance_debug["status"] == (
            "billing_account_ambiguous"
        )
        assert provider._last_balance_debug["billing_account_ids"] == [
            "BA-001",
            "BA-002",
        ]

    def test_get_billing_info_handles_empty_usage_details(self):
        provider = self._make_provider()
        provider._query_billing_api = Mock(return_value=[])
        provider.get_balance = Mock(return_value=None)

        result = provider.get_billing_info("2025-01")

        assert result["status"] == "success"
        assert result["data"]["total_cost"] == 0.0
        assert result["data"]["currency"] == "USD"

    def test_get_billing_info_returns_partial_success_when_cost_fails(self):
        provider = self._make_provider()
        provider._query_billing_api = Mock(
            side_effect=Exception("usageDetails/read denied")
        )
        provider.get_balance = Mock(return_value=321.45)
        provider._last_balance_debug = {
            "status": "success",
            "source": "billing.available_balance",
        }

        result = provider.get_billing_info("2025-01")

        assert result["status"] == "partial_success"
        assert result["data"]["balance"] == 321.45
        assert result["data"]["cost_status"] == "error"
        assert "usageDetails/read denied" in result["data"]["cost_error"]

    def test_get_balance_falls_back_to_consumption_balances(self):
        provider = self._make_provider()
        error_response = Mock(status_code=404, text='{"error":"not found"}')
        http_error = requests.HTTPError(response=error_response)
        provider._management_get = Mock(
            side_effect=[
                {"value": [{"name": "BA-002"}]},
                http_error,
                {
                    "properties": {
                        "endingBalance": "2,345.67",
                        "currency": "USD",
                        "beginningBalance": "3000.00",
                        "totalUsage": "654.33",
                    }
                },
            ]
        )

        balance = provider.get_balance()

        assert balance == 2345.67
        assert provider._last_balance_debug["source"] == (
            "consumption.balances"
        )
        assert provider._last_balance_debug["attempts"][0]["source"] == (
            "billing.available_balance"
        )
        assert provider._last_balance_debug["attempts"][0]["status"] == (
            "http_error"
        )

    def test_get_balance_uses_billing_profile_available_balance_when_present(
        self,
    ):
        provider = self._make_provider()
        error_response = Mock(status_code=404, text='{"error":"not found"}')
        http_error = requests.HTTPError(response=error_response)
        provider._management_get = Mock(
            side_effect=[
                {"value": [{"name": "BA-003"}]},
                {"value": [{"name": "BP-003"}]},
                http_error,
                {
                    "properties": {
                        "amount": {
                            "value": "88.90",
                            "currency": "USD",
                        }
                    }
                },
            ]
        )

        balance = provider.get_balance()

        assert balance == 88.9
        assert provider._last_balance_debug["source"] == (
            "billing.available_balance"
        )
        assert provider._last_balance_debug["billing_account_id"] == "BA-003"
        assert provider._last_balance_debug["billing_profile_id"] == "BP-003"
        assert provider._last_balance_debug["attempts"][0]["status"] == (
            "http_error"
        )

    def test_get_balance_parses_configured_billing_profile_resource_id(self):
        config = AzureConfig(
            tenant_id="tenant",
            client_id="client",
            client_secret="secret",
            subscription_id="sub",
            billing_account_id=(
                "/providers/Microsoft.Billing/billingAccounts/BA-004/"
                "billingProfiles/BP-004"
            ),
        )
        provider = AzureCloud(config)
        provider._resource_client = Mock()
        provider._consumption_client = Mock()
        provider._management_get = Mock(
            return_value={
                "properties": {
                    "amount": {
                        "value": "66.60",
                        "currency": "USD",
                    }
                }
            }
        )

        balance = provider.get_balance()

        assert balance == 66.6
        assert provider._last_balance_debug["billing_account_id"] == "BA-004"
        assert provider._last_balance_debug["billing_profile_id"] == "BP-004"
        provider._management_get.assert_called_once_with(
            "/providers/Microsoft.Billing/billingAccounts/BA-004/"
            "billingProfiles/BP-004/availableBalance/default",
            "2024-04-01",
        )

    def test_validate_credentials_uses_subscription_arm_lookup(self):
        provider = self._make_provider()
        provider._management_get = Mock(
            return_value={"subscriptionId": "sub"}
        )

        result = provider.validate_credentials()

        assert result is True
        provider._management_get.assert_called_once_with(
            "/subscriptions/sub",
            "2020-01-01",
        )
