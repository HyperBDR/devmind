"""
Constants for cloud billing app.
"""

# Webhook status values
WEBHOOK_STATUS_PENDING = 'pending'
WEBHOOK_STATUS_SUCCESS = 'success'
WEBHOOK_STATUS_FAILED = 'failed'

# Source app and type for notifications
SOURCE_APP_CLOUD_BILLING = 'cloud_billing'
SOURCE_TYPE_ALERT = 'alert'

# Language codes
LANGUAGE_ZH_HANS = 'zh-hans'
LANGUAGE_EN = 'en'

# Default language
DEFAULT_LANGUAGE = LANGUAGE_ZH_HANS

# Feishu payload keys
FEISHU_MSG_TYPE_POST = 'post'
FEISHU_TAG_TEXT = 'text'
FEISHU_TAG_AT = 'at'
FEISHU_USER_ID_ALL = 'all'

# WeChat payload keys
WECHAT_MSGTYPE_MARKDOWN = 'markdown'

# Message titles
FEISHU_TITLE_ZH_HANS = "[重点关注]云平台账单消费提醒"
FEISHU_TITLE_EN = "[Important] Cloud Billing Alert"

WECHAT_TITLE_ZH_HANS = "## 云平台账单消费提醒\n\n"
WECHAT_TITLE_EN = "## Cloud Billing Alert\n\n"
