"""Tests for the Yunce cloud account provider."""

from unittest.mock import Mock, patch

import pytest
import requests

from cloud_billing.clouds.service import ProviderFactory
from cloud_billing.clouds.yunce_provider import (
    API_KEYS_URL,
    LOGIN_URL,
    USER_INFO_URL,
    YunceCloud,
    YunceConfig,
)


class TestYunceCloud:
    """Verify Yunce authentication, balance, and API key usage."""

    @staticmethod
    def _make_provider() -> YunceCloud:
        return YunceCloud(YunceConfig(username="account", password="pass"))

    @staticmethod
    def _response(payload, status_code=200):
        response = Mock(status_code=status_code)
        response.raise_for_status.return_value = None
        response.json.return_value = payload
        return response

    @staticmethod
    def _login_payload():
        return {
            "code": 200,
            "data": {
                "refresh": "refresh-secret",
                "access": "access-secret",
                "type": "Bearer",
            },
            "msg": "success",
        }

    @staticmethod
    def _user_info_payload():
        return {
            "code": 200,
            "data": {
                "id": 1,
                "total_recharge": 2000.0,
                "fee_balance": 1080.061064,
                "warning_threshold": 99,
                "shutdown_threshold": 100,
            },
            "msg": "success",
        }

    @patch("cloud_billing.clouds.yunce_provider.requests.Session.request")
    def test_get_balance_authenticates_and_reads_user_info(
        self,
        mock_request,
    ):
        """Login once and use the access token as a Bearer credential."""
        mock_request.side_effect = [
            self._response(self._login_payload()),
            self._response(self._user_info_payload()),
        ]
        provider = self._make_provider()

        balance = provider.get_balance()

        assert balance == 1080.061064
        assert provider._last_balance_debug == {
            "status": "success",
            "currency": "CNY",
            "total_recharge": 2000.0,
            "warning_threshold": 99,
            "shutdown_threshold": 100,
        }
        assert mock_request.call_args_list[0].kwargs == {
            "method": "POST",
            "url": LOGIN_URL,
            "headers": {
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            "json": {"username": "account", "password": "pass"},
            "timeout": 30,
        }

    @pytest.mark.parametrize(
        ("cost_threshold", "current_cost", "expected_balance"),
        [
            ("2000.000000", "1100.000000", 900.0),
            ("3000.000000", "1100.000000", 1080.061064),
        ],
    )
    @patch("cloud_billing.clouds.yunce_provider.requests.Session.request")
    def test_get_balance_uses_lower_api_key_remaining_quota(
        self,
        mock_request,
        cost_threshold,
        current_cost,
        expected_balance,
    ):
        """Compare account balance with the selected key's remaining quota."""
        api_key_page = {
            "code": 200,
            "data": {
                "total": 1,
                "list": [
                    {
                        "id": 1,
                        "displayname": "selected",
                        "key_value": "sk-selected-secret",
                        "status": 1,
                        "limit_rules": {
                            "current_cost": current_cost,
                            "cost_threshold": cost_threshold,
                            "currency": "CNY",
                        },
                    }
                ],
            },
            "msg": "success",
        }
        mock_request.side_effect = [
            self._response(self._login_payload()),
            self._response(self._user_info_payload()),
            self._response(api_key_page),
        ]
        provider = YunceCloud(
            YunceConfig(
                username="account",
                password="pass",
                api_key="sk-selected-secret",
            )
        )

        assert provider.get_balance() == expected_balance

    @patch("cloud_billing.clouds.yunce_provider.requests.Session.request")
    def test_get_balance_uses_account_balance_for_unlimited_api_key(
        self,
        mock_request,
    ):
        """Treat a zero cost threshold as unlimited."""
        api_key_page = {
            "code": 200,
            "data": {
                "total": 1,
                "list": [
                    {
                        "id": 1,
                        "displayname": "unlimited",
                        "key_value": "sk-unlimited-secret",
                        "status": 1,
                        "limit_rules": {
                            "current_cost": "955.801704",
                            "cost_threshold": "0.000000",
                            "currency": "CNY",
                        },
                    }
                ],
            },
            "msg": "success",
        }
        mock_request.side_effect = [
            self._response(self._login_payload()),
            self._response(self._user_info_payload()),
            self._response(api_key_page),
        ]
        provider = YunceCloud(
            YunceConfig(
                username="account",
                password="pass",
                api_key="sk-unlimited-secret",
            )
        )

        assert provider.get_balance() == 1080.061064

    @patch("cloud_billing.clouds.yunce_provider.requests.Session.request")
    def test_missing_configured_api_key_fails_without_exposing_it(
        self,
        mock_request,
    ):
        """Reject an unknown configured key without returning its value."""
        api_key_page = {
            "code": 200,
            "data": {"total": 0, "list": []},
            "msg": "success",
        }
        mock_request.side_effect = [
            self._response(self._login_payload()),
            self._response(self._user_info_payload()),
            self._response(api_key_page),
        ]
        provider = YunceCloud(
            YunceConfig(
                username="account",
                password="pass",
                api_key="sk-missing-secret",
            )
        )

        result = provider.get_billing_info()

        assert result == {
            "status": "error",
            "data": None,
            "error": "Configured Yunce API key was not found.",
        }
        assert "sk-missing-secret" not in str(result)
        assert mock_request.call_args_list[1].kwargs == {
            "method": "GET",
            "url": USER_INFO_URL,
            "headers": {
                "Accept": "application/json",
                "Authorization": "Bearer access-secret",
            },
            "timeout": 30,
        }

    @patch("cloud_billing.clouds.yunce_provider.requests.Session.request")
    def test_get_billing_info_collects_paginated_api_key_usage(
        self,
        mock_request,
    ):
        """Map per-key current cost without exposing API key values."""
        first_page = {
            "code": 200,
            "data": {
                "total": 2,
                "list": [
                    {
                        "id": 1,
                        "displayname": "test1",
                        "description": "primary",
                        "key_value": "sk-first-secret",
                        "status": 1,
                        "limit_rules": {
                            "current_cost": "955.801704",
                            "cost_threshold": "2000.000000",
                            "currency": "CNY",
                        },
                    }
                ],
            },
            "msg": "success",
        }
        second_page = {
            "code": 200,
            "data": {
                "total": 2,
                "list": [
                    {
                        "id": 2,
                        "displayname": "test2",
                        "description": "backup",
                        "key_value": "sk-second-secret",
                        "status": 0,
                        "limit_rules": {
                            "current_cost": "44.198296",
                            "cost_threshold": "0.000000",
                            "currency": "CNY",
                        },
                    }
                ],
            },
            "msg": "success",
        }
        mock_request.side_effect = [
            self._response(self._login_payload()),
            self._response(self._user_info_payload()),
            self._response(first_page),
            self._response(second_page),
        ]

        provider = YunceCloud(
            YunceConfig(
                username="account",
                password="pass",
                api_key="sk-first-secret",
            )
        )

        result = provider.get_billing_info("2026-07")

        assert result["status"] == "success"
        assert result["data"]["account_id"] == "1"
        assert result["data"]["balance"] == 1044.198296
        assert result["data"]["total_cost"] == 1000.0
        assert result["data"]["service_costs"] == {
            "test1": 955.801704,
            "test2": 44.198296,
        }
        assert result["data"]["items"] == [
            {
                "service_name": "test1",
                "amount": 955.801704,
                "currency": "CNY",
                "bill_id": "1",
                "description": "primary",
                "status": 1,
                "cost_threshold": 2000.0,
            },
            {
                "service_name": "test2",
                "amount": 44.198296,
                "currency": "CNY",
                "bill_id": "2",
                "description": "backup",
                "status": 0,
                "cost_threshold": 0.0,
            },
        ]
        serialized = str(result)
        assert "access-secret" not in serialized
        assert "refresh-secret" not in serialized
        assert "sk-first-secret" not in serialized
        assert "sk-second-secret" not in serialized
        key_calls = mock_request.call_args_list[2:]
        assert [call.kwargs["params"]["page"] for call in key_calls] == [
            1,
            2,
        ]
        assert all(call.kwargs["url"] == API_KEYS_URL for call in key_calls)
        assert all(call.kwargs["params"]["size"] == 10 for call in key_calls)
        assert all(
            call.kwargs["params"]["status__ne"] == 3 for call in key_calls
        )

    @patch("cloud_billing.clouds.yunce_provider.requests.Session.request")
    def test_http_error_does_not_expose_credentials(self, mock_request):
        """Return a generic error without leaking username or password."""
        response = Mock(status_code=401)
        response.raise_for_status.side_effect = requests.HTTPError(
            response=response
        )
        mock_request.return_value = response

        result = self._make_provider().get_billing_info()

        assert result == {
            "status": "error",
            "data": None,
            "error": "Yunce API request failed (401).",
        }
        assert "account" not in str(result)
        assert "pass" not in str(result)

    @pytest.mark.parametrize("fee_balance", ["NaN", "-1", "1e18"])
    @patch("cloud_billing.clouds.yunce_provider.requests.Session.request")
    def test_rejects_invalid_balance_values(
        self,
        mock_request,
        fee_balance,
    ):
        """Reject non-finite or out-of-range account balances."""
        payload = self._user_info_payload()
        payload["data"]["fee_balance"] = fee_balance
        mock_request.side_effect = [
            self._response(self._login_payload()),
            self._response(payload),
        ]

        result = self._make_provider().get_billing_info()

        assert result["status"] == "error"
        assert result["data"] is None

    def test_config_requires_username_and_password(self, monkeypatch):
        """Reject incomplete credentials before making a request."""
        monkeypatch.delenv("YUNCE_USERNAME", raising=False)
        monkeypatch.delenv("YUNCE_PASSWORD", raising=False)

        with pytest.raises(ValueError, match="username is required"):
            YunceConfig(username=None, password="pass")
        with pytest.raises(ValueError, match="password is required"):
            YunceConfig(username="account", password=None)

    def test_factory_creates_yunce_provider(self):
        """Register Yunce with the common provider factory."""
        provider = ProviderFactory.create_provider(
            "yunce",
            {"username": "account", "password": "pass"},
        )

        assert isinstance(provider, YunceCloud)
