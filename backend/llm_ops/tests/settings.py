"""Minimal Django settings for llm_ops-specific tests.

Kept narrow on purpose: we only need ``llm_ops`` + ``django_celery_beat``
plus the framework bits (``contenttypes``, ``auth``) required by the
model FK targets. The full project settings import cloud_billing /
data_collector / sals and cannot be used while those apps have
pre-existing migration issues unrelated to llm_ops.
"""
import os
from pathlib import Path

SECRET_KEY = "test-secret"
DEBUG = True

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django_celery_beat",
    "django_celery_results",
    "rest_framework",
    "llm_ops",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

ROOT_URLCONF = "llm_ops.tests.urls"
USE_TZ = True
TIME_ZONE = "Asia/Shanghai"
LANGUAGE_CODE = "en"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "core.paginations.APIPagination",
    "PAGE_SIZE": 10,
}
