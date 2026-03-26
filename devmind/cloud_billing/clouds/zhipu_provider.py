"""Zhipu AI billing provider implementation.

This provider uses the BigModel web endpoints by simulating a user login,
then queries account balance and monthly billing summary with the returned
JWT token.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional

import requests
from django.utils import timezone

from ..utils.logging import mask_sensitive_config_object
from .provider import BaseCloudConfig, BaseCloudProvider

logger = logging.getLogger(__name__)

BASE_URL = "https://bigmodel.cn"
LOGIN_PATH = "/api/auth/login"
ACCOUNT_REPORT_PATH = "/api/biz/account/query-customer-account-report"
MONTHLY_BILL_PATH = "/api/finance/monthlyBill/aggregatedMonthlyBills"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_CURRENCY = "CNY"
DEFAULT_USER_TYPE = "PERSONAL"
DEFAULT_PAGE_SIZE = 100
SUCCESS_CODES = {0, "0", 200, "200", "SUCCESS", "success", "0000", "000000"}
BALANCE_KEYS = (
    "availableBalance",
    "remainingBalance",
    "accountBalance",
    "balance",
    "availableAmount",
    "remainingAmount",
)
BILL_AMOUNT_KEYS = (
    "paidAmount",
    "totalAmount",
    "billAmount",
    "payableAmount",
    "settlementAmount",
    "dueAmount",
    "cashAmount",
    "amount",
    "consumeAmount",
    "totalFee",
)


@dataclass
class ZhipuConfig(BaseCloudConfig):
    """Zhipu AI billing configuration."""

    username: Optional[str] = None
    password: Optional[str] = None
    user_type: str = DEFAULT_USER_TYPE
    timeout: int = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES

    def __post_init__(self):
        if self.username is None:
            self.username = os.getenv("ZHIPU_USERNAME")
        if self.password is None:
            self.password = os.getenv("ZHIPU_PASSWORD")
        if self.user_type == DEFAULT_USER_TYPE:
            self.user_type = os.getenv("ZHIPU_USER_TYPE", DEFAULT_USER_TYPE)
        if self.timeout == DEFAULT_TIMEOUT:
            self.timeout = int(os.getenv("ZHIPU_TIMEOUT", str(DEFAULT_TIMEOUT)))
        if self.max_retries == DEFAULT_MAX_RETRIES:
            self.max_retries = int(
                os.getenv("ZHIPU_MAX_RETRIES", str(DEFAULT_MAX_RETRIES))
            )
        self._validate_config()

    def _validate_config(self):
        if not self.username:
            raise ValueError("Zhipu username is required.")
        if not self.password:
            raise ValueError("Zhipu password is required.")
        if self.timeout <= 0:
            raise ValueError("Timeout must be greater than 0.")
        if self.max_retries < 0:
            raise ValueError("Max retries must be non-negative.")


class ZhipuCloud(BaseCloudProvider):
    """Zhipu AI billing provider."""

    def __init__(self, config: ZhipuConfig):
        super().__init__(config)
        self.name = "zhipu"
        self._session = requests.Session()
        self._token: Optional[str] = None
        self._token_payload: Dict[str, Any] = {}
        self._last_balance_debug: Dict[str, Any] = {}
        self._last_account_id = ""
        logger.info(
            "Initialized Zhipu provider with config: %s",
            mask_sensitive_config_object(config),
        )

    @staticmethod
    def _normalize_period(period: Optional[str]) -> str:
        normalized = period or timezone.now().strftime("%Y-%m")
        try:
            datetime.strptime(normalized, "%Y-%m")
        except ValueError as exc:
            raise ValueError("Invalid period format. Use YYYY-MM.") from exc
        return normalized

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        if value is None or value == "":
            return Decimal("0")
        try:
            if isinstance(value, str):
                value = value.replace(",", "").strip()
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    @staticmethod
    def _extract_payload_data(payload: Dict[str, Any]) -> Any:
        for key in ("data", "result", "payload"):
            if key in payload and payload[key] is not None:
                return payload[key]
        return payload

    @staticmethod
    def _iter_dicts(value: Any) -> Iterable[Dict[str, Any]]:
        if isinstance(value, dict):
            yield value
            for item in value.values():
                yield from ZhipuCloud._iter_dicts(item)
        elif isinstance(value, list):
            for item in value:
                yield from ZhipuCloud._iter_dicts(item)

    @staticmethod
    def _decode_jwt_payload(token: str) -> Dict[str, Any]:
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return {}
            payload = parts[1]
            payload += "=" * (-len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload.encode("utf-8"))
            return json.loads(decoded.decode("utf-8"))
        except Exception:
            return {}

    @staticmethod
    def _extract_token(payload: Dict[str, Any]) -> Optional[str]:
        data = ZhipuCloud._extract_payload_data(payload)
        candidates = []
        if isinstance(data, dict):
            candidates.extend(
                [
                    data.get("accessToken"),
                    data.get("access_token"),
                    data.get("token"),
                    data.get("jwt"),
                ]
            )
        candidates.extend(
            [
                payload.get("accessToken"),
                payload.get("access_token"),
                payload.get("token"),
                payload.get("jwt"),
            ]
        )
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None

    @staticmethod
    def _find_first_numeric(
        payload: Any,
        candidate_keys: Iterable[str],
    ) -> Optional[Decimal]:
        lowered = {key.lower() for key in candidate_keys}
        for item in ZhipuCloud._iter_dicts(payload):
            for key, value in item.items():
                if key.lower() not in lowered:
                    continue
                amount = ZhipuCloud._to_decimal(value)
                if value is not None and str(value).strip() != "":
                    return amount
        return None

    @staticmethod
    def _find_first_string(
        payload: Any,
        candidate_keys: Iterable[str],
    ) -> str:
        lowered = {key.lower() for key in candidate_keys}
        for item in ZhipuCloud._iter_dicts(payload):
            for key, value in item.items():
                if key.lower() in lowered and isinstance(value, str):
                    stripped = value.strip()
                    if stripped:
                        return stripped
        return ""

    @staticmethod
    def _find_records_list(payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, dict):
            for key in ("list", "records", "rows", "items", "data"):
                value = payload.get(key)
                if (
                    isinstance(value, list)
                    and value
                    and all(isinstance(item, dict) for item in value)
                ):
                    return value
            for value in payload.values():
                records = ZhipuCloud._find_records_list(value)
                if records:
                    return records
        elif isinstance(payload, list):
            if payload and all(isinstance(item, dict) for item in payload):
                return payload
            for item in payload:
                records = ZhipuCloud._find_records_list(item)
                if records:
                    return records
        return []

    def _build_headers(self, include_auth: bool = False) -> Dict[str, str]:
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh",
            "content-type": "application/json;charset=UTF-8",
            "origin": BASE_URL,
            "referer": f"{BASE_URL}/finance-center/finance/overview",
            "set-language": "zh",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
        }
        if include_auth:
            headers["authorization"] = self._ensure_token()
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        include_auth: bool = False,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{BASE_URL}{path}"
        last_error: Optional[Exception] = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self._session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_body,
                    headers=self._build_headers(include_auth=include_auth),
                    timeout=self.config.timeout,
                )
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    raise
                logger.debug(
                    "Retrying Zhipu request (attempt=%s, path=%s, error=%s)",
                    attempt + 1,
                    path,
                    exc,
                )
        if last_error:
            raise last_error
        raise RuntimeError("Zhipu request failed unexpectedly.")

    def _ensure_token(self) -> str:
        if self._token:
            return self._token

        payload = self._request(
            "POST",
            LOGIN_PATH,
            json_body={
                "phoneNumber": "",
                "countryCode": "",
                "username": self.config.username,
                "smsCode": "",
                "password": self.config.password,
                "loginType": "password",
                "grantType": "customer",
                "userType": self.config.user_type,
                "userCode": "",
                "appId": "",
                "anonymousId": uuid.uuid4().hex,
            },
        )
        if not self._is_success_payload(payload):
            message = self._extract_error_message(payload) or "Login failed."
            raise RuntimeError(message)
        token = self._extract_token(payload)
        if not token:
            message = self._extract_error_message(payload) or "Login failed."
            raise RuntimeError(message)

        self._token = token
        self._token_payload = self._decode_jwt_payload(token)
        self._last_account_id = (
            str(
                self._token_payload.get("customer_id")
                or self._token_payload.get("customerId")
                or self._token_payload.get("username")
                or self._token_payload.get("user_id")
                or self.config.username
                or ""
            )
        )
        return token

    @staticmethod
    def _extract_error_message(payload: Dict[str, Any]) -> str:
        message = payload.get("message") or payload.get("msg") or ""
        if isinstance(message, str):
            return message.strip()
        return ""

    @staticmethod
    def _is_success_payload(payload: Dict[str, Any]) -> bool:
        if "success" in payload and isinstance(payload["success"], bool):
            return payload["success"]
        code = payload.get("code")
        if code is None or code == "":
            return True
        return code in SUCCESS_CODES

    def _query_account_report(self) -> Dict[str, Any]:
        return self._request("GET", ACCOUNT_REPORT_PATH, include_auth=True)

    def _query_monthly_bill(self, period: str, page_num: int) -> Dict[str, Any]:
        return self._request(
            "GET",
            MONTHLY_BILL_PATH,
            include_auth=True,
            params={
                "billingMonthStart": period,
                "billingMonthEnd": period,
                "pageNum": page_num,
                "pageSize": DEFAULT_PAGE_SIZE,
            },
        )

    def get_balance(self) -> Optional[float]:
        try:
            payload = self._query_account_report()
            if not self._is_success_payload(payload):
                raise RuntimeError(
                    self._extract_error_message(payload)
                    or "Query account report failed."
                )
            data = self._extract_payload_data(payload)
            balance_decimal = self._find_first_numeric(data, BALANCE_KEYS)
            currency = self._find_first_string(
                data,
                ("currency", "currencyCode", "settlementCurrency"),
            ) or DEFAULT_CURRENCY
            balance = (
                float(balance_decimal) if balance_decimal is not None else None
            )
            self._last_balance_debug = {
                "status": "success",
                "currency": currency,
                "parsed_balance": balance,
                "token_payload": {
                    "customer_id": self._token_payload.get("customer_id"),
                    "username": self._token_payload.get("username"),
                    "user_id": self._token_payload.get("user_id"),
                },
                "response_keys": list(data.keys()) if isinstance(data, dict) else [],
            }
            return balance
        except requests.HTTPError as exc:
            body = exc.response.text if exc.response is not None else str(exc)
            self._last_balance_debug = {
                "status": "http_error",
                "error_message": body,
            }
            logger.warning("Zhipu balance lookup failed: %s", body)
            return None
        except Exception as exc:
            self._last_balance_debug = {
                "status": "error",
                "error_message": str(exc),
            }
            logger.warning("Zhipu balance lookup failed: %s", exc)
            return None

    def _parse_bill_records(self, payload: Dict[str, Any], period: str) -> List[Dict[str, Any]]:
        data = self._extract_payload_data(payload)
        records = self._find_records_list(data)
        if records:
            return records
        if isinstance(data, dict):
            billing_month = str(
                data.get("billingMonth") or data.get("month") or data.get("period") or ""
            )
            if not billing_month or billing_month == period:
                return [data]
        return []

    def get_billing_info(self, period: Optional[str] = None) -> Dict[str, Any]:
        try:
            normalized_period = self._normalize_period(period)
            total_cost = Decimal("0")
            records: List[Dict[str, Any]] = []
            page_num = 1

            while True:
                payload = self._query_monthly_bill(normalized_period, page_num)
                if not self._is_success_payload(payload):
                    raise RuntimeError(
                        self._extract_error_message(payload)
                        or "Query monthly bill failed."
                    )
                page_records = self._parse_bill_records(payload, normalized_period)
                if not page_records:
                    break
                records.extend(page_records)
                if len(page_records) < DEFAULT_PAGE_SIZE:
                    break
                page_num += 1

            currency = DEFAULT_CURRENCY
            normalized_items = []
            for record in records:
                record_period = str(
                    record.get("billingMonth")
                    or record.get("month")
                    or record.get("period")
                    or normalized_period
                )
                if record_period and record_period != normalized_period:
                    continue
                amount = None
                for key in BILL_AMOUNT_KEYS:
                    if key in record and record[key] not in (None, ""):
                        amount = self._to_decimal(record[key])
                        break
                if amount is None:
                    continue
                total_cost += amount
                currency = str(
                    record.get("currency")
                    or record.get("currencyCode")
                    or currency
                    or DEFAULT_CURRENCY
                )
                normalized_items.append(
                    {
                        "service_name": "智谱 AI",
                        "amount": float(amount),
                        "currency": currency,
                        "bill_id": record.get("id") or record.get("billId") or record_period,
                        "raw": record,
                    }
                )

            balance = self.get_balance()
            if self._last_balance_debug.get("currency"):
                currency = self._last_balance_debug["currency"]
            return {
                "status": "success",
                "data": {
                    "total_cost": float(total_cost),
                    "balance": balance,
                    "balance_debug": self._last_balance_debug,
                    "currency": currency,
                    "account_id": self._last_account_id,
                    "service_costs": {"智谱 AI": float(total_cost)},
                    "items": normalized_items,
                },
                "error": None,
            }
        except requests.HTTPError as exc:
            body = exc.response.text if exc.response is not None else str(exc)
            logger.error("Zhipu billing HTTP error: %s", body)
            return {"status": "error", "data": None, "error": body}
        except Exception as exc:
            logger.error("Zhipu billing error: %s", exc)
            return {"status": "error", "data": None, "error": str(exc)}

    def get_account_id(self) -> str:
        if self._last_account_id:
            return self._last_account_id
        try:
            self._ensure_token()
        except Exception:
            return self.config.username or ""
        return self._last_account_id or self.config.username or ""

    def validate_credentials(self) -> bool:
        try:
            self._ensure_token()
            return True
        except Exception as exc:
            logger.warning("Zhipu credential validation failed: %s", exc)
            return False
