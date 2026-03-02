"""Tencent Cloud provider implementation.

This module provides an implementation for Tencent Cloud using
tencentcloud-sdk-python-billing. Authentication is validated via
DescribeAccountBalance API.

API Documentation:
https://cloud.tencent.com/document/product/555/50284

Config fields (DB / API): access_key_id, access_key_secret, app_id.
Tencent SDK uses SecretId (= access_key_id) and SecretKey (= access_key_secret).
"""

import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional, Any

from tencentcloud.common.credential import Credential
from tencentcloud.billing.v20180709 import billing_client
from tencentcloud.billing.v20180709 import models as billing_models
from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
    TencentCloudSDKException,
)

from ..utils.logging import mask_sensitive_config_object
from .provider import BaseCloudProvider, BaseCloudConfig


logger = logging.getLogger(__name__)

# Default region for billing API (billing.tencentcloudapi.com is region-agnostic)
DEFAULT_REGION = "ap-guangzhou"


@dataclass
class TencentConfig(BaseCloudConfig):
    """Tencent Cloud provider configuration.

    Config keys: access_key_id (SecretId), access_key_secret (SecretKey), app_id.
    Inherits region, timeout, max_retries from BaseCloudConfig.
    """

    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    app_id: Optional[str] = None

    def __post_init__(self):
        """Initialize from environment if not set."""
        if self.access_key_id is None:
            self.access_key_id = os.getenv("TENCENT_ACCESS_KEY_ID")
        if self.access_key_secret is None:
            self.access_key_secret = os.getenv("TENCENT_ACCESS_KEY_SECRET")
        if self.app_id is None:
            self.app_id = os.getenv("TENCENT_APP_ID")
        if self.region is None:
            self.region = os.getenv("TENCENT_REGION", DEFAULT_REGION)
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
                "Tencent access_key_secret is required. Set it via constructor or "
                "TENCENT_ACCESS_KEY_SECRET environment variable."
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
            config: Tencent configuration (access_key_id, access_key_secret, app_id)
        """
        super().__init__(config)
        self._client = None
        self.name = "tencentcloud"
        sanitized = mask_sensitive_config_object(config)
        logger.info("Initialized Tencent Cloud provider with config: %s", sanitized)

    @property
    def client(self):
        """Get Tencent Billing client."""
        if self._client is None:
            cred = Credential(
                self.config.access_key_id,
                self.config.access_key_secret,
            )
            self._client = billing_client.BillingClient(cred, self.config.region or DEFAULT_REGION)
        return self._client

    def _describe_account_balance(self) -> Any:
        """Call DescribeAccountBalance to validate credentials and get account info."""
        req = billing_models.DescribeAccountBalanceRequest()
        return self.client.DescribeAccountBalance(req)

    def validate_credentials(self) -> bool:
        """Validate Tencent credentials by calling billing API.

        Returns:
            True if credentials are valid, False otherwise.
        """
        try:
            self._describe_account_balance()
            logger.info(
                "Tencent credentials validated successfully (region=%s)",
                self.config.region or DEFAULT_REGION,
            )
            return True
        except TencentCloudSDKException as e:
            logger.warning(
                "Tencent credentials validation failed: %s",
                str(e),
            )
            return False
        except Exception as e:
            logger.error("Failed to validate Tencent credentials: %s", str(e))
            logger.exception(e)
            return False

    def get_account_id(self) -> str:
        """Get account identifier: Uin from API or app_id from config."""
        try:
            resp = self._describe_account_balance()
            uin = getattr(resp, "Uin", None)
            if uin is not None:
                return str(uin)
        except Exception as e:
            logger.debug("Could not get Uin from DescribeAccountBalance: %s", e)
        return self.config.app_id or ""

    def _query_bill_resource_summary(self, period: str) -> tuple:
        """Query DescribeBillResourceSummary for month, return (total_cost_yuan, service_costs, items)."""
        total_cost = 0.0
        service_costs: Dict[str, float] = {}
        items: list = []
        offset = 0
        limit = 1000
        need_record_num = 1

        while True:
            req = billing_models.DescribeBillResourceSummaryRequest()
            req.Month = period
            req.Offset = offset
            req.Limit = limit
            req.NeedRecordNum = need_record_num
            resp = self.client.DescribeBillResourceSummary(req)
            summary_set = getattr(resp, "ResourceSummarySet", None) or []
            for item in summary_set:
                cost_str = getattr(item, "RealTotalCost", None) or getattr(item, "TotalCost", None) or "0"
                try:
                    cost = float(cost_str)
                except (TypeError, ValueError):
                    cost = 0.0
                total_cost += cost
                name = getattr(item, "BusinessCodeName", None) or getattr(item, "ProductCodeName", None) or "Unknown"
                service_costs[name] = service_costs.get(name, 0.0) + cost
                items.append({"service_name": name, "amount": cost})
            total_count = getattr(resp, "Total", 0) or 0
            if not summary_set or offset + len(summary_set) >= total_count:
                break
            offset += limit
            need_record_num = 0  # only first page needs total count

        return total_cost, service_costs, items

    def get_billing_info(self, period: Optional[str] = None) -> Dict[str, Any]:
        """Get billing information for a period.

        Uses DescribeBillResourceSummary for monthly cost; falls back to
        DescribeAccountBalance (balance only, total_cost=0) if bill API fails.

        Args:
            period: Optional YYYY-MM; defaults to current month.

        Returns:
            Dict with status, data (total_cost, currency, account_id, service_costs, items), error.
        """
        from datetime import datetime
        if not period:
            period = datetime.now().strftime("%Y-%m")
        try:
            year, month = period.split("-")
            if not (1 <= int(month) <= 12):
                raise ValueError("Invalid period month")
        except (ValueError, AttributeError):
            period = datetime.now().strftime("%Y-%m")

        account_id = self.get_account_id()
        currency = "CNY"

        try:
            total_cost, service_costs, items = self._query_bill_resource_summary(period)
            data = {
                "total_cost": total_cost,
                "currency": currency,
                "account_id": account_id,
                "service_costs": service_costs,
                "items": items,
            }
            return {
                "status": "success",
                "data": data,
                "error": None,
            }
        except TencentCloudSDKException as e:
            code = getattr(e, "code", "") or ""
            if "CamNoAuth" in code or "UnauthorizedOperation" in code or "NoAuth" in str(e):
                logger.warning(
                    "Tencent DescribeBillResourceSummary not authorized, returning balance only: %s",
                    e,
                )
            else:
                logger.error("Tencent Billing API error: %s", e)
                return {
                    "status": "error",
                    "data": None,
                    "error": str(e),
                }
            try:
                resp = self._describe_account_balance()
                balance_cents = getattr(resp, "RealBalance", 0) or getattr(resp, "Balance", 0)
                try:
                    balance_yuan = float(balance_cents) / 100.0
                except (TypeError, ValueError):
                    balance_yuan = 0.0
                data = {
                    "total_cost": 0.0,
                    "currency": currency,
                    "account_id": account_id,
                    "service_costs": {},
                    "items": [],
                    "balance_yuan": balance_yuan,
                }
                return {"status": "success", "data": data, "error": None}
            except Exception as fallback_e:
                logger.error("Tencent fallback balance error: %s", fallback_e)
                return {"status": "error", "data": None, "error": str(e)}
        except Exception as e:
            logger.error("Unexpected error in Tencent billing: %s", str(e))
            logger.exception(e)
            return {
                "status": "error",
                "data": None,
                "error": str(e),
            }
