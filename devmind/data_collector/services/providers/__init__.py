"""
Platform providers for data collection. Use get_provider(platform) to resolve.
"""
from .base import BaseProvider
from .feishu import FeishuProvider
from .hyperbdr import HyperBDRProvider
from .jira import JiraProvider
from .license import LicenseProvider

PROVIDER_MAPPING = {
    "feishu": FeishuProvider,
    "hyperbdr": HyperBDRProvider,
    "jira": JiraProvider,
    "license": LicenseProvider,
}


def get_provider(platform: str) -> type[BaseProvider] | None:
    """
    Return provider class for platform, or None if not registered.
    """
    return PROVIDER_MAPPING.get(platform)
