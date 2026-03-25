"""Huawei Cloud International provider implementation.

This module provides an implementation for Huawei Cloud International regions.
Uses huaweicloudsdkbssintl SDK with ListMonthlyExpendituresRequest API.

API Documentation:
https://support.huaweicloud.com/intl/en-us/api-bpconsole/mb_00002.html
"""

import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime

from huaweicloudsdkcore.auth.credentials import GlobalCredentials
from huaweicloudsdkbssintl.v2 import BssintlClient
from huaweicloudsdkbssintl.v2.region.bssintl_region import BssintlRegion
from huaweicloudsdkcore.exceptions import exceptions
import huaweicloudsdkbssintl.v2.model as model
from django.utils import timezone

from .provider import BaseCloudProvider, BaseCloudConfig


# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class HuaweiIntlConfig(BaseCloudConfig):
    """Huawei Cloud International provider configuration.

    Environment Variables:
        HUAWEI_INTL_ACCESS_KEY_ID: Huawei access key
        HUAWEI_INTL_SECRET_ACCESS_KEY: Huawei secret key
        HUAWEI_INTL_REGION: Huawei region (default: ap-southeast-1)
        HUAWEI_INTL_PROJECT_ID: Huawei project ID (optional)
    """
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    region: Optional[str] = None
    project_id: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3

    def __post_init__(self):
        """Initialize configuration from environment variables if not set."""
        if self.api_key is None:
            self.api_key = os.getenv("HUAWEI_INTL_ACCESS_KEY_ID")
        if self.api_secret is None:
            self.api_secret = os.getenv("HUAWEI_INTL_SECRET_ACCESS_KEY")
        if self.region is None:
            self.region = os.getenv("HUAWEI_INTL_REGION", "ap-southeast-1")
        if self.project_id is None:
            self.project_id = os.getenv("HUAWEI_INTL_PROJECT_ID")
        if self.timeout == 30:
            self.timeout = int(os.getenv("HUAWEI_INTL_TIMEOUT", "30"))
        if self.max_retries == 3:
            self.max_retries = int(os.getenv("HUAWEI_INTL_MAX_RETRIES", "3"))

        self._validate_config()

    def _validate_config(self):
        """Validate configuration parameters."""
        if not self.api_key:
            raise ValueError(
                "Huawei International access key is required. "
                "Set it via constructor or "
                "HUAWEI_INTL_ACCESS_KEY_ID environment variable."
            )
        if not self.api_secret:
            raise ValueError(
                "Huawei International secret key is required. "
                "Set it via constructor or "
                "HUAWEI_INTL_SECRET_ACCESS_KEY environment variable."
            )
        if not self.region:
            raise ValueError(
                "Huawei International region is required. "
                "Set it via constructor or "
                "HUAWEI_INTL_REGION environment variable."
            )
        if self.timeout <= 0:
            raise ValueError("Timeout must be greater than 0")
        if self.max_retries < 0:
            raise ValueError("Max retries must be non-negative")


class HuaweiIntlCloud(BaseCloudProvider):
    """Huawei Cloud International provider implementation."""

    def __init__(self, config: HuaweiIntlConfig):
        """Initialize Huawei Cloud International provider."""
        super().__init__(config)
        self._client = None
        self._last_balance_debug = {}
        self.name = "huawei-intl"
        logger.info(
            f"Initialized Huawei Cloud International provider: "
            f"region={config.region}"
        )

    @property
    def client(self):
        """Get Huawei BSS International client."""
        if self._client is None:
            credentials = GlobalCredentials(
                self.config.api_key,
                self.config.api_secret
            )
            self._client = BssintlClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(BssintlRegion.value_of(self.config.region)) \
                .build()
        return self._client

    def _convert_amount(self, amount: float, measure_id: int) -> float:
        """Convert amount based on measure_id (1: yuan, 3: fen)."""
        if measure_id == 3:
            return amount / 100
        return amount

    def _validate_period(self, period: Optional[str]) -> str:
        """Validate and return the billing period."""
        if period is None:
            period = timezone.now().strftime("%Y-%m")

        try:
            year, month = map(int, period.split("-"))
            if not (1 <= month <= 12):
                raise ValueError("Month must be between 1 and 12")
        except ValueError as e:
            raise ValueError(f"Invalid period format: {str(e)}")

        return period

    def _resolve_sdk_member(self, names: List[str]) -> Tuple[Any, str]:
        """Resolve the first available SDK attribute from candidate names."""
        for name in names:
            member = getattr(model, name, None)
            if member is not None:
                return member, name
        raise ImportError(
            "None of the SDK members were found in "
            "huaweicloudsdkbssintl.v2.model: "
            + ", ".join(names)
        )

    def _query_billing_api(self, period: str) -> Any:
        """Query the Huawei International billing API."""
        logger.debug(
            f"Querying Huawei International API: "
            f"region={self.config.region}, period={period}"
        )

        try:
            request_class, request_class_name = self._resolve_sdk_member([
                "ShowCustomerMonthlySumRequest",
                "ListMonthlyExpendituresRequest",
            ])
            request = request_class()
            if hasattr(request, "bill_cycle"):
                request.bill_cycle = period
            elif hasattr(request, "cycle"):
                request.cycle = period
            else:
                raise AttributeError(
                    f"Request class {request_class_name} has no supported "
                    "billing cycle field"
                )

            if hasattr(self.client, "show_customer_monthly_sum"):
                response = self.client.show_customer_monthly_sum(request)
            elif hasattr(self.client, "list_monthly_expenditures"):
                response = self.client.list_monthly_expenditures(request)
            else:
                raise AttributeError(
                    "Huawei International client has no supported billing "
                    "summary method"
                )

            if not hasattr(response, 'bill_sums'):
                raise ValueError(
                    "Invalid API response: missing 'bill_sums' attribute"
                )

            if not response.bill_sums:
                logger.warning(f"No billing data found for period: {period}")

            logger.debug(f"Retrieved {len(response.bill_sums)} bill items")
            return response

        except exceptions.ClientRequestException as e:
            error_code = getattr(e, 'error_code', 'Unknown')
            error_msg = getattr(e, 'error_msg', str(e))
            logger.error(
                f"Huawei International BSS API error "
                f"[{error_code}]: {error_msg}"
            )
            raise

    def _query_balance_api(self) -> Any:
        """Query the Huawei International balance API."""
        request_class, _ = self._resolve_sdk_member([
            "ShowCustomerAccountBalancesRequest",
        ])
        request = request_class()
        return self.client.show_customer_account_balances(request)

    def _calculate_total_cost(
        self, response: Any
    ) -> Tuple[float, str, Dict[str, float], List[Dict]]:
        """Calculate total cost from billing API response."""
        currency = getattr(response, 'currency', 'USD')
        total_cost = 0.0
        service_costs: Dict[str, float] = {}
        item_details: List[Dict] = []

        if not response.bill_sums:
            return total_cost, currency, service_costs, item_details

        for bill in response.bill_sums:
            try:
                measure_id = getattr(bill, 'measure_id', 3)
                consume_amount = getattr(bill, 'consume_amount', 0)
                amount = self._convert_amount(
                    float(consume_amount), measure_id
                )
                total_cost += amount

                service_type_name = getattr(
                    bill, 'service_type_name', 'Unknown'
                )
                resource_type_name = getattr(
                    bill, 'resource_type_name', 'Unknown'
                )
                service_name = f"{service_type_name} - {resource_type_name}"

                service_costs[service_name] = (
                    service_costs.get(service_name, 0.0) + amount
                )

                item_details.append({
                    "service_name": service_name,
                    "amount": amount,
                    "measure_id": measure_id
                })
            except (AttributeError, ValueError, TypeError) as e:
                logger.warning(f"Failed to process bill item: {e}, skipping")
                continue

        logger.info(
            f"Calculated total cost: {total_cost} {currency}, "
            f"services: {len(service_costs)}"
        )
        return total_cost, currency, service_costs, item_details

    def _calculate_balance(
        self, response: Any
    ) -> Tuple[Optional[float], Dict[str, Any]]:
        """Calculate credit balance from Huawei International response."""
        account_balances = getattr(response, "account_balances", None) or []
        selected_balance = None
        currency = getattr(response, "currency", "USD")
        measure_id = getattr(response, "measure_id", 1)
        debt_amount = getattr(response, "debt_amount", None)
        debug_items: List[Dict[str, Any]] = []

        for account in account_balances:
            account_type = getattr(account, "account_type", None)
            amount = getattr(account, "amount", None)
            account_currency = getattr(account, "currency", None) or currency
            account_measure_id = getattr(account, "measure_id", measure_id)
            converted_amount = None
            if amount is not None:
                converted_amount = self._convert_amount(
                    float(amount), account_measure_id
                )
            debug_items.append({
                "account_id": getattr(account, "account_id", ""),
                "account_type": account_type,
                "amount": amount,
                "converted_amount": converted_amount,
                "currency": account_currency,
                "designated_amount": getattr(
                    account, "designated_amount", None
                ),
                "credit_amount": getattr(account, "credit_amount", None),
                "measure_id": account_measure_id,
            })
            if account_type == 2:
                credit_amount = getattr(account, "credit_amount", None)
                if credit_amount is not None:
                    selected_balance = self._convert_amount(
                        float(credit_amount), account_measure_id
                    )
                elif amount is not None:
                    selected_balance = converted_amount
                currency = account_currency
                break

        return selected_balance, {
            "status": "success",
            "currency": currency,
            "measure_id": measure_id,
            "debt_amount": (
                self._convert_amount(float(debt_amount), measure_id)
                if debt_amount is not None else None
            ),
            "selected_account_type": 2 if selected_balance is not None else None,
            "balance_type": "credit_amount",
            "account_balances": debug_items,
        }

    def get_billing_info(
        self, period: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get Huawei International billing information for a period."""
        try:
            period = self._validate_period(period)
            response = self._query_billing_api(period)
            total_cost, currency, service_costs, item_details = (
                self._calculate_total_cost(response)
            )
            balance = None
            try:
                balance_response = self._query_balance_api()
                balance, balance_debug = self._calculate_balance(
                    balance_response
                )
                self._last_balance_debug = balance_debug
            except exceptions.ClientRequestException as e:
                self._last_balance_debug = {
                    "status": "client_error",
                    "error_code": getattr(e, "error_code", "Unknown"),
                    "error_msg": getattr(e, "error_msg", str(e)),
                }
                logger.warning(
                    "Huawei International balance lookup failed [%s]: %s",
                    getattr(e, "error_code", "Unknown"),
                    getattr(e, "error_msg", str(e)),
                )
            except Exception as e:
                self._last_balance_debug = {
                    "status": "unexpected_error",
                    "error_msg": str(e),
                }
                logger.warning(
                    "Huawei International balance lookup failed: %s", e
                )
            account_id = self.get_account_id()

            data = {
                "total_cost": total_cost,
                "balance": balance,
                "balance_debug": self._last_balance_debug,
                "currency": currency,
                "account_id": account_id,
                "service_costs": service_costs,
                "items": item_details
            }

            logger.info(f"Huawei International billing data: {data}")

            return {
                "status": "success",
                "data": data,
                "error": None
            }

        except exceptions.ClientRequestException as e:
            error_code = getattr(e, 'error_code', 'Unknown')
            error_msg = getattr(e, 'error_msg', str(e))
            status_code = getattr(e, 'status_code', 'Unknown')
            request_id = getattr(e, 'request_id', 'Unknown')

            error_message = (
                f"Huawei International API Error: {error_code} - {error_msg}\n"
                f"Status Code: {status_code}\n"
                f"Request ID: {request_id}\n"
                f"Region: {self.config.region}"
            )
            logger.error(f"{error_message}")
            logger.exception(e)
            return {
                "status": "error",
                "data": None,
                "error": error_message
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"Unexpected error in Huawei International billing: "
                f"{error_msg}"
            )
            logger.exception(e)
            return {
                "status": "error",
                "data": None,
                "error": error_msg
            }

    def get_account_id(self) -> str:
        """Get Huawei International project ID."""
        return self.config.project_id or "default"

    def validate_credentials(self) -> bool:
        """Validate Huawei International credentials."""
        try:
            result = self.get_billing_info()
            is_valid = result["status"] == "success"
            if is_valid:
                logger.info(
                    f"Huawei International credentials validated: "
                    f"region={self.config.region}"
                )
            else:
                logger.warning(
                    f"Huawei International credentials validation failed: "
                    f"{result.get('error')}"
                )
            return is_valid
        except Exception as e:
            logger.error(
                f"Failed to validate Huawei International credentials: "
                f"{str(e)}"
            )
            logger.exception(e)
            return False
