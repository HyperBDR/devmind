"""
Sentry event filtering helpers.
"""


POSTGRES_DNS_ERROR = (
    'could not translate host name "postgresql" to address: '
    "Temporary failure in name resolution"
)
CELERY_BEAT_LOGGER = "django_celery_beat.schedulers"


def before_send(event, hint):
    """
    Drop expected transient infrastructure logs before sending to Sentry.
    """
    if _is_celery_beat_postgres_dns_error(event):
        return None
    return event


def _is_celery_beat_postgres_dns_error(event):
    if event.get("logger") != CELERY_BEAT_LOGGER:
        return False

    return _exception_matches(event) or _logentry_matches(event)


def _exception_matches(event):
    values = event.get("exception", {}).get("values") or []
    for value in values:
        if value.get("type") != "OperationalError":
            continue
        if POSTGRES_DNS_ERROR in str(value.get("value", "")):
            return True
    return False


def _logentry_matches(event):
    logentry = event.get("logentry") or {}
    message = " ".join(
        str(logentry.get(key, ""))
        for key in ("message", "formatted")
    )
    return POSTGRES_DNS_ERROR in message
