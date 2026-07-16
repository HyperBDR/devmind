"""Settings for quotation documents, PDF rendering, and Feishu Drive."""

import os

from .accounts import FRONTEND_URL


STORAGE_ROOT = os.getenv("STORAGE_ROOT", "/opt/storage")

QUOTATION_STORAGE = os.getenv(
    "QUOTATION_STORAGE",
    os.path.join(STORAGE_ROOT, "quotation"),
)

FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_BASE_URL = os.getenv(
    "FEISHU_BASE_URL",
    os.getenv("FEISHU_AUTH_BASE_URL", "https://open.feishu.cn"),
)
FEISHU_WEB_BASE_URL = os.getenv(
    "FEISHU_WEB_BASE_URL",
    os.getenv("FEISHU_APPROVAL_BASE_URL", "https://feishu.cn"),
)
FEISHU_OAUTH_REDIRECT_URI = os.getenv(
    "FEISHU_OAUTH_REDIRECT_URI",
    (
        f"{FRONTEND_URL.rstrip('/')}"
        "/api/v1/quotation/feishu/oauth/callback"
    ),
)
FEISHU_OAUTH_SCOPES = os.getenv(
    "FEISHU_OAUTH_SCOPES",
    "drive:drive drive:file drive:file:upload drive:file:download "
    "drive:export:readonly docs:document:export search:docs:read "
    "offline_access",
)
FEISHU_TEST_FOLDER_TOKEN = os.getenv("FEISHU_TEST_FOLDER_TOKEN", "")

QUOTATION_MAX_UPLOAD_BYTES = int(
    os.getenv("QUOTATION_MAX_UPLOAD_BYTES", str(50 * 1024 * 1024))
)
QUOTATION_ALLOWED_EXTENSIONS = (".xlsx", ".pdf")
QUOTATION_MAX_PDF_HTML_BYTES = int(
    os.getenv("QUOTATION_MAX_PDF_HTML_BYTES", str(5 * 1024 * 1024))
)
