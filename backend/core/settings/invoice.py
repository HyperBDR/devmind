"""Settings for invoice and sales-record documents."""

import os

from .quotation import STORAGE_ROOT

INVOICE_STORAGE = os.getenv(
    "INVOICE_STORAGE",
    os.path.join(STORAGE_ROOT, "invoice"),
)
INVOICE_MAX_UPLOAD_BYTES = int(
    os.getenv("INVOICE_MAX_UPLOAD_BYTES", str(50 * 1024 * 1024))
)
INVOICE_UPLOAD_CHUNK_BYTES = int(
    os.getenv("INVOICE_UPLOAD_CHUNK_BYTES", str(1024 * 1024))
)
INVOICE_MAX_SIGNATURE_LENGTH = int(
    os.getenv("INVOICE_MAX_SIGNATURE_LENGTH", str(3 * 1024 * 1024))
)
INVOICE_FEISHU_FOLDER_URL = os.getenv(
    "INVOICE_FEISHU_FOLDER_URL",
    (
        "https://oneprocloud.feishu.cn/drive/folder/"
        "IhhIf6eRKlx8NddzKPUcATyPnnd"
    ),
)
INVOICE_FEISHU_FOLDER_TOKEN = os.getenv(
    "INVOICE_FEISHU_FOLDER_TOKEN",
    "",
)
INVOICE_FEISHU_SYNC_INTERVAL_SECONDS = int(
    os.getenv("INVOICE_FEISHU_SYNC_INTERVAL_SECONDS", "900")
)
INVOICE_FEISHU_SYNC_STALE_SECONDS = int(
    os.getenv("INVOICE_FEISHU_SYNC_STALE_SECONDS", "1800")
)
INVOICE_FEISHU_PERIODIC_SYNC_ENABLED = os.getenv(
    "INVOICE_FEISHU_PERIODIC_SYNC_ENABLED",
    "true",
).lower() == "true"
