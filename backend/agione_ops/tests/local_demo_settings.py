"""Disposable local-demo tests with the real accounts app and signals."""

from agione_ops.tests.settings import *

INSTALLED_APPS = [*INSTALLED_APPS, "accounts"]
AGIONE_OPS_LOCAL_DEMO_ENABLED = True
AGIONE_OPS_LOCAL_EAGER = True
AGIONE_OPS_SYNTHETIC_ENABLED = True
AGIONE_OPS_TASK_PROJECTION_ENABLED = False
# Inline execution is app-local even when the global eager flag is off.
CELERY_TASK_ALWAYS_EAGER = False
