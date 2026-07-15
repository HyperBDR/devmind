"""Minimal Django settings for data_ops tests."""

SECRET_KEY = "test-secret-data-ops"
DEBUG = True

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "accounts",
    "data_ops",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "data-ops-tests",
    }
}

ROOT_URLCONF = "data_ops.tests.urls"
USE_TZ = True
TIME_ZONE = "Asia/Shanghai"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CELERY_TASK_ALWAYS_EAGER = True

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": (
        "rest_framework.pagination.PageNumberPagination"
    ),
    "PAGE_SIZE": 20,
}
