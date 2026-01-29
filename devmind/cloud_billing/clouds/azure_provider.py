"""Azure cloud provider implementation.

This module provides an implementation of the Cloud interface for Azure.
"""

import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional, Any, Tuple
from datetime import datetime, timedelta

from azure.identity import ClientSecretCredential
from azure.mgmt.consumption import ConsumptionManagementClient
from azure.mgmt.resource import ResourceManagementClient

from ..utils.logging import mask_sensitive_config_object
from .provider import BaseCloudProvider, BaseCloudConfig


# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class AzureConfig(BaseCloudConfig):
    """Azure cloud provider configuration.

    This configuration class extends the base CloudConfig and adds
    Azure-specific configuration options. If values are not provided,
    they will be read from environment variables.

    Environment Variables:
        AZURE_TENANT_ID: Azure tenant ID
        AZURE_CLIENT_ID: Azure client ID
        AZURE_CLIENT_SECRET: Azure client secret
        AZURE_SUBSCRIPTION_ID: Azure subscription ID
        AZURE_TIMEOUT: Request timeout in seconds
        AZURE_MAX_RETRIES: Maximum number of retries for failed requests
    """
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    subscription_id: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3

    def __post_init__(self):
        """Initialize configuration from environment variables if not set."""
        if self.tenant_id is None:
            self.tenant_id = os.getenv("AZURE_TENANT_ID")
        if self.client_id is None:
            self.client_id = os.getenv("AZURE_CLIENT_ID")
        if self.client_secret is None:
            self.client_secret = os.getenv("AZURE_CLIENT_SECRET")
        if self.subscription_id is None:
            self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        if self.timeout == 30:
            self.timeout = int(os.getenv("AZURE_TIMEOUT", "30"))
        if self.max_retries == 3:
            self.max_retries = int(os.getenv("AZURE_MAX_RETRIES", "3"))

        self._validate_config()

    def _validate_config(self):
        """Validate configuration parameters.

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        if not self.tenant_id:
            raise ValueError(
                "Azure tenant ID is required. Set it via constructor or "
                "AZURE_TENANT_ID environment variable."
            )

        if not self.client_id:
            raise ValueError(
                "Azure client ID is required. Set it via constructor or "
                "AZURE_CLIENT_ID environment variable."
            )

        if not self.client_secret:
            raise ValueError(
                "Azure client secret is required. Set it via constructor or "
                "AZURE_CLIENT_SECRET environment variable."
            )

        if not self.subscription_id:
            raise ValueError(
                "Azure subscription ID is required. Set it via constructor or "
                "AZURE_SUBSCRIPTION_ID environment variable."
            )

        if self.timeout <= 0:
            raise ValueError("Timeout must be greater than 0")

        if self.max_retries < 0:
            raise ValueError("Max retries must be non-negative")


class AzureCloud(BaseCloudProvider):
    """Azure cloud provider implementation."""

    def __init__(self, config: AzureConfig):
        """Initialize Azure cloud provider.

        Args:
            config (AzureConfig): Azure configuration

        Raises:
            ValueError: If configuration is invalid
        """
        super().__init__(config)
        self._credential = None
        self._consumption_client = None
        self._resource_client = None
        self.name = "azure"
        sanitized_config = mask_sensitive_config_object(config)
        logger.info(
            f"Initialized Azure Cloud provider with config: "
            f"{sanitized_config}"
        )

    @property
    def credential(self):
        """Get Azure credential."""
        if self._credential is None:
            self._credential = ClientSecretCredential(
                tenant_id=self.config.tenant_id,
                client_id=self.config.client_id,
                client_secret=self.config.client_secret
            )
        return self._credential

    @property
    def consumption_client(self):
        """Get Azure Consumption Management client."""
        if self._consumption_client is None:
            self._consumption_client = ConsumptionManagementClient(
                credential=self.credential,
                subscription_id=self.config.subscription_id
            )
        return self._consumption_client

    @property
    def resource_client(self):
        """Get Azure Resource Management client."""
        if self._resource_client is None:
            self._resource_client = ResourceManagementClient(
                credential=self.credential,
                subscription_id=self.config.subscription_id
            )
        return self._resource_client

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
            period = datetime.now().strftime("%Y-%m")

        logger.info(f"Getting billing info for period: {period}")

        try:
            year, month = map(int, period.split("-"))
            if not (1 <= month <= 12):
                raise ValueError("Month must be between 1 and 12")
        except ValueError as e:
            raise ValueError(f"Invalid period format: {str(e)}")

        return period

    def _get_period_dates(self, period: str) -> Tuple[str, str]:
        """Get start and end dates for the billing period.

        Args:
            period (str): Period in YYYY-MM format

        Returns:
            Tuple[str, str]: Start and end dates in YYYY-MM-DD format
        """
        year, month = map(int, period.split("-"))
        if month == 12:
            next_month = 1
            next_year = year + 1
        else:
            next_month = month + 1
            next_year = year

        last_day = (
            datetime(next_year, next_month, 1) - timedelta(days=1)
        ).day

        return f"{period}-01", f"{period}-{last_day:02d}"

    def _query_billing_api(
        self, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """Query the Azure Consumption API.

        Args:
            start_date (str): Start date in YYYY-MM-DD format
            end_date (str): End date in YYYY-MM-DD format

        Returns:
            Dict[str, Any]: API response containing cost and usage data
        """
        logger.debug(
            f"Using Azure configuration: "
            f"subscription_id={self.config.subscription_id}"
        )

        usage_details = self.consumption_client.usage_details.list(
            scope=f"/subscriptions/{self.config.subscription_id}",
            filter=(
                f"usageStart ge '{start_date}' and "
                f"usageEnd le '{end_date}'"
            )
        )

        return list(usage_details)

    def _calculate_total_cost(
        self, usage_details: list
    ) -> Tuple[float, str]:
        """Calculate total cost from billing API response.

        Args:
            usage_details (list): List of usage details

        Returns:
            Tuple[float, str]: Total cost and currency
        """
        total_cost = sum(float(detail.cost) for detail in usage_details)
        currency = (
            usage_details[0].billing_currency
            if usage_details else "USD"
        )

        logger.debug(
            f"Calculated total cost: {total_cost} {currency}"
        )

        return total_cost, currency

    def get_billing_info(
        self, period: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get Azure billing information for a specific period.

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
                        "account_id": str
                    } | None,
                    "error": str | None
                }

        Raises:
            Exception: If the billing information cannot be retrieved
        """
        try:
            period = self._validate_period(period)
            start_date, end_date = self._get_period_dates(period)

            usage_details = self._query_billing_api(start_date, end_date)
            total_cost, currency = self._calculate_total_cost(usage_details)
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
        """Get the Azure subscription ID.

        Returns:
            str: Azure subscription ID

        Raises:
            Exception: If the subscription ID cannot be retrieved
        """
        try:
            return self.config.subscription_id
        except Exception as e:
            logger.error(f"Failed to get account ID: {str(e)}")
            raise

    def validate_credentials(self) -> bool:
        """Validate the Azure credentials.

        Returns:
            bool: True if credentials are valid, False otherwise

        Raises:
            Exception: If the validation fails due to network or other issues
        """
        try:
            # Try to get subscription details to validate credentials
            self.resource_client.subscriptions.get(
                self.config.subscription_id
            )
            return True
        except Exception as e:
            logger.error(f"Failed to validate credentials: {str(e)}")
            return False
