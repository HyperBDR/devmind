"""Volcengine cloud provider implementation.

This module provides billing collection for Volcengine using the
Billing OpenAPI.

API docs:
https://www.volcengine.com/docs/6269/130258?lang=zh
https://www.volcengine.com/docs/6269/1165274
https://www.volcengine.com/docs/6269/1165275
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from itertools import count
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlsplit

import requests
from django.utils import timezone

from ..utils.logging import mask_sensitive_config_object
from .provider import BaseCloudConfig, BaseCloudProvider

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://billing.volcengineapi.com"
DEFAULT_REGION = "cn-north-1"
DEFAULT_SERVICE = "billing"
DEFAULT_VERSION = "2022-01-01"
DEFAULT_LIMIT = 100
DEFAULT_ACTION = "ListBill"
DEFAULT_BALANCE_ACTION = "QueryBalanceAcct"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3


@dataclass
class VolcengineConfig(BaseCloudConfig):
    """Volcengine billing configuration."""

    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    region: Optional[str] = DEFAULT_REGION
    endpoint: str = DEFAULT_ENDPOINT
    service: str = DEFAULT_SERVICE
    version: str = DEFAULT_VERSION
    payer_id: Optional[str] = None
    timeout: int = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES

    def __post_init__(self):
        self._load_env_defaults()
        self._validate_config()

    def _load_env_defaults(self):
        if self.api_key is None:
            self.api_key = os.getenv("VOLCENGINE_ACCESS_KEY_ID")
        if self.api_secret is None:
            self.api_secret = os.getenv(
                "VOLCENGINE_SECRET_ACCESS_KEY"
            ) or os.getenv("VOLCENGINE_ACCESS_KEY_SECRET")
        if self.region is None:
            self.region = os.getenv("VOLCENGINE_REGION", DEFAULT_REGION)
        if self.endpoint == DEFAULT_ENDPOINT:
            self.endpoint = os.getenv("VOLCENGINE_ENDPOINT", DEFAULT_ENDPOINT)
        if self.service == DEFAULT_SERVICE:
            self.service = os.getenv("VOLCENGINE_SERVICE", DEFAULT_SERVICE)
        if self.version == DEFAULT_VERSION:
            self.version = os.getenv("VOLCENGINE_VERSION", DEFAULT_VERSION)
        if self.payer_id is None:
            self.payer_id = os.getenv("VOLCENGINE_PAYER_ID")
        if self.timeout == DEFAULT_TIMEOUT:
            self.timeout = int(
                os.getenv("VOLCENGINE_TIMEOUT", str(DEFAULT_TIMEOUT))
            )
        if self.max_retries == DEFAULT_MAX_RETRIES:
            self.max_retries = int(
                os.getenv("VOLCENGINE_MAX_RETRIES", str(DEFAULT_MAX_RETRIES))
            )

    def _validate_config(self):
        if not self.api_key:
            raise ValueError(
                "Volcengine access key is required. Set it via constructor or "
                "VOLCENGINE_ACCESS_KEY_ID environment variable."
            )
        if not self.api_secret:
            raise ValueError(
                "Volcengine secret key is required. Set it via constructor or "
                "VOLCENGINE_SECRET_ACCESS_KEY environment variable."
            )
        if not self.region:
            raise ValueError(
                "Volcengine region is required. Set it via constructor or "
                "VOLCENGINE_REGION environment variable."
            )
        if self.timeout <= 0:
            raise ValueError("Timeout must be greater than 0")
        if self.max_retries < 0:
            raise ValueError("Max retries must be non-negative")


class VolcengineCloud(BaseCloudProvider):
    """Volcengine cloud billing provider."""

    def __init__(self, config: VolcengineConfig):
        super().__init__(config)
        self.name = "volcengine"
        self._session = requests.Session()
        self._last_balance_debug = {}
        sanitized_config = mask_sensitive_config_object(config)
        logger.info(
            f"Initialized Volcengine Cloud provider with config: "
            f"{sanitized_config}"
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
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    @staticmethod
    def _format_x_date(now: Optional[datetime] = None) -> str:
        now = now or timezone.now()
        return now.strftime("%Y%m%dT%H%M%SZ")

    @staticmethod
    def _sha256_hex(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _hmac_sha256(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    @staticmethod
    def _canonical_query(params: Dict[str, Any]) -> str:
        items: List[Tuple[str, str]] = []
        for key in sorted(params.keys()):
            value = params[key]
            if value is None or value == "":
                continue
            items.append((key, str(value)))
        return "&".join(
            f'{quote(key, safe="-_.~")}={quote(value, safe="-_.~")}'
            for key, value in items
        )

    def _sign_headers(
        self,
        method: str,
        host: str,
        query_params: Dict[str, Any],
        x_date: str,
    ) -> Dict[str, str]:
        canonical_query = self._canonical_query(query_params)
        canonical_headers = f"host:{host}\n" f"x-date:{x_date}\n"
        signed_headers = "host;x-date"
        canonical_request = "\n".join(
            [
                method.upper(),
                "/",
                canonical_query,
                canonical_headers,
                signed_headers,
                self._sha256_hex(""),
            ]
        )
        short_date = x_date[:8]
        scope = (
            f"{short_date}/{self.config.region}/{self.config.service}/request"
        )
        string_to_sign = "\n".join(
            [
                "HMAC-SHA256",
                x_date,
                scope,
                self._sha256_hex(canonical_request),
            ]
        )
        # Match Volcengine OpenAPI signer:
        # HMAC(secret, date) -> region -> service -> request.
        signing_key = self._hmac_sha256(
            self.config.api_secret.encode("utf-8"),
            short_date,
        )
        signing_key = self._hmac_sha256(signing_key, self.config.region or "")
        signing_key = self._hmac_sha256(signing_key, self.config.service or "")
        signing_key = self._hmac_sha256(signing_key, "request")
        signature = hmac.new(
            signing_key,
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        authorization = (
            f"HMAC-SHA256 Credential={self.config.api_key}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        return {
            "Authorization": authorization,
            "X-Date": x_date,
            "Host": host,
        }

    def _request_list_bill(
        self,
        period: str,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> Dict[str, Any]:
        url, host = self._resolve_request_target()
        query_params = self._build_list_bill_params(
            period,
            limit,
            offset,
            self.config.version or DEFAULT_VERSION,
        )
        x_date = self._format_x_date()
        headers = self._sign_headers("GET", host, query_params, x_date)
        return self._request_json_with_retry(
            url=url,
            params=query_params,
            headers=headers,
            period=period,
            offset=offset,
        )

    def _request_query_balance(self) -> Dict[str, Any]:
        """Call QueryBalanceAcct to fetch account balance."""
        url, host = self._resolve_request_target()
        query_params = {
            "Action": DEFAULT_BALANCE_ACTION,
            "Version": self.config.version or DEFAULT_VERSION,
        }
        x_date = self._format_x_date()
        headers = self._sign_headers("GET", host, query_params, x_date)
        return self._request_json_with_retry(
            url=url,
            params=query_params,
            headers=headers,
            period="balance",
            offset=0,
        )

    def _resolve_request_target(self) -> Tuple[str, str]:
        parsed = urlsplit(self.config.endpoint or DEFAULT_ENDPOINT)
        return (
            self.config.endpoint or DEFAULT_ENDPOINT,
            parsed.netloc or parsed.path,
        )

    @staticmethod
    def _build_list_bill_params(
        period: str,
        limit: int,
        offset: int,
        version: str,
    ) -> Dict[str, Any]:
        return {
            "Action": DEFAULT_ACTION,
            "BillPeriod": period,
            "Limit": limit,
            "Offset": offset,
            "Version": version,
        }

    def _request_json_with_retry(
        self,
        url: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
        period: str,
        offset: int,
    ) -> Dict[str, Any]:
        last_error: Optional[Exception] = None

        for attempt in range(self.config.max_retries + 1):
            try:
                response = self._session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.config.timeout,
                )
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    if isinstance(exc, ValueError):
                        raise ValueError(
                            "Volcengine API returned non-JSON response"
                        ) from exc
                    raise
                logger.debug(
                    "Retrying Volcengine bill request "
                    f"(attempt={attempt + 1}, period={period}, "
                    f"offset={offset}): {exc}"
                )

        if last_error is not None:
            raise last_error
        raise RuntimeError("Volcengine bill request failed unexpectedly")

    @staticmethod
    def _extract_error(payload: Dict[str, Any]) -> str:
        metadata = payload.get("ResponseMetadata") or {}
        error = metadata.get("Error") or payload.get("Error")
        if isinstance(error, dict):
            code = error.get("Code") or error.get("code") or "Unknown"
            message = (
                error.get("Message") or error.get("message") or "Unknown error"
            )
            return f"{code}: {message}"
        if isinstance(error, list) and error:
            first = error[0]
            if isinstance(first, dict):
                code = first.get("Code") or first.get("code") or "Unknown"
                message = (
                    first.get("Message")
                    or first.get("message")
                    or "Unknown error"
                )
                return f"{code}: {message}"
        if error:
            return str(error)
        return "Unknown Volcengine API error"

    @staticmethod
    def _extract_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        result = payload.get("Result") or {}
        if not isinstance(result, dict):
            return []
        for key in ("List", "BillList", "Items", "Data"):
            items = result.get(key)
            if isinstance(items, list):
                return items
        return []

    @staticmethod
    def _extract_total(payload: Dict[str, Any], default: int) -> int:
        result = payload.get("Result") or {}
        if not isinstance(result, dict):
            return default
        for key in ("Total", "Count", "TotalCount"):
            value = result.get(key)
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return default
        return default

    @staticmethod
    def _extract_result_object(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return the Volcengine Result object when present."""
        result = payload.get("Result") or {}
        return result if isinstance(result, dict) else {}

    def _parse_bill_items(
        self,
        items: List[Dict[str, Any]],
    ) -> Tuple[Decimal, str, Dict[str, float], List[Dict[str, Any]], str]:
        total_cost = Decimal("0")
        currency = "CNY"
        service_costs: Dict[str, float] = {}
        normalized_items: List[Dict[str, Any]] = []
        account_id = self.config.payer_id or ""

        for item in items:
            if not isinstance(item, dict):
                continue
            amount = self._to_decimal(self._get_item_amount(item))
            total_cost += amount

            currency = str(item.get("Currency") or currency or "CNY")
            service_name = self._get_item_service_name(item)
            service_costs[service_name] = service_costs.get(
                service_name, 0.0
            ) + float(amount)

            if not account_id:
                account_id = str(
                    item.get("PayerID")
                    or item.get("OwnerID")
                    or item.get("PayerUserName")
                    or ""
                )

            normalized_items.append(
                self._normalize_bill_item(item, amount, currency)
            )

        return (
            total_cost,
            currency,
            service_costs,
            normalized_items,
            account_id,
        )

    @staticmethod
    def _get_item_amount(item: Dict[str, Any]) -> Any:
        return (
            item.get("PayableAmount")
            or item.get("PaidAmount")
            or item.get("DiscountBillAmount")
            or item.get("OriginalBillAmount")
            or item.get("RoundBillAmount")
            or 0
        )

    @staticmethod
    def _get_item_service_name(item: Dict[str, Any]) -> str:
        return str(item.get("ProductZh") or item.get("Product") or "Unknown")

    @staticmethod
    def _normalize_bill_item(
        item: Dict[str, Any],
        amount: Decimal,
        currency: str,
    ) -> Dict[str, Any]:
        return {
            "bill_period": item.get("BillPeriod", ""),
            "payer_id": item.get("PayerID", ""),
            "payer_user_name": item.get("PayerUserName", ""),
            "payer_customer_name": item.get("PayerCustomerName", ""),
            "owner_id": item.get("OwnerID", ""),
            "owner_user_name": item.get("OwnerUserName", ""),
            "owner_customer_name": item.get("OwnerCustomerName", ""),
            "product": item.get("Product", ""),
            "product_zh": item.get("ProductZh", ""),
            "business_mode": item.get("BusinessMode", ""),
            "billing_mode": item.get("BillingMode", ""),
            "expense_begin_time": item.get("ExpenseBeginTime", ""),
            "expense_end_time": item.get("ExpenseEndTime", ""),
            "trade_time": item.get("TradeTime", ""),
            "bill_id": item.get("BillID", ""),
            "bill_category_parent": item.get("BillCategoryParent", ""),
            "original_bill_amount": item.get("OriginalBillAmount", ""),
            "preferential_bill_amount": item.get("PreferentialBillAmount", ""),
            "round_bill_amount": item.get("RoundBillAmount", ""),
            "discount_bill_amount": item.get("DiscountBillAmount", ""),
            "coupon_amount": item.get("CouponAmount", ""),
            "payable_amount": item.get("PayableAmount", ""),
            "paid_amount": item.get("PaidAmount", ""),
            "unpaid_amount": item.get("UnpaidAmount", ""),
            "currency": item.get("Currency", currency),
            "pay_status": item.get("PayStatus", ""),
            "raw": item,
            "amount": float(amount),
        }

    def get_balance(self) -> Optional[float]:
        """Get Volcengine available balance from QueryBalanceAcct."""
        try:
            payload = self._request_query_balance()
            metadata = payload.get("ResponseMetadata") or {}
            if metadata.get("Error") or payload.get("Error"):
                raise RuntimeError(self._extract_error(payload))

            result = self._extract_result_object(payload)
            container = result or payload
            available_balance = container.get("AvailableBalance")
            cash_balance = container.get("CashBalance")
            arrears_balance = container.get("ArrearsBalance")
            available_decimal = self._to_decimal(available_balance)

            self._last_balance_debug = {
                "status": "success",
                "available_balance": str(available_balance),
                "cash_balance": str(cash_balance),
                "arrears_balance": str(arrears_balance),
                "response_keys": list(container.keys()),
            }
            return float(available_decimal)
        except requests.HTTPError as exc:
            self._last_balance_debug = {
                "status": "http_error",
                "error_message": str(exc),
            }
            logger.warning("Volcengine balance HTTP error: %s", exc)
            return None
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            self._last_balance_debug = {
                "status": "error",
                "error_message": str(exc),
            }
            logger.warning("Volcengine balance error: %s", exc)
            return None
        except Exception as exc:
            self._last_balance_debug = {
                "status": "unexpected_error",
                "error_message": str(exc),
            }
            logger.warning("Unexpected Volcengine balance error: %s", exc)
            return None

    def get_billing_info(self, period: Optional[str] = None) -> Dict[str, Any]:
        try:
            data = self._collect_billing_data(self._normalize_period(period))
            balance = self.get_balance()
            data["balance"] = balance
            data["balance_debug"] = self._last_balance_debug
            return {"status": "success", "data": data, "error": None}
        except requests.HTTPError as exc:
            logger.error(f"Volcengine billing HTTP error: {exc}")
            return {"status": "error", "data": None, "error": str(exc)}
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            logger.error(f"Volcengine billing error: {exc}")
            return {"status": "error", "data": None, "error": str(exc)}
        except Exception as exc:
            logger.exception(f"Unexpected Volcengine billing error: {exc}")
            return {"status": "error", "data": None, "error": str(exc)}

    def _collect_billing_data(self, period: str) -> Dict[str, Any]:
        limit = DEFAULT_LIMIT
        all_items: List[Dict[str, Any]] = []
        total = 0
        currency = "CNY"
        service_costs: Dict[str, float] = {}
        account_id = self.config.payer_id or ""
        total_cost = Decimal("0")

        for offset in count(start=0, step=limit):
            payload = self._request_list_bill(
                period, limit=limit, offset=offset
            )
            metadata = payload.get("ResponseMetadata") or {}
            if metadata.get("Error") or payload.get("Error"):
                raise RuntimeError(self._extract_error(payload))

            items = self._extract_items(payload)
            if not items:
                if total == 0:
                    total = self._extract_total(payload, total)
                break

            (
                batch_total,
                batch_currency,
                batch_service_costs,
                batch_items,
                batch_account_id,
            ) = self._parse_bill_items(items)
            total_cost += batch_total
            currency = batch_currency or currency
            account_id = account_id or batch_account_id
            all_items.extend(batch_items)
            for name, value in batch_service_costs.items():
                service_costs[name] = service_costs.get(name, 0.0) + value

            total = self._extract_total(payload, total or len(all_items))
            if total and offset + len(items) >= total:
                break
            if len(items) < limit:
                break

        return {
            "total_cost": float(total_cost),
            "currency": currency,
            "account_id": account_id,
            "service_costs": service_costs,
            "items": all_items,
            "bill_period": period,
            "total_records": total or len(all_items),
        }

    def get_account_id(self) -> str:
        if self.config.payer_id:
            return self.config.payer_id
        try:
            result = self.get_billing_info()
            if result.get("status") == "success":
                data = result.get("data") or {}
                return str(data.get("account_id") or "")
        except Exception:
            logger.debug("Volcengine account ID lookup failed", exc_info=True)
        return ""

    def validate_credentials(self) -> bool:
        result = self.get_billing_info()
        return result.get("status") == "success"
