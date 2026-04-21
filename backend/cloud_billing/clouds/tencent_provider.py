"""Tencent Cloud provider implementation.

This module provides Tencent Cloud billing collection using the
tencentcloud-sdk-python-billing package. Authentication is validated through
the DescribeAccountBalance API.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from tencentcloud.billing.v20180709 import billing_client
from tencentcloud.billing.v20180709 import models as billing_models
from tencentcloud.common.credential import Credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
    TencentCloudSDKException,
)
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile

from ..utils.logging import mask_sensitive_config_object
from .provider import BaseCloudConfig, BaseCloudProvider


logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "billing.tencentcloudapi.com"
DEFAULT_REGION = "ap-guangzhou"
DEFAULT_HTTP_TIMEOUT = 60
DEFAULT_SUMMARY_GROUP_TYPE = "business"
DEFAULT_CURRENCY = "CNY"
BALANCE_CENT_DIVISOR = Decimal("100")


@dataclass
class TencentConfig(BaseCloudConfig):
    """Tencent Cloud provider configuration."""

    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    app_id: Optional[str] = None
    endpoint: Optional[str] = None

    def __post_init__(self):
        """Load unset values from environment variables."""
        if self.access_key_id is None:
            self.access_key_id = os.getenv("TENCENT_ACCESS_KEY_ID")
        if self.access_key_secret is None:
            self.access_key_secret = os.getenv("TENCENT_ACCESS_KEY_SECRET")
        if self.app_id is None:
            self.app_id = os.getenv("TENCENT_APP_ID")
        if self.region is None:
            self.region = os.getenv("TENCENT_REGION", DEFAULT_REGION)
        if self.endpoint is None:
            self.endpoint = os.getenv("TENCENT_ENDPOINT", DEFAULT_ENDPOINT)
        if self.timeout == 30:
            self.timeout = int(os.getenv("TENCENT_TIMEOUT", "30"))
        if self.max_retries == 3:
            self.max_retries = int(os.getenv("TENCENT_MAX_RETRIES", "3"))
        self._validate_config()

    def _validate_config(self):
        """Validate required parameters."""
        if not self.access_key_id:
            raise ValueError(
                "Tencent access_key_id is required. Set it via constructor or "
                "TENCENT_ACCESS_KEY_ID environment variable."
            )
        if not self.access_key_secret:
            raise ValueError(
                "Tencent access_key_secret is required. Set it via "
                "constructor or TENCENT_ACCESS_KEY_SECRET environment "
                "variable."
            )
        if not self.app_id:
            raise ValueError(
                "Tencent app_id is required. Set it via constructor or "
                "TENCENT_APP_ID environment variable."
            )
        if self.timeout <= 0:
            raise ValueError("Timeout must be greater than 0")
        if self.max_retries < 0:
            raise ValueError("Max retries must be non-negative")


class TencentCloud(BaseCloudProvider):
    """Tencent Cloud provider implementation."""

    def __init__(self, config: TencentConfig):
        """Initialize Tencent Cloud provider.

        Args:
            config: Tencent configuration.
        """
        super().__init__(config)
        self._client = None
        self._last_balance_debug = {}
        self.name = "tencentcloud"
        sanitized = mask_sensitive_config_object(config)
        logger.info(
            f"Initialized Tencent Cloud provider with config: {sanitized}"
        )

    @staticmethod
    def _normalize_period(period: Optional[str]) -> str:
        """Normalize a billing period to YYYY-MM."""
        if not period:
            period = datetime.now().strftime("%Y-%m")
        try:
            datetime.strptime(period, "%Y-%m")
        except ValueError as exc:
            raise ValueError("Invalid period format. Use YYYY-MM") from exc
        return period

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        """Convert a raw value to Decimal, defaulting to zero."""
        try:
            if value is None or value == "":
                return Decimal("0")
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    def _parse_balance_amount(self, value: Any) -> Decimal:
        """Convert Tencent balance fields from cents to yuan."""
        amount = self._to_decimal(value)
        if amount == Decimal("0"):
            return amount
        return (amount / BALANCE_CENT_DIVISOR).quantize(
            Decimal("0.01")
        )

    def _build_client(self):
        """Create a Tencent billing client."""
        credential = Credential(
            self.config.access_key_id,
            self.config.access_key_secret,
        )
        http_profile = HttpProfile(
            endpoint=self.config.endpoint or DEFAULT_ENDPOINT,
            reqTimeout=self.config.timeout or DEFAULT_HTTP_TIMEOUT,
        )
        client_profile = ClientProfile(httpProfile=http_profile)
        return billing_client.BillingClient(
            credential,
            self.config.region or DEFAULT_REGION,
            client_profile,
        )

    @property
    def client(self):
        """Lazily create and cache the Tencent billing client."""
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _describe_account_balance(self) -> Any:
        """Call DescribeAccountBalance to validate credentials."""
        request = billing_models.DescribeAccountBalanceRequest()
        return self.client.DescribeAccountBalance(request)

    def get_balance(self) -> Optional[float]:
        """Get Tencent Cloud balance from DescribeAccountBalance."""
        try:
            response = self._describe_account_balance()
            available_balance = getattr(response, "AvailableBalance", None)
            if available_balance is None:
                available_balance = getattr(response, "Balance", None)
            balance_decimal = self._parse_balance_amount(available_balance)
            balance = float(balance_decimal)
            self._last_balance_debug = {
                "status": "success",
                "uin": getattr(response, "Uin", None),
                "available_balance_raw": available_balance,
                "available_balance": str(balance_decimal),
                "balance_raw": getattr(response, "Balance", None),
                "credit_balance_raw": getattr(
                    response, "CreditBalance", None
                ),
                "unit": "yuan_from_cent",
            }
            return balance
        except TencentCloudSDKException as exc:
            self._last_balance_debug = {
                "status": "client_error",
                "error_code": getattr(exc, "code", ""),
                "error_message": str(exc),
            }
            logger.warning(
                "Tencent balance lookup failed: %s",
                exc,
            )
            return None
        except Exception as exc:
            self._last_balance_debug = {
                "status": "unexpected_error",
                "error_message": str(exc),
            }
            logger.warning("Tencent balance lookup failed: %s", exc)
            return None

    def validate_credentials(self) -> bool:
        """Validate Tencent credentials by calling the billing API."""
        try:
            self._describe_account_balance()
            logger.info(
                "Tencent credentials validated successfully "
                f"(region={self.config.region or DEFAULT_REGION})"
            )
            return True
        except TencentCloudSDKException as exc:
            logger.warning(
                f"Tencent credentials validation failed: {exc}"
            )
            return False
        except Exception as exc:
            logger.exception(
                f"Failed to validate Tencent credentials: {exc}"
            )
            return False

    def get_account_id(self) -> str:
        """Return the Tencent Uin when available."""
        try:
            response = self._describe_account_balance()
        except Exception as exc:
            logger.debug(
                f"Could not get Uin from DescribeAccountBalance: {exc}"
            )
            return ""

        uin = getattr(response, "Uin", None)
        if uin is None:
            return ""
        return str(uin)

    def _query_bill_summary(
        self,
        period: str,
    ) -> Tuple[Decimal, Dict[str, float], List[Dict[str, Any]]]:
        """Query DescribeBillSummary for the given month."""
        request = billing_models.DescribeBillSummaryRequest()
        request.Month = period
        request.GroupType = DEFAULT_SUMMARY_GROUP_TYPE
        response = self.client.DescribeBillSummary(request)

        ready = getattr(response, "Ready", 0)
        if not ready:
            raise TencentCloudSDKException(
                "SummaryDataNotReady",
                "Tencent bill summary data is not ready yet.",
            )

        total_cost = Decimal("0")
        service_costs: Dict[str, float] = {}
        items: List[Dict[str, Any]] = []
        summary_detail = getattr(response, "SummaryDetail", None) or []

        for detail in summary_detail:
            cost = self._to_decimal(
                getattr(detail, "RealTotalCost", None)
                or getattr(detail, "TotalCost", None)
                or getattr(detail, "CashPayAmount", None)
                or "0"
            )
            total_cost += cost
            name = (
                getattr(detail, "GroupValue", None)
                or getattr(detail, "BusinessCodeName", None)
                or getattr(detail, "ProductCodeName", None)
                or "Unknown"
            )
            service_costs[name] = service_costs.get(name, 0.0) + float(cost)
            items.append({"service_name": name, "amount": float(cost)})

        return total_cost, service_costs, items

    def get_billing_info(self, period: Optional[str] = None) -> Dict[str, Any]:
        """Get billing information for a specific month."""
        try:
            period = self._normalize_period(period)
            total_cost, service_costs, items = self._query_bill_summary(period)
            balance = self.get_balance()
            account_id = self.get_account_id()
            currency = DEFAULT_CURRENCY
            data = {
                "total_cost": float(total_cost),
                "balance": balance,
                "balance_debug": self._last_balance_debug,
                "currency": currency,
                "account_id": account_id,
                "service_costs": service_costs,
                "items": items,
                "bill_period": period,
            }
            return {"status": "success", "data": data, "error": None}
        except TencentCloudSDKException as exc:
            logger.warning(f"Tencent bill summary query failed: {exc}")
            return {"status": "error", "data": None, "error": str(exc)}
        except Exception as exc:
            logger.exception(f"Unexpected error in Tencent billing: {exc}")
            return {"status": "error", "data": None, "error": str(exc)}
