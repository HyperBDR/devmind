import importlib.util
from pathlib import Path


SENTRY_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "core" / "sentry.py"
)

spec = importlib.util.spec_from_file_location(
    "core_sentry_for_tests",
    SENTRY_MODULE_PATH,
)
assert spec is not None
assert spec.loader is not None
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


def test_before_send_drops_celery_beat_postgres_connection_refused():
    event = {
        "logger": "django_celery_beat.schedulers",
        "exception": {
            "values": [
                {
                    "type": "OperationalError",
                    "value": (
                        'connection to server at "postgresql" '
                        "(172.18.0.4), port 5432 failed: "
                        "Connection refused\n"
                    ),
                }
            ]
        },
    }

    assert core_sentry.before_send(event, {}) is None


def test_before_send_drops_celery_redis_broker_reconnect_logs():
    event = {
        "logger": "celery.worker.consumer.consumer",
        "logentry": {
            "message": "consumer: Cannot connect to %s: %s.\n%s\n",
            "formatted": (
                "consumer: Cannot connect to redis://redis:6379/0: "
                "Error 111 connecting to redis:6379. Connection refused..\n"
                "Trying again in 2.00 seconds... (1/None)\n"
            ),
        },
    }

    assert core_sentry.before_send(event, {}) is None


def test_before_send_keeps_non_broker_celery_consumer_errors():
    event = {
        "logger": "celery.worker.consumer.consumer",
        "logentry": {
            "formatted": "consumer: Unexpected unrecoverable worker error",
        },
    }

    assert core_sentry.before_send(event, {}) is event


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
