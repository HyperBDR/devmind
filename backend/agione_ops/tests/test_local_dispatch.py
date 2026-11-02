"""The local switch changes only AGIOne dispatch, never global Celery mode."""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from agione_ops import snapshot_queries, sync
from agione_ops.client import AgioneOpsError
from agione_ops.snapshot_serializers import SnapshotOperationSerializer
from agione_ops.tasks import run_sync


def test_retired_demo_source_cannot_query(monkeypatch):
    connection = SimpleNamespace(pk="legacy", source_kind="demo_snapshot")
    monkeypatch.setattr(
        snapshot_queries, "get_connection_for", lambda *args: connection
    )
    with pytest.raises(AgioneOpsError) as error:
        snapshot_queries.query_operation(connection, object(), {})
    assert error.value.code == "SOURCE_KIND_FORBIDDEN"


@pytest.mark.parametrize("body", [
    {"operation": "customers"},
    {"operation": "customers", "data_version": str(uuid4()),
     "payload": {"page": True}},
    {"operation": "analysis", "data_version": str(uuid4()),
     "payload": {"group_by": ["date", "date"]}},
])
def test_snapshot_request_validation(body):
    assert not SnapshotOperationSerializer(data=body).is_valid()


@pytest.mark.parametrize("flag", [True, False, "true", 1, None])
def test_app_local_dispatch_uses_inline_only_for_literal_true(
    settings,
    monkeypatch,
    flag,
):
    """No database, transport or other task needs to run for this contract."""

    settings.AGIONE_OPS_LOCAL_EAGER = flag
    before = settings.CELERY_TASK_ALWAYS_EAGER
    run = SimpleNamespace(
        celery_id="synthetic-stable-celery-id",
        connection=SimpleNamespace(source_kind="synthetic"),
    )
    monkeypatch.setattr(sync.SyncRun.objects, "get", Mock(return_value=run))
    monkeypatch.setattr(sync, "_project", Mock())
    failure = Mock()
    monkeypatch.setattr(sync, "mark_dispatch_failed", failure)
    inline, queued = Mock(), Mock()
    monkeypatch.setattr(run_sync, "apply", inline)
    monkeypatch.setattr(run_sync, "apply_async", queued)
    sync._dispatch("synthetic-run")
    if flag is True:
        inline.assert_called_once_with(
            args=["synthetic-run"],
            task_id=run.celery_id,
        )
        queued.assert_not_called()
    else:
        queued.assert_called_once_with(
            args=["synthetic-run"],
            task_id=run.celery_id,
            retry=False,
        )
        inline.assert_not_called()
    failure.assert_not_called()
    assert settings.CELERY_TASK_ALWAYS_EAGER == before
