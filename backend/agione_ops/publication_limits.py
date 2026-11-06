"""Limit memory-intensive snapshot publication across workers."""

import time
from contextlib import contextmanager
from threading import Lock

from django.db import connection


_LOCK_NAMESPACE = 0x4147494F
_LOCK_SLOT = 100
_MYSQL_LOCK = "devmind_agione_snapshot_publish"
_local_lock = Lock()


@contextmanager
def publication_slot(checkpoint):
    """Keep waiting tasks alive; release the slot even when publication fails."""
    vendor = connection.vendor
    acquired = False
    try:
        while not acquired:
            checkpoint("publishing")
            if vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_try_advisory_lock(%s, %s)",
                        [_LOCK_NAMESPACE, _LOCK_SLOT],
                    )
                    acquired = bool(cursor.fetchone()[0])
            elif vendor == "mysql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT GET_LOCK(%s, 0)", [_MYSQL_LOCK])
                    acquired = cursor.fetchone()[0] == 1
            else:
                acquired = _local_lock.acquire(blocking=False)
            if not acquired:
                time.sleep(1)
        yield
    finally:
        if acquired:
            if vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_unlock(%s, %s)",
                        [_LOCK_NAMESPACE, _LOCK_SLOT],
                    )
            elif vendor == "mysql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", [_MYSQL_LOCK])
            else:
                _local_lock.release()
