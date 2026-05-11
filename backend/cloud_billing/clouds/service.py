"""Cloud service base classes and provider factory.

This module provides base classes for cloud services and a factory
for creating cloud provider instances.
"""

import logging
from typing import Dict, Any, Optional

from ..utils.logging import mask_sensitive_config

from .aws_provider import AWSConfig, AWSCloud
from .huawei_provider import HuaweiConfig, HuaweiCloud
from .huawei_intl_provider import HuaweiIntlConfig, HuaweiIntlCloud
from .alibaba_provider import AlibabaConfig, AlibabaCloud
from .azure_provider import AzureConfig, AzureCloud
from .tencent_provider import TencentConfig, TencentCloud
from .volcengine_provider import VolcengineConfig, VolcengineCloud
from .baidu_provider import BaiduConfig, BaiduCloud
from .zhipu_provider import ZhipuConfig, ZhipuCloud

# Configure logging
logger = logging.getLogger(__name__)


def _build_provider_mapping():
    mapping = {
        "aws": {"config_class": AWSConfig, "provider_class": AWSCloud},
        "huawei": {
            "config_class": HuaweiConfig,
            "provider_class": HuaweiCloud,
        },
        "huawei-intl": {
            "config_class": HuaweiIntlConfig,
            "provider_class": HuaweiIntlCloud,
        },
        "alibaba": {
            "config_class": AlibabaConfig,
            "provider_class": AlibabaCloud,
        },
        "azure": {"config_class": AzureConfig, "provider_class": AzureCloud},
        "volcengine": {
            "config_class": VolcengineConfig,
            "provider_class": VolcengineCloud,
        },
        "baidu": {
            "config_class": BaiduConfig,
            "provider_class": BaiduCloud,
        },
        "zhipu": {
            "config_class": ZhipuConfig,
            "provider_class": ZhipuCloud,
        },
    }
    mapping["tencentcloud"] = {
        "config_class": TencentConfig,
        "provider_class": TencentCloud,
    }
    return mapping


class ProviderFactory:
    """Factory for creating cloud provider instances."""

    # Mapping of provider names to their config and provider classes
    PROVIDER_MAPPING = _build_provider_mapping()

    @classmethod
    def create_provider(
        cls, provider_name: str, config: Optional[Dict[str, Any]] = {}
    ) -> Any:
        """Create a cloud provider instance.

        Args:
            provider_name (str): Name of the cloud provider
            config (Dict[str, Any]): Provider configuration

        Returns:
            Any: Cloud provider instance

        Raises:
            ValueError: If provider name is not supported
        """
        if provider_name not in cls.PROVIDER_MAPPING:
            raise ValueError(f"Unsupported provider: {provider_name}")

        provider_info = cls.PROVIDER_MAPPING[provider_name]
        config_class = provider_info["config_class"]
        provider_class = provider_info["provider_class"]

        # Create provider instance with validated config
        # Add fallback to empty dict if config is None
        config = config or {}
        sanitized_config = mask_sensitive_config(config)
        logger.info(
            f"Creating provider instance with config: {sanitized_config}"
        )
        provider_config = config_class(**config)
        return provider_class(provider_config)


class BillingService:
    """Service for retrieving cloud billing information."""

    def __init__(
        self, provider_name: str, config: Optional[Dict[str, Any]] = None
    ):
        """Initialize billing service.

        Args:
            provider_name (str): Name of the cloud provider
            config (Dict[str, Any]): Provider configuration
        """
        self.provider = ProviderFactory.create_provider(provider_name, config)

    def get_billing_info(self, period: Optional[str] = None) -> Dict[str, Any]:
        """Get billing information.

        Args:
            period (Optional[str]): Period in YYYY-MM format. Defaults to
                current month if not specified.

        Returns:
            Dict[str, Any]: Billing information
        """
        return self.provider.get_billing_info(period=period)

    def get_resource_cost_breakdown(
        self,
        start_date: str,
        end_date: str,
        group_by: str = "SERVICE",
    ) -> Dict[str, Any]:
        """Get cost breakdown by resource dimension.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            group_by: Dimension to group by (SERVICE, INSTANCE_TYPE, etc.)

        Returns:
            Dict with cost breakdown by resource
        """
        if hasattr(self.provider, "get_resource_cost_breakdown"):
            return self.provider.get_resource_cost_breakdown(
                start_date, end_date, group_by
            )
        return {"status": "error", "error": "Not supported", "items": []}

    def list_instances_with_tags(self) -> list:
        """List instances with tags for owner resolution.

        Returns a list of dicts with instance_id, instance_name, owner.
        Returns empty list if not supported by the provider.
        """
        if hasattr(self.provider, "list_instances_with_tags"):
            return self.provider.list_instances_with_tags()
        return []
