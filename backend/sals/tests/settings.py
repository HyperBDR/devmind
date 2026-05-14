"""
Minimal Django settings for sals tests.
"""
SECRET_KEY = "sals-tests-secret-key"
DEBUG = True
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "django_celery_beat",
    "agentcore_task.adapters.django",
    "sals",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

ROOT_URLCONF = "sals.tests.urls"
REST_FRAMEWORK = {}
CELERY_TASK_ALWAYS_EAGER = True
