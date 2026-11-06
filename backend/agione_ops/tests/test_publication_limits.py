"""Protect native publication across workers."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from django.db import close_old_connections, connection


@pytest.mark.django_db(transaction=True)
def test_publications_wait_with_heartbeats_and_release_after_failure():
    from agione_ops.publication_limits import publication_slot

    if connection.vendor != "postgresql":
        pytest.skip("Cross-process publication lock requires PostgreSQL")
    entered = Event()
    release = Event()
    waiting = Event()
    second_entered = Event()
    heartbeats = []

    def first():
        try:
            with publication_slot(lambda phase: None):
                entered.set()
                assert release.wait(10)
                raise ValueError("publication failed")
        finally:
            close_old_connections()

    def second():
        try:
            assert entered.wait(5)

            def heartbeat(phase):
                heartbeats.append(phase)
                if len(heartbeats) >= 2:
                    waiting.set()

            with publication_slot(heartbeat):
                second_entered.set()
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(first)
        follower = pool.submit(second)
        try:
            assert waiting.wait(5)
            assert not second_entered.is_set()
        finally:
            release.set()
        with pytest.raises(ValueError):
            owner.result(timeout=10)
        follower.result(timeout=10)
    assert second_entered.is_set()


@pytest.mark.django_db(transaction=True)
def test_publication_lock_is_released_when_database_session_closes():
    from agione_ops.publication_limits import publication_slot

    if connection.vendor != "postgresql":
        pytest.skip("Session lock release requires PostgreSQL")
    entered = Event()
    disconnected = Event()

    def owner():
        try:
            with publication_slot(lambda phase: None):
                entered.set()
                assert disconnected.wait(5)
                connection.close()
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(owner)
        assert entered.wait(5)
        disconnected.set()
        future.result(timeout=10)
    with publication_slot(lambda phase: None):
        pass
