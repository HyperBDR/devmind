"""Tests for the DeepSeek balance provider."""

from unittest.mock import Mock, patch

import pytest
import requests

from cloud_billing.clouds.deepseek_provider import (
    BALANCE_URL,
    DeepSeekCloud,
    DeepSeekConfig,
)
from cloud_billing.clouds.service import ProviderFactory


class TestDeepSeekCloud:
    """Verify DeepSeek balance collection and authentication."""

    @staticmethod
    def _make_provider() -> DeepSeekCloud:
        return DeepSeekCloud(DeepSeekConfig(api_key="sk-test-key"))

    @patch("cloud_billing.clouds.deepseek_provider.requests.Session.get")
    def test_get_balance_uses_bearer_auth_and_parses_total(self, mock_get):
        """Use the documented endpoint and Bearer authorization header."""
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "is_available": True,
            "balance_infos": [
                {
                    "currency": "CNY",
                    "total_balance": "110.00",
                    "granted_balance": "10.00",
                    "topped_up_balance": "100.00",
                }
            ],
        }
        mock_get.return_value = response
        provider = self._make_provider()

        balance = provider.get_balance()

        assert balance == 110.0
        assert provider._last_balance_debug == {
            "status": "success",
            "is_available": True,
            "currency": "CNY",
            "granted_balance": "10.00",
            "topped_up_balance": "100.00",
        }
        mock_get.assert_called_once_with(
            BALANCE_URL,
            headers={
                "Accept": "application/json",
                "Authorization": "Bearer sk-test-key",
            },
            timeout=30,
        )

    @patch("cloud_billing.clouds.deepseek_provider.requests.Session.get")
    def test_get_billing_info_returns_balance_only_contract(self, mock_get):
        """Expose DeepSeek balance through the common billing contract."""
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "is_available": False,
            "balance_infos": [
                {
                    "currency": "USD",
                    "total_balance": "0.00",
                    "granted_balance": "0.00",
                    "topped_up_balance": "0.00",
                }
            ],
        }
        mock_get.return_value = response
        provider = self._make_provider()

        result = provider.get_billing_info("2026-07")

        assert result["status"] == "success"
        assert result["error"] is None
        assert result["data"]["total_cost"] == 0.0
        assert result["data"]["balance"] == 0.0
        assert result["data"]["currency"] == "USD"
        assert result["data"]["service_costs"] == {}
        assert result["data"]["items"] == []
        assert result["data"]["account_id"] == "deepseek"

    def test_account_id_is_stable_across_api_key_rotations(self):
        """Keep billing history attached when credentials are rotated."""
        previous = DeepSeekCloud(DeepSeekConfig(api_key="sk-previous-key"))
        rotated = DeepSeekCloud(DeepSeekConfig(api_key="sk-rotated-key"))

        assert previous.get_account_id() == rotated.get_account_id()

    @patch("cloud_billing.clouds.deepseek_provider.requests.Session.get")
    def test_validate_credentials_accepts_successful_empty_balance(
        self,
        mock_get,
    ):
        """Validate a key when a successful response has no balance rows."""
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "is_available": False,
            "balance_infos": [],
        }
        mock_get.return_value = response

        assert self._make_provider().validate_credentials() is True

    @patch("cloud_billing.clouds.deepseek_provider.requests.Session.get")
    def test_billing_error_does_not_expose_api_key(self, mock_get):
        """Return a generic HTTP error without leaking the Bearer token."""
        response = Mock(status_code=401)
        response.raise_for_status.side_effect = requests.HTTPError(
            response=response
        )
        mock_get.return_value = response

        result = self._make_provider().get_billing_info()

        assert result == {
            "status": "error",
            "data": None,
            "error": "DeepSeek API request failed (401).",
        }
        assert "sk-test-key" not in str(result)

    @pytest.mark.parametrize(
        ("currency", "total_balance"),
        [
            ("EUR", "10.00"),
            ("CNY", "NaN"),
            ("USD", "-1.00"),
        ],
    )
    @patch("cloud_billing.clouds.deepseek_provider.requests.Session.get")
    def test_rejects_invalid_external_balance_values(
        self,
        mock_get,
        currency,
        total_balance,
    ):
        """Reject values outside the documented response contract."""
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "is_available": True,
            "balance_infos": [
                {
                    "currency": currency,
                    "total_balance": total_balance,
                }
            ],
        }
        mock_get.return_value = response

        result = self._make_provider().get_billing_info()

        assert result["status"] == "error"
        assert result["data"] is None

    def test_config_requires_api_key(self, monkeypatch):
        """Reject an empty API key before making a network request."""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        with pytest.raises(ValueError, match="DeepSeek API key is required"):
            DeepSeekConfig(api_key=None)

    def test_config_rejects_non_positive_timeout(self):
        """Reject unsafe request timeout values."""
        with pytest.raises(ValueError, match="greater than 0"):
            DeepSeekConfig(api_key="sk-test-key", timeout=0)

    def test_factory_creates_deepseek_provider(self):
        """Register DeepSeek with the common provider factory."""
        provider = ProviderFactory.create_provider(
            "deepseek",
            {"api_key": "sk-test-key"},
        )

        assert isinstance(provider, DeepSeekCloud)
