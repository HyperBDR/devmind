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
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
ROOT_URLCONF = "cloud_billing.tests.urls"
CELERY_TASK_ALWAYS_EAGER = True
