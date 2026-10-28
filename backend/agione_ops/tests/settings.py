"""Isolated synthetic settings: no project configuration or real secrets."""

import base64

SECRET_KEY = "synthetic-agione-tests-only"
DEBUG = False
USE_TZ = True
TIME_ZONE = "Asia/Shanghai"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "agione_ops",
]
DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
}
ROOT_URLCONF = "agione_ops.tests.urls"
ALLOWED_HOSTS = ["testserver"]
MIDDLEWARE = []
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
AGIONE_OPS_SYNTHETIC_ENABLED = True
AGIONE_OPS_ACTIVE_KEY_ID = "synthetic-test-key"
AGIONE_OPS_ENCRYPTION_KEYS = {
    "synthetic-test-key": base64.urlsafe_b64encode(b"0" * 32).decode("ascii"),
}
AGIONE_OPS_ALLOWED_ENDPOINT_HOSTS = []
