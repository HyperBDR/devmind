"""Tests for the Azure cloud billing provider."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

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
