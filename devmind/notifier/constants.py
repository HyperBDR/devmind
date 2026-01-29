"""
Constants for notifier app.
"""


class Status:
    """
    Notification status constants.
    """
    PENDING = 'pending'
    SUCCESS = 'success'
    FAILED = 'failed'


class Provider:
    """
    Notification provider type constants.
    """
    FEISHU = 'feishu'
    WECOM = 'wecom'
    WECHAT = 'wechat'
    EMAIL = 'email'


class Channel:
    """
    Notification channel constants.
    """
    WEBHOOK = 'webhook'
    EMAIL = 'email'
    SMS = 'sms'


# Default values
DEFAULT_SOURCE_APP = 'unknown'
DEFAULT_PROVIDER_TYPE = Provider.FEISHU
DEFAULT_TIMEOUT = 10

# Configuration keys
CONFIG_KEY_WEBHOOK = 'webhook_config'

# Provider type groups
FEISHU_PROVIDERS = [Provider.FEISHU, Provider.WECOM]
