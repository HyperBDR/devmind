import importlib.util
from pathlib import Path


SENTRY_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "core" / "sentry.py"
)

spec = importlib.util.spec_from_file_location(
    "core_sentry_for_tests",
    SENTRY_MODULE_PATH,
)
core_sentry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core_sentry)


def test_before_send_drops_celery_beat_postgres_dns_errors():
    event = {
        "logger": "django_celery_beat.schedulers",
        "exception": {
            "values": [
                {
                    "type": "OperationalError",
                    "value": (
                        'could not translate host name "postgresql" '
                        "to address: Temporary failure in name resolution\n"
                    ),
                }
            ]
        },
    }

    assert core_sentry.before_send(event, {}) is None


def test_before_send_keeps_postgres_dns_errors_from_other_loggers():
    event = {
        "logger": "cloud_billing.tasks",
        "exception": {
            "values": [
                {
                    "type": "OperationalError",
                    "value": (
                        'could not translate host name "postgresql" '
                        "to address: Temporary failure in name resolution\n"
                    ),
                }
            ]
        },
    }

    assert core_sentry.before_send(event, {}) is event


def test_before_send_keeps_other_celery_beat_database_errors():
    event = {
        "logger": "django_celery_beat.schedulers",
        "exception": {
            "values": [
                {
                    "type": "OperationalError",
                    "value": "connection to server at postgresql timed out",
                }
            ]
        },
    }

    assert core_sentry.before_send(event, {}) is event
