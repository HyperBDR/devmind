"""The shared task projection must never become domain authority."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.db import DatabaseError, transaction

from agione_ops import tracking


def test_projection_is_off_without_explicit_opt_in(monkeypatch, settings):
    settings.AGIONE_OPS_TASK_PROJECTION_ENABLED = False
    factory = Mock(side_effect=AssertionError("Unexpected tracker import"))
    monkeypatch.setattr(tracking, "_tracker", factory)
    assert tracking.project_run("synthetic-run") is False
    factory.assert_not_called()


@pytest.mark.django_db
def test_projection_failure_is_safe_for_an_enclosing_transaction(
    monkeypatch,
    settings,
):
    settings.AGIONE_OPS_TASK_PROJECTION_ENABLED = True
    from agione_ops.models import SyncRun

    with transaction.atomic():
        assert (
            tracking.project_run("00000000-0000-4000-8000-000000000001")
            is False
        )
        assert SyncRun.objects.count() == 0


def test_projection_metadata_never_contains_source_or_business_payload(
    monkeypatch,
    settings,
):
    settings.AGIONE_OPS_TASK_PROJECTION_ENABLED = True
    run = SimpleNamespace(
        pk="synthetic-run",
        celery_id="synthetic-celery",
        status="succeeded",
        initiated_by=object(),
    )
    from agione_ops.models import SyncRun

    query = Mock()
    query.get.return_value = run
    monkeypatch.setattr(
        SyncRun.objects, "select_related", Mock(return_value=query)
    )
    tracker = Mock()
    statuses = SimpleNamespace(
        **{
            name: name
            for name in (
                "PENDING",
                "STARTED",
                "RETRY",
                "SUCCESS",
                "REVOKED",
                "FAILURE",
            )
        }
    )
    monkeypatch.setattr(tracking, "_tracker", lambda: (tracker, statuses))
    atomic = Mock()
    atomic.return_value.__enter__ = Mock()
    atomic.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(tracking.transaction, "atomic", atomic)
    assert tracking.project_run(run.pk) is True
    payload = tracker.register_task.call_args.kwargs
    assert payload["metadata"] == {"domain_run_id": "synthetic-run"}
    assert payload["task_kwargs"] == {"run_id": "synthetic-run"}
    assert payload["created_by"] is run.initiated_by
    assert tracker.update_task_status.call_args.args == (
        "synthetic-celery",
        "SUCCESS",
    )
    tracker.register_task.side_effect = DatabaseError(
        "synthetic-private-detail"
    )
    assert tracking.project_run(run.pk) is False
