SECRET_KEY = "onepro-monitor-tests"
DEBUG = True
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "django_celery_beat",
    "onepro_monitor",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}
ROOT_URLCONF = "onepro_monitor.tests.urls"
CELERY_TASK_ALWAYS_EAGER = True
REST_FRAMEWORK = {}
