"""Baidu Cloud billing provider implementation.

This module provides billing and balance collection for Baidu AI Cloud
using Finance OpenAPI endpoints.

Official docs:
https://cloud.baidu.com/doc/Finance/s/0k8y4grdc
https://cloud.baidu.com/doc/Finance/s/ojxecslph
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlsplit

import requests
from django.utils import timezone

from ..utils.logging import mask_sensitive_config_object
from .provider import BaseCloudConfig, BaseCloudProvider

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://billing.baidubce.com"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_BILL_PAGE_SIZE = 100
DEFAULT_CURRENCY = "CNY"
DEFAULT_AUTH_EXPIRE = 1800
MONTH_BILL_PATH = "/v1/bill/resource/month"
CASH_BALANCE_PATH = "/v1/finance/cash/balance"
PRODUCT_TYPES = ("postpay", "prepay")


@dataclass
class BaiduConfig(BaseCloudConfig):
    """Baidu Cloud billing configuration."""

    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    timeout: int = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES

    def __post_init__(self):
        if self.api_key is None:
            self.api_key = os.getenv("BAIDU_ACCESS_KEY_ID")
        if self.api_secret is None:
            self.api_secret = os.getenv("BAIDU_SECRET_ACCESS_KEY")
        if self.timeout == DEFAULT_TIMEOUT:
            self.timeout = int(os.getenv("BAIDU_TIMEOUT", "30"))
        if self.max_retries == DEFAULT_MAX_RETRIES:
            self.max_retries = int(os.getenv("BAIDU_MAX_RETRIES", "3"))
        self._validate_config()

    def _validate_config(self):
        if not self.api_key:
            raise ValueError(
                "Baidu access key is required. Set it via constructor or "
                "BAIDU_ACCESS_KEY_ID environment variable."
            )
        if not self.api_secret:
            raise ValueError(
                "Baidu secret key is required. Set it via constructor or "
                "BAIDU_SECRET_ACCESS_KEY environment variable."
            )
        if self.timeout <= 0:
            raise ValueError("Timeout must be greater than 0")
        if self.max_retries < 0:
            raise ValueError("Max retries must be non-negative")


class BaiduCloud(BaseCloudProvider):
    """Baidu Cloud billing provider."""

    def __init__(self, config: BaiduConfig):
        super().__init__(config)
        self.name = "baidu"
        self._session = requests.Session()
        self._last_balance_debug = {}
        self._last_account_id = ""
        sanitized = mask_sensitive_config_object(config)
        logger.info(
            "Initialized Baidu Cloud provider with config: %s",
            sanitized,
        )

    @staticmethod
    def _normalize_period(period: Optional[str]) -> str:
        if not period:
            period = timezone.now().strftime("%Y-%m")
        try:
            datetime.strptime(period, "%Y-%m")
        except ValueError as exc:
            raise ValueError("Invalid period format. Use YYYY-MM") from exc
        return period

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        try:
            if value is None or value == "":
                return Decimal("0")
            if isinstance(value, str):
                value = value.replace(",", "").strip()
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    @staticmethod
    def _iso_timestamp(now: Optional[datetime] = None) -> str:
        now = now or timezone.now()
        return now.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _hmac_sha256(key: bytes, value: str) -> bytes:
        return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()

    @staticmethod
    def _hmac_sha256_hex(key: bytes, value: str) -> str:
        return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def _normalize_string(value: Any, encode_slash: bool = True) -> str:
        safe_chars = "-_.~" if encode_slash else "/-_.~"
        return quote("" if value is None else str(value), safe=safe_chars)

    @staticmethod
    def _canonical_query(params: Dict[str, Any]) -> str:
        items: List[Tuple[str, str]] = []
        for key in sorted(params.keys()):
            value = params[key]
            items.append((str(key), "" if value is None else str(value)))
        return "&".join(
            f"{BaiduCloud._normalize_string(key)}="
            f"{BaiduCloud._normalize_string(value)}"
            for key, value in items
        )

    @staticmethod
    def _canonical_headers(headers: Dict[str, str]) -> str:
        included = {}
        for key, value in headers.items():
            key_lower = key.strip().lower()
            if key_lower in {
                "host",
                "content-type",
                "content-length",
                "content-md5",
            } or key_lower.startswith("x-bce-"):
                normalized_value = " ".join(str(value).strip().split())
                included[
                    BaiduCloud._normalize_string(key_lower)
                ] = BaiduCloud._normalize_string(normalized_value)
        return "\n".join(
            f"{key}:{included[key]}" for key in sorted(included.keys())
        )

    def _sign_headers(
        self,
        method: str,
        path: str,
        query_params: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, str]:
        timestamp = headers["x-bce-date"]
        auth_prefix = (
            f"bce-auth-v1/{self.config.api_key}/{timestamp}/"
            f"{DEFAULT_AUTH_EXPIRE}"
        )
        signing_key = self._hmac_sha256_hex(
            self.config.api_secret.encode("utf-8"),
            auth_prefix,
        )
        canonical_headers = self._canonical_headers(headers)
        canonical_request = "\n".join(
            [
                method.upper(),
                path,
                self._canonical_query(query_params),
                canonical_headers,
            ]
        )
        signature = self._hmac_sha256_hex(
            signing_key.encode("utf-8"), canonical_request
        )
        authorization = f"{auth_prefix}//{signature}"
        signed = headers.copy()
        signed["Authorization"] = authorization
        return signed

    def _request_json(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        params = params or {}
        body_text = ""
        if json_body is not None:
            body_text = "{}"
        parsed = urlsplit(DEFAULT_ENDPOINT)
        base_url = DEFAULT_ENDPOINT
        host = parsed.netloc or parsed.path
        url = f"{base_url}{path}"
        headers = {
            "host": host,
            "x-bce-date": self._iso_timestamp(),
            "content-type": "application/json",
            "content-length": str(len(body_text.encode("utf-8"))),
        }
        signed_headers = self._sign_headers(method, path, params, headers)
        last_error: Optional[Exception] = None
        request_data = body_text if json_body is not None else None

        for attempt in range(self.config.max_retries + 1):
            try:
                response = self._session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=request_data,
                    headers=signed_headers,
                    timeout=self.config.timeout,
                )
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    if isinstance(exc, ValueError):
                        raise ValueError(
                            "Baidu API returned non-JSON response"
                        ) from exc
                    raise
                logger.debug(
                    "Retrying Baidu API request (attempt=%s, path=%s): %s",
                    attempt + 1,
                    path,
                    exc,
                )

        if last_error is not None:
            raise last_error
        raise RuntimeError("Baidu API request failed unexpectedly")

    @staticmethod
    def _extract_payload_data(payload: Dict[str, Any]) -> Any:
        for key in ("result", "data", "items", "list"):
            value = payload.get(key)
            if value is not None:
                return value
        return payload

    @staticmethod
    def _extract_error(payload: Dict[str, Any]) -> Optional[str]:
        for key in ("message", "msg", "errorMsg", "error", "error_message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _get_period_dates(period: str) -> Tuple[str, str]:
        year, month = map(int, period.split("-"))
        if month == 12:
            next_year, next_month = year + 1, 1
        else:
            next_year, next_month = year, month + 1
        period_start = datetime(year, month, 1)
        period_end = datetime(next_year, next_month, 1) - timedelta(days=1)
        today = timezone.localdate()
        if year == today.year and month == today.month:
            yesterday = today - timedelta(days=1)
            period_end = min(
                period_end,
                datetime.combine(yesterday, datetime.min.time()),
            )
        if period_end < period_start:
            period_end = period_start
        return period_start.strftime("%Y-%m-%d"), period_end.strftime("%Y-%m-%d")

    def _request_month_bill(
        self,
        period: str,
        begin_time: str,
        end_time: str,
        product_type: str,
        service_type: str,
        page_no: int,
    ) -> Dict[str, Any]:
        params = {
            "month": period,
            "beginTime": begin_time,
            "endTime": end_time,
            "productType": product_type,
            "pageNo": page_no,
            "pageSize": DEFAULT_BILL_PAGE_SIZE,
        }
        if service_type:
            params["serviceType"] = service_type
        return self._request_json(
            "GET",
            MONTH_BILL_PATH,
            params=params,
        )

    def _request_cash_balance(self) -> Dict[str, Any]:
        return self._request_json(
            "POST",
            CASH_BALANCE_PATH,
            json_body={},
        )

    def _parse_bill_items(
        self,
        payload: Dict[str, Any],
        product_type: str,
    ) -> Tuple[List[Dict[str, Any]], int]:
        data = self._extract_payload_data(payload)
        if isinstance(data, dict):
            items = (
                data.get("items")
                or data.get("list")
                or data.get("bills")
                or data.get("result")
                or []
            )
            total_count = (
                data.get("totalCount")
                or data.get("total")
                or data.get("count")
                or len(items)
            )
        elif isinstance(data, list):
            items = data
            total_count = len(items)
        else:
            items = []
            total_count = 0

        normalized = []
        for item in items:
            if not isinstance(item, dict):
                continue
            normalized.append({**item, "_product_type": product_type})
        return normalized, int(total_count or 0)

    def _collect_bill_items(self, period: str) -> List[Dict[str, Any]]:
        all_items: List[Dict[str, Any]] = []
        begin_time, end_time = self._get_period_dates(period)
        for product_type in PRODUCT_TYPES:
            page_no = 1
            while True:
                payload = self._request_month_bill(
                    period,
                    begin_time,
                    end_time,
                    product_type,
                    "",
                    page_no,
                )
                error_message = self._extract_error(payload)
                if error_message:
                    raise RuntimeError(error_message)
                items, total_count = self._parse_bill_items(payload, product_type)
                all_items.extend(items)
                if not items or len(items) < DEFAULT_BILL_PAGE_SIZE:
                    break
                if total_count and page_no * DEFAULT_BILL_PAGE_SIZE >= total_count:
                    break
                page_no += 1
        return all_items

    def _calculate_bill_summary(
        self, items: List[Dict[str, Any]]
    ) -> Tuple[float, str, Dict[str, float], List[Dict[str, Any]], str]:
        total_cost = Decimal("0")
        currency = DEFAULT_CURRENCY
        service_costs: Dict[str, float] = {}
        normalized_items: List[Dict[str, Any]] = []
        account_id = self._last_account_id or ""

        for item in items:
            amount = self._to_decimal(
                item.get("financePrice")
                or item.get("orderPrice")
                or item.get("cash")
                or item.get("amount")
                or 0
            )
            total_cost += amount

            item_currency = str(
                item.get("currency")
                or item.get("currencyCode")
                or currency
                or DEFAULT_CURRENCY
            )
            currency = item_currency
            service_name = str(
                item.get("serviceTypeName")
                or item.get("serviceName")
                or item.get("productName")
                or item.get("productType")
                or item.get("serviceType")
                or "Unknown"
            )
            service_costs[service_name] = (
                service_costs.get(service_name, 0.0) + float(amount)
            )

            if not account_id:
                account_id = str(
                    item.get("accountId")
                    or item.get("account_id")
                    or item.get("userId")
                    or ""
                )

            normalized_items.append(
                {
                    "service_name": service_name,
                    "amount": float(amount),
                    "currency": item_currency,
                    "bill_id": item.get("billId") or item.get("orderId") or "",
                    "product_type": item.get("_product_type", ""),
                    "raw": item,
                }
            )

        if account_id:
            self._last_account_id = account_id

        return (
            float(total_cost),
            currency,
            service_costs,
            normalized_items,
            account_id,
        )

    def get_balance(self) -> Optional[float]:
        try:
            payload = self._request_cash_balance()
            error_message = self._extract_error(payload)
            if error_message:
                raise RuntimeError(error_message)

            data = self._extract_payload_data(payload)
            if not isinstance(data, dict):
                data = payload

            account_id = str(
                data.get("accountId")
                or data.get("account_id")
                or self._last_account_id
                or ""
            )
            if account_id:
                self._last_account_id = account_id

            balance_raw = (
                data.get("cashBalance")
                or data.get("availableBalance")
                or data.get("balance")
                or data.get("amount")
            )
            balance = float(self._to_decimal(balance_raw)) if balance_raw is not None else None
            currency = str(
                data.get("currency")
                or data.get("currencyCode")
                or DEFAULT_CURRENCY
            )
            self._last_balance_debug = {
                "status": "success",
                "account_id": account_id,
                "currency": currency,
                "cash_balance": data.get("cashBalance"),
                "available_balance": data.get("availableBalance"),
                "balance": data.get("balance"),
                "voucher_balance": data.get("voucherBalance"),
                "response_keys": list(data.keys()),
            }
            return balance
        except requests.HTTPError as exc:
            body = exc.response.text if exc.response is not None else str(exc)
            self._last_balance_debug = {
                "status": "http_error",
                "error_message": body,
            }
            logger.warning("Baidu balance lookup failed: %s", body)
            return None
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            self._last_balance_debug = {
                "status": "error",
                "error_message": str(exc),
            }
            logger.warning("Baidu balance lookup failed: %s", exc)
            return None
        except Exception as exc:
            self._last_balance_debug = {
                "status": "unexpected_error",
                "error_message": str(exc),
            }
            logger.warning("Unexpected Baidu balance lookup error: %s", exc)
            return None

    def get_billing_info(self, period: Optional[str] = None) -> Dict[str, Any]:
        try:
            normalized_period = self._normalize_period(period)
            items = self._collect_bill_items(normalized_period)
            (
                total_cost,
                currency,
                service_costs,
                normalized_items,
                account_id,
            ) = self._calculate_bill_summary(items)
            balance = self.get_balance()
            if self._last_balance_debug.get("currency"):
                currency = self._last_balance_debug["currency"]
            account_id = account_id or self._last_balance_debug.get("account_id") or ""
            return {
                "status": "success",
                "data": {
                    "total_cost": total_cost,
                    "balance": balance,
                    "balance_debug": self._last_balance_debug,
                    "currency": currency,
                    "account_id": account_id,
                    "service_costs": service_costs,
                    "items": normalized_items,
                },
                "error": None,
            }
        except requests.HTTPError as exc:
            body = exc.response.text if exc.response is not None else str(exc)
            status_code = (
                exc.response.status_code if exc.response is not None else None
            )
            logger.error(
                "Baidu billing HTTP error (status=%s, body=%s)",
                status_code,
                body,
            )
            return {"status": "error", "data": None, "error": body}
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            logger.error("Baidu billing error: %s", exc)
            return {"status": "error", "data": None, "error": str(exc)}
        except Exception as exc:
            logger.exception("Unexpected Baidu billing error: %s", exc)
            return {"status": "error", "data": None, "error": str(exc)}

    def get_account_id(self) -> str:
        if self._last_account_id:
            return self._last_account_id
        try:
            balance = self.get_balance()
            if balance is not None and self._last_account_id:
                return self._last_account_id
            result = self.get_billing_info()
            if result.get("status") == "success":
                return str((result.get("data") or {}).get("account_id") or "")
        except Exception:
            logger.debug("Baidu account ID lookup failed", exc_info=True)
        return ""

    def validate_credentials(self) -> bool:
        balance = self.get_balance()
        if balance is not None:
            return True
        debug_status = self._last_balance_debug.get("status")
        if debug_status == "success":
            return True
        result = self.get_billing_info()
        return result.get("status") == "success"
