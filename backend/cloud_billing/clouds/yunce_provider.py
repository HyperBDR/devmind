"""Yunce cloud account balance and API key usage provider."""

from __future__ import annotations

import logging
import os
import secrets
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

import requests

from .provider import BaseCloudConfig, BaseCloudProvider

logger = logging.getLogger(__name__)

LOGIN_URL = "https://llm.guohe-sh.com/admin/api/users/login/"
USER_INFO_URL = "https://llm.guohe-sh.com/admin/api/users/info/"
API_KEYS_URL = (
    "https://llm.guohe-sh.com/admin/api/llm_platform/" "user_access_key/"
)
DEFAULT_TIMEOUT = 30
DEFAULT_CURRENCY = "CNY"
DEFAULT_PAGE_SIZE = 10
MAX_PAGES = 100
MAX_AMOUNT = Decimal("1e18")


@dataclass
class YunceConfig(BaseCloudConfig):
    """Yunce username and password configuration."""

    username: Optional[str] = None
    password: Optional[str] = None
    timeout: int = DEFAULT_TIMEOUT

    def __post_init__(self):
        if self.username is None:
            self.username = os.getenv("YUNCE_USERNAME")
        if self.password is None:
            self.password = os.getenv("YUNCE_PASSWORD")
        if self.api_key is None:
            self.api_key = os.getenv("YUNCE_API_KEY")
        if self.timeout == DEFAULT_TIMEOUT:
            self.timeout = int(
                os.getenv("YUNCE_TIMEOUT", str(DEFAULT_TIMEOUT))
            )
        self._validate_config()

    def _validate_config(self):
        if not self.username:
            raise ValueError("Yunce username is required.")
        if not self.password:
            raise ValueError("Yunce password is required.")
        if self.api_key is not None:
            if not isinstance(self.api_key, str):
                raise ValueError("Yunce API key must be a string.")
            self.api_key = self.api_key.strip()
            if len(self.api_key) > 512:
                raise ValueError("Yunce API key is too long.")
        if self.timeout <= 0:
            raise ValueError("Timeout must be greater than 0.")


class YunceCloud(BaseCloudProvider):
    """Collect Yunce account balance and per-key current cost."""

    def __init__(self, config: YunceConfig):
        super().__init__(config)
        self.name = "yunce"
        self._session = requests.Session()
        self._access_token = ""
        self._last_account_id = ""
        self._last_balance_debug: Dict[str, Any] = {}
        logger.info("Initialized Yunce provider")

    @staticmethod
    def _parse_amount(value: Any, field_name: str) -> Decimal:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(
                f"Yunce API returned an invalid {field_name}."
            ) from exc
        if not amount.is_finite() or amount < 0 or amount >= MAX_AMOUNT:
            raise ValueError(f"Yunce API returned an invalid {field_name}.")
        return amount

    @staticmethod
    def _safe_text(value: Any, limit: int) -> str:
        return str(value or "").strip()[:limit]

    @staticmethod
    def _validate_payload(payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Yunce API returned an invalid response.")
        if payload.get("code") not in {200, "200"}:
            raise ValueError("Yunce API returned an error response.")
        return payload

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        authenticated: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        headers = {"Accept": "application/json"}
        if "json" in kwargs:
            headers["Content-Type"] = "application/json"
        if authenticated:
            token = self._ensure_access_token()
            headers["Authorization"] = f"Bearer {token}"

        response = self._session.request(
            method=method,
            url=url,
            headers=headers,
            timeout=self.config.timeout,
            **kwargs,
        )
        response.raise_for_status()
        return self._validate_payload(response.json())

    def _ensure_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        payload = self._request_json(
            "POST",
            LOGIN_URL,
            json={
                "username": self.config.username,
                "password": self.config.password,
            },
        )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError("Yunce login response is missing data.")
        access_token = data.get("access")
        if not isinstance(access_token, str) or not access_token.strip():
            raise ValueError("Yunce login response is missing access token.")
        self._access_token = access_token.strip()
        return self._access_token

    def _get_user_info(self) -> Dict[str, Any]:
        payload = self._request_json(
            "GET",
            USER_INFO_URL,
            authenticated=True,
        )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError("Yunce user info response is missing data.")

        balance = self._parse_amount(data.get("fee_balance"), "balance")
        total_recharge = self._parse_amount(
            data.get("total_recharge", 0),
            "total recharge",
        )
        raw_account_id = data.get("id")
        if isinstance(raw_account_id, bool) or not isinstance(
            raw_account_id,
            (int, str),
        ):
            raise ValueError(
                "Yunce user info response has an invalid account id."
            )
        account_id = self._safe_text(raw_account_id, 100)
        if not account_id:
            raise ValueError("Yunce user info response is missing account id.")
        self._last_account_id = account_id
        return {
            "account_id": account_id,
            "balance": balance,
            "total_recharge": total_recharge,
            "warning_threshold": data.get("warning_threshold"),
            "shutdown_threshold": data.get("shutdown_threshold"),
        }

    def _get_api_key_page(self, page: int) -> Dict[str, Any]:
        payload = self._request_json(
            "GET",
            API_KEYS_URL,
            authenticated=True,
            params={
                "page": page,
                "size": DEFAULT_PAGE_SIZE,
                "status__ne": 3,
            },
        )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError("Yunce API key response is missing data.")
        rows = data.get("list")
        if not isinstance(rows, list):
            raise ValueError("Yunce API key response is missing list.")
        try:
            total = int(data.get("total", len(rows)))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Yunce API key response has an invalid total."
            ) from exc
        if total < 0:
            raise ValueError("Yunce API key response has an invalid total.")
        return {"total": total, "rows": rows}

    def _get_all_api_keys(self) -> List[Dict[str, Any]]:
        collected: List[Dict[str, Any]] = []
        expected_total = 0
        for page in range(1, MAX_PAGES + 1):
            page_data = self._get_api_key_page(page)
            expected_total = page_data["total"]
            rows = page_data["rows"]
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError(
                        "Yunce API key response has an invalid row."
                    )
                collected.append(row)
            if len(collected) >= expected_total or not rows:
                return collected[:expected_total]
        raise ValueError("Yunce API key pagination limit exceeded.")

    def _normalize_api_key(self, row: Dict[str, Any]) -> Dict[str, Any]:
        rules = row.get("limit_rules") or {}
        if not isinstance(rules, dict):
            raise ValueError("Yunce API key limit rules are invalid.")
        currency = self._safe_text(
            rules.get("currency") or DEFAULT_CURRENCY,
            10,
        ).upper()
        if currency != DEFAULT_CURRENCY:
            raise ValueError("Yunce API returned an unsupported currency.")
        current_cost = self._parse_amount(
            rules.get("current_cost", 0),
            "current cost",
        )
        cost_threshold = self._parse_amount(
            rules.get("cost_threshold", 0),
            "cost threshold",
        )
        raw_item_id = row.get("id")
        if isinstance(raw_item_id, bool) or not isinstance(
            raw_item_id,
            (int, str),
        ):
            raise ValueError("Yunce API key response has an invalid id.")
        item_id = self._safe_text(raw_item_id, 100)
        if not item_id:
            raise ValueError("Yunce API key response is missing id.")
        status = row.get("status")
        if status not in {0, 1}:
            raise ValueError("Yunce API key response has an invalid status.")
        service_name = self._safe_text(row.get("displayname"), 200)
        if not service_name:
            service_name = f"API Key {item_id}"
        return {
            "service_name": service_name,
            "amount": current_cost,
            "currency": currency,
            "bill_id": item_id,
            "description": self._safe_text(row.get("description"), 500),
            "status": status,
            "cost_threshold": cost_threshold,
        }

    def _get_selected_api_key_remaining(
        self,
        rows: List[Dict[str, Any]],
    ) -> Optional[Decimal]:
        configured_api_key = self.config.api_key
        if not configured_api_key:
            return None

        selected_row = None
        for row in rows:
            raw_api_key = row.get("key_value")
            if not isinstance(raw_api_key, str):
                continue
            if secrets.compare_digest(
                raw_api_key.strip(),
                configured_api_key,
            ):
                selected_row = row
                break
        if selected_row is None:
            raise ValueError("Configured Yunce API key was not found.")

        normalized = self._normalize_api_key(selected_row)
        cost_threshold = normalized["cost_threshold"]
        if cost_threshold == 0:
            return None
        return max(cost_threshold - normalized["amount"], Decimal("0"))

    def _get_effective_balance(
        self,
        user_info: Dict[str, Any],
        rows: Optional[List[Dict[str, Any]]] = None,
    ) -> Decimal:
        account_balance = user_info["balance"]
        if not self.config.api_key:
            return account_balance
        if rows is None:
            rows = self._get_all_api_keys()
        api_key_remaining = self._get_selected_api_key_remaining(rows)
        if api_key_remaining is None:
            return account_balance
        return min(account_balance, api_key_remaining)

    @staticmethod
    def _error_message(exc: Exception) -> str:
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            return f"Yunce API request failed ({exc.response.status_code})."
        if isinstance(exc, requests.Timeout):
            return "Yunce API request timed out."
        if isinstance(exc, requests.RequestException):
            return "Yunce API request failed."
        return str(exc)

    def _set_balance_debug(self, user_info: Dict[str, Any]):
        self._last_balance_debug = {
            "status": "success",
            "currency": DEFAULT_CURRENCY,
            "total_recharge": float(user_info["total_recharge"]),
            "warning_threshold": user_info["warning_threshold"],
            "shutdown_threshold": user_info["shutdown_threshold"],
        }

    def get_balance(self) -> Optional[float]:
        """Return the remaining account balance from user info."""
        try:
            user_info = self._get_user_info()
            balance = self._get_effective_balance(user_info)
            self._set_balance_debug(user_info)
            return float(balance)
        except (requests.RequestException, ValueError) as exc:
            message = self._error_message(exc)
            self._last_balance_debug = {
                "status": "error",
                "error_message": message,
            }
            logger.warning("Yunce balance lookup failed: %s", message)
            return None

    def get_billing_info(
        self,
        period: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return account balance and current usage for each API key."""
        del period
        try:
            user_info = self._get_user_info()
            api_key_rows = self._get_all_api_keys()
            balance = self._get_effective_balance(
                user_info,
                api_key_rows,
            )
            normalized_items = [
                self._normalize_api_key(row) for row in api_key_rows
            ]
            total_cost = Decimal("0")
            service_costs = defaultdict(lambda: Decimal("0"))
            items = []
            for item in normalized_items:
                amount = item["amount"]
                total_cost += amount
                service_costs[item["service_name"]] += amount
                items.append(
                    {
                        **item,
                        "amount": float(amount),
                        "cost_threshold": float(item["cost_threshold"]),
                    }
                )

            self._set_balance_debug(user_info)
            return {
                "status": "success",
                "data": {
                    "total_cost": float(total_cost),
                    "balance": float(balance),
                    "balance_debug": self._last_balance_debug,
                    "currency": DEFAULT_CURRENCY,
                    "account_id": user_info["account_id"],
                    "service_costs": {
                        name: float(amount)
                        for name, amount in service_costs.items()
                    },
                    "items": items,
                },
                "error": None,
            }
        except (requests.RequestException, ValueError) as exc:
            message = self._error_message(exc)
            self._last_balance_debug = {
                "status": "error",
                "error_message": message,
            }
            logger.warning("Yunce billing lookup failed: %s", message)
            return {"status": "error", "data": None, "error": message}

    def get_account_id(self) -> str:
        """Return the Yunce user ID."""
        if self._last_account_id:
            return self._last_account_id
        return self._get_user_info()["account_id"]

    def validate_credentials(self) -> bool:
        """Validate credentials through login and user info APIs."""
        user_info = self._get_user_info()
        self._get_effective_balance(user_info)
        return True
