"""Published synthetic business data is scoped, immutable and read-only."""

from datetime import timedelta
from unittest.mock import Mock

import pytest
from rest_framework.exceptions import NotFound

from agione_ops.client import AgioneOpsError, SyntheticClient
from agione_ops.models import DatasetVersion
from agione_ops.queries import query_dashboard
from agione_ops.sync import execute_sync, submit_sync
from agione_ops.tasks import run_sync
from agione_ops.tests.test_sync import make_prepared

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def never_dispatch(monkeypatch):
    """All task progression is explicit and local to the test process."""

    monkeypatch.setattr(run_sync, "apply_async", Mock())


def publish(graph, key="query-run"):
    user, connection, _, start, end = graph
    run, _ = submit_sync(connection, user, start, end, "Asia/Shanghai", key)
    assert execute_sync(run.pk)["status"] == "succeeded"
    return DatasetVersion.objects.get(run=run)


def test_no_snapshot_is_not_reported_as_successful_zero():
    user, connection, *_ = make_prepared()
    data = query_dashboard(connection, user)
    assert data["state"] == "not_collected"
    assert data["dataVersion"] is None
    assert data["summary"] is None
    assert data["comparison"]["summary"] is None


def test_basic_summary_preserves_unknown_and_token_sample_coverage():
    graph = make_prepared()
    version = publish(graph)
    user, connection, *_ = graph
    data = query_dashboard(connection, user, version.pk)
    summary = data["summary"]
    assert data["state"] == "ready"
    assert data["dataVersion"] == str(version.pk)
    assert summary["requests"] == 4
    assert (summary["success"], summary["failure"], summary["unknown"]) == (
        2,
        1,
        1,
    )
    assert summary["successRate"] == 50
    assert summary["activeCustomers"] == summary["activeModels"] == 2
    assert summary["inputTokens"] == 130
    assert summary["outputTokens"] == 43
    assert summary["inputTokensSampleCount"] == 3
    assert summary["inputTokensCoverage"] == 0.75
    assert summary["totalTokens"] == 140
    assert summary["totalTokensSampleCount"] == 2
    assert summary["totalTokensCoverage"] == 0.5
    assert sum(row["requests"] for row in data["trend"]) == 4
    assert sum(row["requests"] for row in data["modelDistribution"]) == 4
    assert data["coverage"]["excludedUnknownCustomers"] == 1
    assert data["comparison"]["state"] == "not_collected"
    assert data["comparison"]["reason"] == "PREVIOUS_NOT_COLLECTED"
    assert data["comparison"]["summary"] is None
    assert not {"finance", "cash", "balance", "credit"}.intersection(data)


def test_published_empty_snapshot_has_zero_requests_but_no_fake_rates(
    monkeypatch,
):
    graph = make_prepared()
    original = SyntheticClient.page_calls

    def empty(self, start, end, page):
        payload = original(self, start, end, page)
        return {**payload, "items": [], "total": 0, "next_page": None}

    monkeypatch.setattr(SyntheticClient, "page_calls", empty)
    publish(graph)
    user, connection, *_ = graph
    summary = query_dashboard(connection, user)["summary"]
    assert summary["requests"] == 0
    assert summary["successRate"] is None
    assert summary["inputTokens"] is None
    assert summary["inputTokensCoverage"] is None


def test_missing_tokens_stay_unknown_rather_than_becoming_zero(monkeypatch):
    graph = make_prepared()
    original = SyntheticClient.page_calls

    def missing(self, start, end, page):
        payload = original(self, start, end, page)
        for row in payload["items"]:
            row["input_tokens"] = row["output_tokens"] = None
        return payload

    monkeypatch.setattr(SyntheticClient, "page_calls", missing)
    publish(graph)
    user, connection, *_ = graph
    summary = query_dashboard(connection, user)["summary"]
    assert summary["requests"] == 4
    assert summary["inputTokens"] is None
    assert summary["inputTokensSampleCount"] == 0
    assert summary["inputTokensCoverage"] == 0
    assert summary["totalTokens"] is None


def test_fixed_versions_do_not_change_when_new_data_is_published(monkeypatch):
    graph = make_prepared()
    first = publish(graph)
    original = SyntheticClient.page_calls

    def changed(self, start, end, page):
        payload = original(self, start, end, page)
        if page == 1:
            payload["items"][0]["input_tokens"] = 900
        return payload

    monkeypatch.setattr(SyntheticClient, "page_calls", changed)
    second = publish(graph, "second-version")
    user, connection, *_ = graph
    assert (
        query_dashboard(connection, user, first.pk)["summary"]["inputTokens"]
        == 130
    )
    latest = query_dashboard(connection, user)
    assert latest["dataVersion"] == str(second.pk)
    assert latest["summary"]["inputTokens"] == 930


def test_failed_new_sync_preserves_the_latest_successful_version(monkeypatch):
    graph = make_prepared()
    version = publish(graph)
    monkeypatch.setattr(
        SyntheticClient,
        "page_calls",
        Mock(side_effect=AgioneOpsError("SOURCE_INCOMPLETE_PAGING")),
    )
    user, connection, _, start, end = graph
    run, _ = submit_sync(
        connection, user, start, end, "Asia/Shanghai", "failed-new-version"
    )
    assert execute_sync(run.pk)["status"] == "failed"
    assert query_dashboard(connection, user)["dataVersion"] == str(version.pk)


def test_versions_cannot_cross_connections_even_when_ids_match():
    first = make_prepared()
    second = make_prepared()
    first_version = publish(first)
    second_version = publish(second)
    assert first_version.pk != second_version.pk
    with pytest.raises(NotFound):
        query_dashboard(first[1], first[0], second_version.pk)
    assert query_dashboard(first[1], first[0])["summary"]["requests"] == 4
    assert query_dashboard(second[1], second[0])["summary"]["requests"] == 4


def test_current_grant_is_required_for_old_published_data():
    graph = make_prepared()
    version = publish(graph)
    user, connection, grant, *_ = graph
    grant.can_view = False
    grant.save()
    with pytest.raises(NotFound):
        query_dashboard(connection, user, version.pk)


def test_queries_never_fetch_or_synchronize_the_source(monkeypatch, settings):
    graph = make_prepared()
    publish(graph)
    settings.AGIONE_OPS_SYNTHETIC_ENABLED = False
    monkeypatch.setattr(
        SyntheticClient,
        "identity",
        Mock(side_effect=AssertionError("Query contacted source")),
    )
    monkeypatch.setattr(
        SyntheticClient,
        "page_calls",
        Mock(side_effect=AssertionError("Query started collection")),
    )
    assert query_dashboard(graph[1], graph[0])["state"] == "ready"


def test_query_windows_and_unknown_versions_fail_closed():
    graph = make_prepared()
    version = publish(graph)
    user, connection, _, start, end = graph
    with pytest.raises(AgioneOpsError, match="WINDOW_PAIR_REQUIRED"):
        query_dashboard(connection, user, window_start=start)
    with pytest.raises(AgioneOpsError, match="WINDOW_VERSION_MISMATCH"):
        query_dashboard(
            connection, user, version.pk, start + timedelta(seconds=1), end
        )
    with pytest.raises(NotFound):
        query_dashboard(connection, user, "invalid-uuid")
    absent = query_dashboard(
        connection,
        user,
        window_start=start - timedelta(days=1),
        window_end=start,
    )
    assert absent["state"] == "not_collected"
