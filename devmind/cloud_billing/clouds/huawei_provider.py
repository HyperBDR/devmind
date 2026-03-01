"""Huawei Cloud Domestic (China) provider implementation.

This module provides an implementation for Huawei Cloud domestic
regions (China). Uses huaweicloudsdkbss SDK with
ShowCustomerMonthlySumRequest API.

API Documentation:
https://support.huaweicloud.com/api-bss/bss_01_0006.html

Note: For international regions, use huawei_intl_provider instead.
"""

import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime

from huaweicloudsdkcore.auth.credentials import GlobalCredentials
from huaweicloudsdkbss.v2 import BssClient
from huaweicloudsdkbss.v2.region.bss_region import BssRegion
from huaweicloudsdkbss.v2.model import ShowCustomerMonthlySumRequest
from huaweicloudsdkcore.exceptions import exceptions
from django.utils import timezone

from ..utils.logging import mask_sensitive_config_object
from .provider import BaseCloudProvider, BaseCloudConfig


# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class HuaweiConfig(BaseCloudConfig):
    """Huawei cloud provider configuration.

    This configuration class extends the base CloudConfig and adds
    Huawei-specific configuration options. If values are not provided,
    they will be read from environment variables.

    Environment Variables:
        HUAWEI_ACCESS_KEY_ID: Huawei access key
        HUAWEI_SECRET_ACCESS_KEY: Huawei secret key
        HUAWEI_REGION: Huawei region (default: cn-north-1)
        HUAWEI_PROJECT_ID: Huawei project ID (optional)
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
            self.api_key = os.getenv("HUAWEI_ACCESS_KEY_ID")
        if self.api_secret is None:
            self.api_secret = os.getenv("HUAWEI_SECRET_ACCESS_KEY")
        if self.region is None:
            self.region = os.getenv("HUAWEI_REGION", "cn-north-1")
        if self.project_id is None:
            self.project_id = os.getenv("HUAWEI_PROJECT_ID")
        if self.timeout == 30:
            self.timeout = int(os.getenv("HUAWEI_TIMEOUT", "30"))
        if self.max_retries == 3:
            self.max_retries = int(os.getenv("HUAWEI_MAX_RETRIES", "3"))

        self._validate_config()

    def _validate_config(self):
        """Validate configuration parameters.

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        if not self.api_key:
            raise ValueError(
                "Huawei access key is required. Set it via constructor or "
                "HUAWEI_ACCESS_KEY_ID environment variable."
            )

        if not self.api_secret:
            raise ValueError(
                "Huawei secret key is required. Set it via constructor or "
                "HUAWEI_SECRET_ACCESS_KEY environment variable."
            )

        if not self.region:
            raise ValueError(
                "Huawei region is required. Set it via constructor or "
                "HUAWEI_REGION environment variable."
            )

        if self.timeout <= 0:
            raise ValueError("Timeout must be greater than 0")

        if self.max_retries < 0:
            raise ValueError("Max retries must be non-negative")


class HuaweiCloud(BaseCloudProvider):
    """Huawei cloud provider implementation."""

    def __init__(self, config: HuaweiConfig):
        """Initialize Huawei cloud provider.

        Args:
            config (HuaweiConfig): Huawei configuration

        Raises:
            ValueError: If configuration is invalid
        """
        super().__init__(config)
        self._client = None
        self.name = "huawei"
        sanitized_config = mask_sensitive_config_object(config)
        logger.info(
            f"Initialized Huawei Cloud provider with config: "
            f"{sanitized_config}"
        )

    @property
    def client(self):
        """Get Huawei BSS client."""
        if self._client is None:
            credentials = GlobalCredentials(
                self.config.api_key,
                self.config.api_secret
            )
            self._client = BssClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(BssRegion.value_of(self.config.region)) \
                .build()
        return self._client

    def _convert_amount(self, amount: float, measure_id: int) -> float:
        """Convert amount based on measure_id.

        Args:
            amount (float): Original amount
            measure_id (int): Amount unit (1: yuan, 3: fen)

        Returns:
            float: Converted amount in yuan
        """
        # Convert fen to yuan
        if measure_id == 3:
            return amount / 100
        return amount

    def _validate_period(self, period: Optional[str]) -> str:
        """Validate and return the billing period.

        Args:
            period (Optional[str]): Period in YYYY-MM format

        Returns:
            str: Validated period

        Raises:
            ValueError: If period format is invalid
        """
        if period is None:
            period = timezone.now().strftime("%Y-%m")

        logger.info(f"Getting billing info for period: {period}")

        try:
            year, month = map(int, period.split("-"))
            if not (1 <= month <= 12):
                raise ValueError("Month must be between 1 and 12")
        except ValueError as e:
            raise ValueError(f"Invalid period format: {str(e)}")

        return period

    def _query_billing_api(self, period: str) -> Any:
        """Query the Huawei domestic billing API.

        Args:
            period (str): Period in YYYY-MM format

        Returns:
            Any: API response object with bill_sums attribute

        Raises:
            exceptions.ClientRequestException: If API request fails
            ValueError: If response format is invalid
        """
        logger.debug(
            f"Querying Huawei domestic API: "
            f"region={self.config.region}, period={period}"
        )

        try:
            request = ShowCustomerMonthlySumRequest()
            request.bill_cycle = period
            response = self.client.show_customer_monthly_sum(request)

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
            logger.error(f"Huawei BSS API error [{error_code}]: {error_msg}")
            raise

    def _calculate_total_cost(
        self, response: Any
    ) -> Tuple[float, str, Dict[str, float], List[Dict]]:
        """Calculate total cost from billing API response.

        Args:
            response (Any): API response object

        Returns:
            Tuple[float, str, Dict[str, float], List[Dict]]: Total cost,
            currency, service costs breakdown, and item details
        """
        currency = getattr(response, 'currency', 'CNY')
        logger.debug(f"Currency from response: {currency}")

        total_cost = 0.0
        service_costs: Dict[str, float] = {}
        item_details: List[Dict] = []

        if not response.bill_sums:
            logger.warning("No bill sums found in response")
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

                logger.debug(
                    f"Processed bill: service={service_name}, "
                    f"amount={amount}, measure_id={measure_id}"
                )
            except (AttributeError, ValueError, TypeError) as e:
                logger.warning(
                    f"Failed to process bill item: {e}, skipping"
                )
                continue

        logger.info(
            f"Calculated total cost: {total_cost} {currency}, "
            f"services: {len(service_costs)}"
        )

        return total_cost, currency, service_costs, item_details

    def get_billing_info(
        self, period: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get Huawei billing information for a specific period.

        Args:
            period (Optional[str]): Period in YYYY-MM format. Defaults to
                current month if not specified.

        Returns:
            Dict[str, Any]: Dictionary containing billing information
                in the following format:
                {
                    "status": "success" | "error",
                    "data": {
                        "total_cost": float,
                        "currency": str,
                        "account_id": str,
                        "items": List[Dict]
                    } | None,
                    "error": str | None
                }
        """
        try:
            # Validate and get billing period
            period = self._validate_period(period)

            # Query billing API
            response = self._query_billing_api(period)

            # Calculate total cost, service costs, and item details
            total_cost, currency, service_costs, item_details = (
                self._calculate_total_cost(response)
            )

            # Get account ID
            account_id = self.get_account_id()

            # Build response data
            data = {
                "total_cost": total_cost,
                "currency": currency,
                "account_id": account_id,
                "service_costs": service_costs,
                "items": item_details
            }

            logger.info(f"Huawei billing data: {data}")

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
                f"Huawei API Error: {error_code} - {error_msg}\n"
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
            logger.error(f"Unexpected error in Huawei billing: {error_msg}")
            logger.exception(e)
            return {
                "status": "error",
                "data": None,
                "error": error_msg
            }

    def get_account_id(self) -> str:
        """Get Huawei project ID.

        Returns:
            str: Huawei project ID or 'default' if not set
        """
        return self.config.project_id or "default"

    def validate_credentials(self) -> bool:
        """Validate Huawei credentials.

        Returns:
            bool: True if credentials are valid, False otherwise
        """
        try:
            # Try to get billing info for current month
            result = self.get_billing_info()
            is_valid = result["status"] == "success"
            if is_valid:
                logger.info(
                    f"Huawei credentials validated successfully "
                    f"(region={self.config.region})"
                )
            else:
                logger.warning(
                    f"Huawei credentials validation failed: "
                    f"{result.get('error', 'Unknown error')}"
                )
            return is_valid
        except Exception as e:
            logger.error(
                f"Failed to validate Huawei credentials: {str(e)}"
            )
            logger.exception(e)
            return False
