"""
Platform providers for data collection. Use get_provider(platform) to resolve.
"""
from .base import BaseProvider
from .jira import JiraProvider
from .feishu import FeishuProvider

PROVIDER_MAPPING = {
    "jira": JiraProvider,
    "feishu": FeishuProvider,
}


def get_provider(platform: str) -> type[BaseProvider] | None:
    """
    Return provider class for platform, or None if not registered.
    """
    return PROVIDER_MAPPING.get(platform)
