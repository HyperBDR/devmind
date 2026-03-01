"""Alibaba Cloud provider implementation.

This module provides an implementation of the Cloud interface for Alibaba
Cloud.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Tuple

from alibabacloud_bssopenapi20171214.client import Client
from alibabacloud_tea_openapi.models import Config
from alibabacloud_bssopenapi20171214 import models as bss_models
from django.utils import timezone

from .provider import BaseCloudConfig, BaseCloudProvider


# Configure logging
logger = logging.getLogger(__name__)


class AlibabaConfig(BaseCloudConfig):
    """Alibaba Cloud configuration."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        region: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = 3
    ):
        """Initialize Alibaba Cloud configuration.

        Args:
            api_key (Optional[str]): Alibaba Cloud access key ID
            api_secret (Optional[str]): Alibaba Cloud access key secret
            region (Optional[str]): Alibaba Cloud region
            timeout (int): Request timeout in seconds
            max_retries (int): Maximum number of retries for failed requests
        """
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.region = region
        self.timeout = timeout
        self.max_retries = max_retries
        self._post_init()

    def _post_init(self):
        """Post initialization configuration."""
        # Set values from environment variables if not provided
        if self.api_key is None:
            self.api_key = os.environ.get("ALIBABA_ACCESS_KEY_ID")
        if self.api_secret is None:
            self.api_secret = os.environ.get("ALIBABA_ACCESS_KEY_SECRET")
        if self.region is None:
            self.region = os.environ.get("ALIBABA_REGION")

        # Validate required fields
        if not self.api_key:
            raise ValueError("access key ID is required")
        if not self.api_secret:
            raise ValueError("access key secret is required")
        if not self.region:
            raise ValueError("region is required")


class AlibabaCloud(BaseCloudProvider):
    """Alibaba Cloud provider implementation."""

    def __init__(self, config: AlibabaConfig):
        """Initialize Alibaba Cloud provider.

        Args:
            config (AlibabaConfig): Alibaba Cloud configuration
        """
        super().__init__(config)
        self._client = None
        self.name = "alibaba"

    @property
    def client(self) -> Client:
        """Get Alibaba Cloud BSS client."""
        if self._client is None:
            config = Config(
                access_key_id=self.config.api_key,
                access_key_secret=self.config.api_secret,
                endpoint=(
                    f"bssopenapi.{self.config.region}.aliyuncs.com"
                )
            )
            self._client = Client(config)
        return self._client

    def _validate_period(self, period: Optional[str] = None) -> str:
        """Validate and format billing period.

        Args:
            period (Optional[str]): Billing period in YYYY-MM format

        Returns:
            str: Validated billing period

        Raises:
            ValueError: If period format is invalid
        """
        if period is None:
            period = timezone.now().strftime("%Y-%m")

        try:
            datetime.strptime(period, "%Y-%m")
        except ValueError:
            raise ValueError("Invalid period format. Use YYYY-MM")

        year, month = map(int, period.split("-"))
        if not 1 <= month <= 12:
            raise ValueError("Month must be between 1 and 12")

        return period

    def _get_period_dates(self, period: str) -> Tuple[str, str]:
        """Get start and end dates for a billing period.

        Args:
            period (str): Billing period in YYYY-MM format

        Returns:
            Tuple[str, str]: Start and end dates in YYYY-MM-DD format
        """
        year, month = map(int, period.split("-"))
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(days=1)

        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    def _query_billing_api(
        self, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """Query the Alibaba Cloud BSS API.

        Args:
            start_date (str): Start date in YYYY-MM-DD format
            end_date (str): End date in YYYY-MM-DD format

        Returns:
            Dict[str, Any]: API response containing cost and usage data
        """
        logger.debug(
            f"Using Alibaba Cloud configuration: region={self.config.region}"
        )

        # Extract YYYY-MM from start_date
        billing_cycle = start_date[:7]
        request = bss_models.QueryBillRequest(
            billing_cycle=billing_cycle,
            granularity="DAILY"
        )
        return self.client.query_bill(request)

    def _calculate_total_cost(
        self, response: Dict[str, Any]
    ) -> Tuple[float, str]:
        """Calculate total cost from API response.

        Args:
            response (Dict[str, Any]): API response

        Returns:
            Tuple[float, str]: Total cost and currency
        """
        total_cost = float(response.body.data.total_amount)
        currency = response.body.data.currency
        return total_cost, currency

    def get_billing_info(
        self, period: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get billing information for a period.

        Args:
            period (Optional[str]): Billing period in YYYY-MM format

        Returns:
            Dict[str, Any]: Billing information
        """
        try:
            period = self._validate_period(period)
            start_date, end_date = self._get_period_dates(period)

            response = self._query_billing_api(start_date, end_date)
            total_cost, currency = self._calculate_total_cost(response)
            account_id = self.get_account_id()

            return {
                "status": "success",
                "data": {
                    "total_cost": total_cost,
                    "currency": currency,
                    "account_id": account_id
                },
                "error": None
            }
        except Exception as e:
            logger.error(f"Failed to get billing info: {str(e)}")
            return {
                "status": "error",
                "data": None,
                "error": str(e)
            }

    def get_account_id(self) -> str:
        """Get the Alibaba Cloud account ID.

        Returns:
            str: Alibaba Cloud account ID

        Raises:
            Exception: If the account ID cannot be retrieved
        """
        try:
            request = bss_models.GetResourcePackageRequest()
            response = self.client.get_resource_package(request)
            return response.body.data.owner_id
        except Exception as e:
            logger.error(f"Failed to get account ID: {str(e)}")
            raise

    def validate_credentials(self) -> bool:
        """Validate Alibaba Cloud credentials.

        Returns:
            bool: True if credentials are valid, False otherwise
        """
        try:
            self.get_account_id()
            return True
        except Exception as e:
            logger.error(f"Failed to validate credentials: {str(e)}")
            return False
