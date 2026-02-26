"""
Minimal Django settings for cloud_billing tests.
Runs without agentcore_metering so tests can run in isolation.
"""
SECRET_KEY = "test-secret"
DEBUG = True
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "cloud_billing",
    "agentcore_notifier.adapters.django",
    "agentcore_task.adapters.django",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
ROOT_URLCONF = "cloud_billing.tests.urls"
CELERY_TASK_ALWAYS_EAGER = True
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": (
        "rest_framework.pagination.PageNumberPagination"
    ),
    "PAGE_SIZE": 100,
}
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
