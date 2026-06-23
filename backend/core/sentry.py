"""
Sentry event filtering helpers.
"""


POSTGRES_DNS_ERROR = (
    'could not translate host name "postgresql" to address: '
    "Temporary failure in name resolution"
)
CELERY_BEAT_LOGGER = "django_celery_beat.schedulers"
CELERY_CONSUMER_LOGGER = "celery.worker.consumer.consumer"
REDIS_BROKER_RECONNECT_PREFIX = "consumer: Cannot connect to redis://"
CELERY_RETRY_MESSAGE = "Trying again in"


def before_send(event, hint):
    """
    Drop expected transient infrastructure logs before sending to Sentry.
    """
    if _is_celery_beat_postgres_dns_error(event):
        return None
    if _is_celery_redis_broker_reconnect_log(event):
        return None
    return event


def _is_celery_beat_postgres_dns_error(event):
    if event.get("logger") != CELERY_BEAT_LOGGER:
        return False

    return _exception_matches(event) or _logentry_matches(event)


def _is_celery_redis_broker_reconnect_log(event):
    if event.get("logger") != CELERY_CONSUMER_LOGGER:
        return False

    message = _logentry_message(event)
    return (
        REDIS_BROKER_RECONNECT_PREFIX in message
        and CELERY_RETRY_MESSAGE in message
    )


def _exception_matches(event):
    values = event.get("exception", {}).get("values") or []
    for value in values:
        if value.get("type") != "OperationalError":
            continue
        if POSTGRES_DNS_ERROR in str(value.get("value", "")):
            return True
    return False


def _logentry_matches(event):
    return POSTGRES_DNS_ERROR in _logentry_message(event)


def _logentry_message(event):
    logentry = event.get("logentry") or {}
    return " ".join(
        str(logentry.get(key, ""))
        for key in ("message", "formatted")
    )
