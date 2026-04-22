"""
Data collector app configuration. Reads from Django settings.
"""
from django.conf import settings

DATA_COLLECTOR_ROOT = getattr(
    settings,
    "DATA_COLLECTOR_ROOT",
    "/opt/storage/data_collector",
)


def get_data_collector_root():
    """
    Return the root directory for data_collector storage (container path).
    Attachments are stored under {root}/raw_data/{raw_record_uuid}/.
    """
    return DATA_COLLECTOR_ROOT
