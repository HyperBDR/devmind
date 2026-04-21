"""
Minimal Django settings for data_collector tests.
"""
SECRET_KEY = "test-secret-dc"
DEBUG = True
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "django_celery_beat",
    "agentcore_task.adapters.django",
    "data_collector",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
ROOT_URLCONF = "data_collector.tests.urls"
CELERY_TASK_ALWAYS_EAGER = True
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": (
        "rest_framework.pagination.PageNumberPagination"
    ),
    "PAGE_SIZE": 100,
}
