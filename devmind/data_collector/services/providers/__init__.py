"""
Platform providers for data collection. Use get_provider(platform) to resolve.
"""
from .base import BaseProvider
from .ai_pricehub import AIPriceHubProvider
from .feishu import FeishuProvider
from .jira import JiraProvider
from .license import LicenseProvider

PROVIDER_MAPPING = {
    "ai_pricehub": AIPriceHubProvider,
    "feishu": FeishuProvider,
    "jira": JiraProvider,
    "license": LicenseProvider,
}


def get_provider(platform: str) -> type[BaseProvider] | None:
    """
    Return provider class for platform, or None if not registered.
    """
    return PROVIDER_MAPPING.get(platform)
