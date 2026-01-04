"""
Storage-related Django settings.

This module contains settings for file storage, including local storage paths
and OSS (Object Storage Service) configuration.
"""
import os

# ============================
# Local Storage Configuration
# ============================

# ============================
# OSS Configuration
# ============================

# OSS configuration dictionary for ObjectStorage initialization
# This is used by devtoolbox.storage.ObjectStorage
OSS_CONFIG = {
    'access_key_id': os.getenv('DEVMIND_OSS_ACCESS_KEY_ID', ''),
    'access_key_secret': os.getenv('DEVMIND_OSS_ACCESS_KEY_SECRET', ''),
    'endpoint': os.getenv('DEVMIND_OSS_ENDPOINT', ''),
    'bucket_name': os.getenv('DEVMIND_OSS_BUCKET_NAME', ''),
    'region': os.getenv('DEVMIND_OSS_REGION', ''),
    'use_virtual_style': (
        os.getenv('DEVMIND_OSS_USE_VIRTUAL_STYLE', 'False').lower()
        == 'true'
    ),
}
