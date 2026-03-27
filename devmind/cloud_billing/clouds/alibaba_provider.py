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

try:
    from alibabacloud_sts20150401.client import Client as StsClient
    _STS_AVAILABLE = True
except ImportError:
    StsClient = None  # type: ignore[misc, assignment]
    _STS_AVAILABLE = False


# Configure logging
logger = logging.getLogger(__name__)

# BSS OpenAPI: China uses business.aliyuncs.com (bssopenapi.*.aliyuncs.com often fails to resolve).
BSS_ENDPOINT_CHINA = "business.aliyuncs.com"
DEFAULT_BSS_ENDPOINT = "bssopenapi.aliyuncs.com"
BSS_OPENAPI_ENDPOINT = DEFAULT_BSS_ENDPOINT  # alias for backward compatibility
# STS GetCallerIdentity endpoint (same as working script: sts.aliyuncs.com).
STS_ENDPOINT_DEFAULT = "sts.aliyuncs.com"


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
            self.region = os.environ.get("ALIBABA_REGION", "cn-hangzhou")

        # Validate required fields (region has default for BSS central endpoint)
        if not self.api_key:
            raise ValueError("access key ID is required")
        if not self.api_secret:
            raise ValueError("access key secret is required")


class AlibabaCloud(BaseCloudProvider):
    """Alibaba Cloud provider implementation."""

    def __init__(self, config: AlibabaConfig):
        """Initialize Alibaba Cloud provider.

        Args:
            config (AlibabaConfig): Alibaba Cloud configuration
        """
        super().__init__(config)
        self._client = None
        self._sts_client = None
        self.name = "alibaba"

    def _get_sts_endpoint(self) -> str:
        """STS endpoint (env override or default sts.aliyuncs.com, same as working script)."""
        return os.environ.get("ALIBABA_STS_ENDPOINT", "").strip() or STS_ENDPOINT_DEFAULT

    @property
    def sts_client(self) -> Optional[Any]:
        """Lazy STS client for GetCallerIdentity (account ID). Build same as working script."""
        if not _STS_AVAILABLE or StsClient is None:
            return None
        if self._sts_client is None:
            endpoint = self._get_sts_endpoint()
            logger.debug("Using Alibaba STS endpoint: %s", endpoint)
            # Same as working script: Config(access_key_id, access_key_secret) then set endpoint
            cfg = Config(
                access_key_id=self.config.api_key,
                access_key_secret=self.config.api_secret,
            )
            cfg.endpoint = endpoint
            self._sts_client = StsClient(cfg)
        return self._sts_client

    def _get_bss_endpoint(self) -> str:
        """Resolve BSS endpoint: env override, then China region -> business.aliyuncs.com, else default."""
        endpoint = os.environ.get("ALIBABA_BSS_ENDPOINT", "").strip()
        if endpoint:
            return endpoint
        region = (self.config.region or "").strip().lower()
        if region and region.startswith("cn-"):
            return BSS_ENDPOINT_CHINA
        if region:
            return f"bssopenapi.{region}.aliyuncs.com"
        return BSS_OPENAPI_ENDPOINT

    @property
    def client(self) -> Client:
        """Get Alibaba Cloud BSS client."""
        if self._client is None:
            endpoint = self._get_bss_endpoint()
            logger.debug("Using Alibaba BSS endpoint: %s", endpoint)
            config = Config(
                access_key_id=self.config.api_key,
                access_key_secret=self.config.api_secret,
                endpoint=endpoint,
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
            billing_cycle=billing_cycle
        )
        return self.client.query_bill(request)

    def _calculate_total_cost(
        self, response: Dict[str, Any]
    ) -> Tuple[float, str, Dict[str, float]]:
        """Calculate total cost and service breakdown from API response.

        Args:
            response (Dict[str, Any]): API response

        Returns:
            Tuple[float, str, Dict[str, float]]: Total cost, currency, and service costs
        """
        data = response.body.data
        total_cost = 0.0
        currency = 'CNY'
        service_costs: Dict[str, float] = {}

        # Extract items from the response
        items_obj = getattr(data, 'items', None)
        if items_obj:
            # Get item list (attribute is 'item' in lowercase)
            items = getattr(items_obj, 'item', [])
            
            if not isinstance(items, list):
                items = [items]

            for item in items:
                try:
                    # Handle both dict and object items
                    if isinstance(item, dict):
                        pretax_amount = float(item.get('PretaxAmount', 0))
                        product_name = item.get('ProductName', 'Unknown Service')
                        product_code = item.get('ProductCode', '')
                        item_currency = item.get('Currency', 'CNY')
                    else:
                        pretax_amount = float(getattr(item, 'pretax_amount', 0))
                        product_name = getattr(item, 'product_name', 'Unknown Service')
                        product_code = getattr(item, 'product_code', '')
                        item_currency = getattr(item, 'currency', 'CNY')

                    total_cost += pretax_amount
                    currency = item_currency

                    if product_code:
                        service_key = f"{product_name} ({product_code})"
                    else:
                        service_key = product_name

                    service_costs[service_key] = service_costs.get(service_key, 0) + pretax_amount
                except (AttributeError, ValueError, TypeError, KeyError):
                    continue

        return total_cost, currency, service_costs

    def _query_account_balance(self) -> Any:
        """Query Alibaba Cloud account balance."""
        return self.client.query_account_balance()

    def _to_plain_dict(self, value: Any) -> Any:
        """Convert SDK models to plain dictionaries/lists when possible."""
        if value is None:
            return None
        if isinstance(value, dict):
            return {
                k: self._to_plain_dict(v)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [self._to_plain_dict(item) for item in value]

        to_map = getattr(value, "to_map", None)
        if callable(to_map):
            try:
                return self._to_plain_dict(to_map())
            except Exception:
                pass

        raw_dict = getattr(value, "__dict__", None)
        if isinstance(raw_dict, dict) and raw_dict:
            return {
                k: self._to_plain_dict(v)
                for k, v in raw_dict.items()
                if not k.startswith("_")
            }

        return value

    def _get_nested_value(self, data: Any, key: str) -> Any:
        """Read a value from dict/object using common Tea/OpenAPI styles."""
        if data is None:
            return None

        if isinstance(data, dict):
            if key in data:
                return data[key]
            lowered = key.lower()
            for candidate_key, candidate_value in data.items():
                if str(candidate_key).lower() == lowered:
                    return candidate_value
            return None

        direct = getattr(data, key, None)
        if direct is not None:
            return direct

        lowered = key.lower()
        for attr in dir(data):
            if attr.startswith("_"):
                continue
            if attr.lower() == lowered:
                return getattr(data, attr, None)
        return None

    def _parse_amount(self, value: Any) -> Optional[float]:
        """Parse amount strings like '2,895.93' into floats."""
        if value in (None, ""):
            return None
        try:
            return float(str(value).strip().replace(",", ""))
        except (TypeError, ValueError):
            return None

    def _extract_cash_balance(self, response: Any) -> Optional[float]:
        """Extract cash balance from Alibaba Cloud balance response."""
        body = self._get_nested_value(response, "body")
        plain_body = self._to_plain_dict(body)
        data = self._get_nested_value(body, "data")
        if data is None:
            data = self._get_nested_value(plain_body, "data")

        logger.warning(
            "Alibaba QueryAccountBalance raw response body: %s",
            plain_body,
        )

        candidate_sources = [data, self._to_plain_dict(data), body, plain_body]
        candidate_fields = [
            "available_cash_amount",
            "AvailableCashAmount",
            "available_amount",
            "AvailableAmount",
            "cash_amount",
            "CashAmount",
            "balance_amount",
            "BalanceAmount",
        ]

        for source in candidate_sources:
            if source is None:
                continue
            for field in candidate_fields:
                value = self._get_nested_value(source, field)
                if value in (None, ""):
                    continue
                parsed_value = self._parse_amount(value)
                if parsed_value is None:
                    continue
                logger.warning(
                    "Alibaba QueryAccountBalance matched field %s=%s",
                    field,
                    parsed_value,
                )
                return parsed_value

        logger.warning(
            "Alibaba QueryAccountBalance returned no recognizable cash "
            "balance field. body=%s",
            plain_body,
        )
        return None

    def _build_balance_debug_info(self, response: Any) -> Dict[str, Any]:
        """Build a compact debug payload for balance parsing diagnostics."""
        body = self._get_nested_value(response, "body")
        plain_body = self._to_plain_dict(body)
        data = self._get_nested_value(body, "data")
        if data is None:
            data = self._get_nested_value(plain_body, "data")
        plain_data = self._to_plain_dict(data)
        return {
            "body_keys": sorted(plain_body.keys())
            if isinstance(plain_body, dict)
            else [],
            "data": plain_data,
        }

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
            total_cost, currency, service_costs = self._calculate_total_cost(response)
            balance_response = self._query_account_balance()
            balance = self._extract_cash_balance(balance_response)
            balance_debug = self._build_balance_debug_info(balance_response)
            account_id = self.get_account_id()

            logger.warning(
                "Alibaba billing collection result: period=%s total_cost=%s "
                "currency=%s balance=%s account_id=%s",
                period,
                total_cost,
                currency,
                balance,
                account_id,
            )

            return {
                "status": "success",
                "data": {
                    "total_cost": total_cost,
                    "balance": balance,
                    "balance_debug": balance_debug,
                    "currency": currency,
                    "account_id": account_id,
                    "service_costs": service_costs
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
        """Get the Alibaba Cloud account ID via STS GetCallerIdentity (same as working script)."""
        if self.sts_client is None:
            logger.warning(
                "Alibaba account_id requires alibabacloud-sts20150401. "
                "Install in backend env: pip install alibabacloud-sts20150401"
            )
            return ""
        try:
            response = self.sts_client.get_caller_identity()
            body = response.body
            if body is None:
                return ""
            account_id = getattr(body, "account_id", None)
            return str(account_id) if account_id else ""
        except Exception as e:
            logger.warning("Alibaba STS GetCallerIdentity failed: %s", e)
            return ""

    def validate_credentials(self) -> bool:
        """Validate via STS GetCallerIdentity when available, else BSS QueryAccountBalance."""
        if self.sts_client is not None:
            try:
                response = self.sts_client.get_caller_identity()
                body = response.body
                if body and getattr(body, "account_id", None):
                    return True
            except Exception as e:
                logger.warning("Alibaba STS GetCallerIdentity failed, trying BSS: %s", e)
        # Fallback: BSS QueryAccountBalance (no account_id, but validates credentials)
        try:
            self.client.query_account_balance()
            if self.sts_client is None:
                logger.info(
                    "Alibaba validated via BSS. Install alibabacloud-sts20150401 "
                    "in backend to get account_id: pip install alibabacloud-sts20150401"
                )
            return True
        except Exception as e:
            logger.error("Alibaba credential validation failed: %s", e)
            raise
