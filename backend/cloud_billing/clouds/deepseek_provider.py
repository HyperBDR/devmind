"""DeepSeek account balance provider.

Official API documentation:
https://api-docs.deepseek.com/zh-cn/api/deepseek-api
https://api-docs.deepseek.com/zh-cn/api/get-user-balance
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Tuple

import requests

from ..utils.logging import mask_sensitive_config_object
from .provider import BaseCloudConfig, BaseCloudProvider

logger = logging.getLogger(__name__)

BALANCE_URL = "https://api.deepseek.com/user/balance"
DEFAULT_TIMEOUT = 30
DEFAULT_CURRENCY = "CNY"
ALLOWED_CURRENCIES = {"CNY", "USD"}
MAX_BALANCE = Decimal("1e18")


@dataclass
class DeepSeekConfig(BaseCloudConfig):
    """DeepSeek API configuration."""

    api_key: Optional[str] = None
    timeout: int = DEFAULT_TIMEOUT

    def __post_init__(self):
        if self.api_key is None:
            self.api_key = os.getenv("DEEPSEEK_API_KEY")
        if self.timeout == DEFAULT_TIMEOUT:
            self.timeout = int(
                os.getenv("DEEPSEEK_TIMEOUT", str(DEFAULT_TIMEOUT))
            )
        self._validate_config()

    def _validate_config(self):
        if not self.api_key:
            raise ValueError("DeepSeek API key is required.")
        if self.timeout <= 0:
            raise ValueError("Timeout must be greater than 0.")


class DeepSeekCloud(BaseCloudProvider):
    """Collect current DeepSeek account balance using an API key."""

    def __init__(self, config: DeepSeekConfig):
        super().__init__(config)
        self.name = "deepseek"
        self._session = requests.Session()
        self._last_balance_debug: Dict[str, Any] = {}
        logger.info(
            "Initialized DeepSeek provider with config: %s",
            mask_sensitive_config_object(config),
        )

    @staticmethod
    def _parse_decimal(value: Any) -> Decimal:
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(
                "DeepSeek API returned an invalid balance value."
            ) from exc
        if not parsed.is_finite() or parsed < 0 or parsed >= MAX_BALANCE:
            raise ValueError("DeepSeek API returned an invalid balance value.")
        return parsed

    def _request_balance(
        self,
    ) -> Tuple[Optional[float], str, Dict[str, Any]]:
        response = self._session.get(
            BALANCE_URL,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("DeepSeek API returned an invalid response.")

        is_available = payload.get("is_available")
        if not isinstance(is_available, bool):
            raise ValueError("DeepSeek API response is missing is_available.")

        balance_infos = payload.get("balance_infos")
        if not isinstance(balance_infos, list):
            raise ValueError("DeepSeek API response is missing balance_infos.")

        balance_info: Dict[str, Any] = {}
        for item in balance_infos:
            has_total = (
                isinstance(item, dict)
                and item.get("total_balance") is not None
            )
            if has_total:
                balance_info = item
                break

        balance: Optional[float] = None
        currency = ""
        if balance_info:
            balance = float(self._parse_decimal(balance_info["total_balance"]))
            currency = str(balance_info.get("currency") or "").upper()
            if currency not in ALLOWED_CURRENCIES:
                raise ValueError(
                    "DeepSeek API returned an unsupported currency."
                )

        debug = {
            "status": "success",
            "is_available": is_available,
            "currency": currency,
            "granted_balance": balance_info.get("granted_balance"),
            "topped_up_balance": balance_info.get("topped_up_balance"),
        }
        self._last_balance_debug = debug
        return balance, currency, debug

    @staticmethod
    def _error_message(exc: Exception) -> str:
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            return f"DeepSeek API request failed ({exc.response.status_code})."
        if isinstance(exc, requests.Timeout):
            return "DeepSeek API request timed out."
        if isinstance(exc, requests.RequestException):
            return "DeepSeek API request failed."
        return str(exc)

    def get_balance(self) -> Optional[float]:
        """Return the first currency balance reported by DeepSeek."""
        try:
            balance, _, _ = self._request_balance()
            return balance
        except (requests.RequestException, ValueError) as exc:
            message = self._error_message(exc)
            self._last_balance_debug = {
                "status": "error",
                "error_message": message,
            }
            logger.warning("DeepSeek balance lookup failed: %s", message)
            return None

    def get_billing_info(
        self,
        period: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return the current balance in the common billing response shape."""
        del period
        try:
            balance, currency, debug = self._request_balance()
            return {
                "status": "success",
                "data": {
                    "total_cost": 0.0,
                    "balance": balance,
                    "balance_debug": debug,
                    "currency": currency or DEFAULT_CURRENCY,
                    "account_id": self.get_account_id(),
                    "service_costs": {},
                    "items": [],
                },
                "error": None,
            }
        except (requests.RequestException, ValueError) as exc:
            message = self._error_message(exc)
            self._last_balance_debug = {
                "status": "error",
                "error_message": message,
            }
            logger.warning("DeepSeek balance lookup failed: %s", message)
            return {"status": "error", "data": None, "error": message}

    def get_account_id(self) -> str:
        """Return an identifier that remains stable across key rotations."""
        return "deepseek"

    def validate_credentials(self) -> bool:
        """Validate the API key with the documented balance endpoint."""
        self._request_balance()
        return True
