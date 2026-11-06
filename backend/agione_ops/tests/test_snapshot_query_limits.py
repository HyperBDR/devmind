"""Bound concurrent snapshot work without leaving stale locks."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.db import close_old_connections, connection

from agione_ops.client import AgioneOpsError


@pytest.mark.django_db(transaction=True)
def test_snapshot_slots_bound_concurrent_work_and_recover(monkeypatch):
    from agione_ops import snapshot_query_limits as limits

    if connection.vendor != "postgresql":
        pytest.skip("Cross-connection advisory locks require PostgreSQL")
    monkeypatch.setattr(limits, "QUERY_WAIT_SECONDS", 0.15)
    release = Event()
    entered = [Event(), Event()]

    def hold(index):
        try:
            with limits.snapshot_compute_slot():
                entered[index].set()
                assert release.wait(5)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(hold, index) for index in range(2)]
        try:
            assert all(event.wait(3) for event in entered)
            with pytest.raises(AgioneOpsError, match="QUERY_IN_PROGRESS"):
                with limits.snapshot_compute_slot():
                    pass
        finally:
            release.set()
        for future in futures:
            future.result(timeout=5)
    with limits.snapshot_compute_slot():
        pass


@pytest.mark.django_db(transaction=True)
def test_snapshot_slot_is_released_when_computation_fails():
    from agione_ops.snapshot_query_limits import snapshot_compute_slot

    with pytest.raises(ValueError):
        with snapshot_compute_slot():
            raise ValueError("test failure")
    with snapshot_compute_slot():
        pass


def test_cache_hit_skips_slot_and_cache_miss_uses_slot(monkeypatch, settings):
    from agione_ops import query_cache, snapshot_query_limits

    source, actor = SimpleNamespace(source_kind="native"), object()
    monkeypatch.setattr(
        query_cache, "_authorize", lambda *_: (source, actor, {"id": "1"}),
    )
    events = []

    @contextmanager
    def slot():
        events.append("entered")
        yield
        events.append("released")

    monkeypatch.setattr(snapshot_query_limits, "snapshot_compute_slot", slot)
    query = {"operation": "dashboard", "data_version": "v1"}
    expected = {"dataVersion": "v1"}
    compute = Mock(return_value=expected)
    settings.AGIONE_OPS_QUERY_CACHE_ENABLED = False
    assert query_cache.cached_operation(source, actor, query, compute) == expected
    assert events == ["entered", "released"]

    events.clear()
    settings.AGIONE_OPS_QUERY_CACHE_ENABLED = True
    monkeypatch.setattr(
        query_cache, "_cache_get",
        lambda key: {"schema": query_cache._CACHE_SCHEMA, "result": expected},
    )
    assert query_cache.cached_operation(source, actor, query, compute) == expected
    assert not events
    compute.assert_called_once()
