"""Bound expensive snapshot computations across API processes."""

import time
from contextlib import contextmanager
from threading import BoundedSemaphore

from django.db import connection, transaction

from agione_ops.client import AgioneOpsError

QUERY_SLOTS = 2
QUERY_WAIT_SECONDS = 5
_LOCK_NAMESPACE = 0x4147494F
_local_slots = BoundedSemaphore(QUERY_SLOTS)


def _busy():
    return AgioneOpsError(
        "QUERY_IN_PROGRESS", status_code=503, retryable=True,
    )


@contextmanager
def snapshot_compute_slot():
    """Release the database slot automatically on transaction end or crash."""
    if connection.vendor != "postgresql":
        if not _local_slots.acquire(timeout=QUERY_WAIT_SECONDS):
            raise _busy()
        try:
            yield
        finally:
            _local_slots.release()
        return

    deadline = time.monotonic() + QUERY_WAIT_SECONDS
    with transaction.atomic():
        while True:
            with connection.cursor() as cursor:
                for slot in range(QUERY_SLOTS):
                    cursor.execute(
                        "SELECT pg_try_advisory_xact_lock(%s, %s)",
                        [_LOCK_NAMESPACE, slot],
                    )
                    if cursor.fetchone()[0]:
                        break
                else:
                    if time.monotonic() >= deadline:
                        raise _busy()
                    time.sleep(0.05)
                    continue
            break
        yield
