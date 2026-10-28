"""Combine the archived and new domains in one disposable SQLite database."""

from llm_ops.tests.archive_settings import *  # noqa: F403
from agione_ops.tests.settings import (
    AGIONE_OPS_ACTIVE_KEY_ID,
    AGIONE_OPS_ALLOWED_ENDPOINT_HOSTS,
    AGIONE_OPS_ENCRYPTION_KEYS,
)

INSTALLED_APPS = [*INSTALLED_APPS, "agione_ops"]  # noqa: F405
ROOT_URLCONF = "agione_ops.tests.integration_urls"
AGIONE_OPS_SYNTHETIC_ENABLED = True
AGIONE_OPS_TASK_PROJECTION_ENABLED = False
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
