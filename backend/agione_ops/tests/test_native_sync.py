"""Fake-only native collection, resumability and local-query regressions."""

import json
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.utils import timezone

from agione_ops.client import AgioneOpsError
from agione_ops.models import (
    ConnectionGrant, DatasetVersion, SourceConnection, SyncRun,
)
from agione_ops.native_queries import query_live_operation
from agione_ops.native_snapshot_queries import (
    query_native_snapshot, validate_native_snapshot,
)
from agione_ops.native_sync import execute_native_sync
from agione_ops.native_sync_models import (
    NativePublishedSnapshot, NativeStagedRecord, NativeSyncShard,
)
from agione_ops.sync import LEASE_SECONDS, execute_sync, submit_sync
from agione_ops.tasks import run_sync

pytestmark = pytest.mark.django_db
ZONE = ZoneInfo("Asia/Shanghai")


@pytest.fixture
def native(settings, monkeypatch):
    settings.AGIONE_OPS_NATIVE_ENABLED = True
    settings.AGIONE_OPS_FINANCE_REFRESH_ON_SYNC = True
    settings.AGIONE_OPS_ALLOWED_ENDPOINT_HOSTS = ["fake-native.example"]
    settings.AGIONE_OPS_NATIVE_CONCURRENCY = 3
    settings.AGIONE_OPS_NATIVE_SHARD_CONCURRENCY = 1
    settings.AGIONE_OPS_NATIVE_OVERLAP_SECONDS = 86400
    monkeypatch.setattr(run_sync, "apply_async", Mock())
    user = get_user_model().objects.create_user(username=str(uuid.uuid4()))
    user.user_permissions.add(*Permission.objects.filter(
        content_type__app_label="agione_ops",
        codename__in=["run_sync", "view_business"],
    ))
    connection = SourceConnection.objects.create(
        name="Fake native", platform="pro", principal_kind="provider",
        source_kind="native", endpoint="https://fake-native.example",
        expected_tenant_id="100", enabled=True, created_by=user,
    )
    grant = ConnectionGrant.objects.create(
        connection=connection, user=user, can_view=True, can_sync=True,
    )
    connection.refresh_from_db()
    start = timezone.now().astimezone(ZONE).replace(
        hour=0, minute=0, second=0, microsecond=0,
    ) - timedelta(days=4)
    state = {
        "user": user, "connection": connection, "grant": grant,
        "start": start, "end": start + timedelta(days=2),
        "calls": [], "clients": [], "fail_day": None,
        "mutation": None, "dense": False,
        "rows": [{
            "id": str(1000 + day), "customerTenantId": "200",
            "modelId": "300", "userId": "400", "status": 1,
            "createTime": int((start + timedelta(
                days=day, hours=1,
            )).timestamp() * 1000),
            "promptTokens": 10, "completionTokens": 5, "totalTokens": 15,
            "prompt": "PRIVATE", "Authorization": "PRIVATE",
        } for day in range(2)],
    }

    class FakeClient:
        def __init__(self, source):
            self.connection = source
            self.closed = False
            state["clients"].append(self)

        def identity(self):
            return {
                "tenant_id": "100", "platform": "pro",
                "principal_kind": "provider", "role_state": "verified",
            }

        def get(self, path, params=None):
            state["calls"].append((path, deepcopy(params)))
            if path.endswith("provider-customers"):
                return {"total": 1, "data": [{
                    "customerTenantId": "200", "customerName": "Business",
                    "contact": "PRIVATE",
                }]}
            if path.endswith("models/options"):
                return [{"modelId": "300", "modelName": "Model"}]
            assert path.endswith("call-logs")
            at = datetime.strptime(
                params["startTime"], "%Y-%m-%d %H:%M:%S",
            ).replace(tzinfo=ZONE)
            stop = datetime.strptime(
                params["endTime"], "%Y-%m-%d %H:%M:%S",
            ).replace(tzinfo=ZONE)
            if state["mutation"]:
                state["mutation"]()
            if state["fail_day"] == at.date():
                raise AgioneOpsError("SOURCE_TIMEOUT", status_code=504)
            if state["dense"] and stop - at > timedelta(hours=1):
                return {"total": 50000, "records": []}
            rows = [deepcopy(x) for x in state["rows"] if (
                at.timestamp() * 1000 <= x["createTime"]
                <= stop.timestamp() * 1000
            )]
            offset = (params["current"] - 1) * params["size"]
            return {
                "total": len(rows),
                "records": rows[offset:offset + params["size"]],
            }

        def close(self):
            self.closed = True

    state["factory"] = FakeClient
    return state


def submit(native, key=None):
    return submit_sync(
        native["connection"], native["user"], native["start"], native["end"],
        "Asia/Shanghai", key or str(uuid.uuid4()),
    )[0]


def collect(native, run=None):
    run = run or submit(native)
    return run, execute_native_sync(run.pk, client_factory=native["factory"])


def test_native_publish_is_atomic_normalized_and_redelivery_safe(native):
    run, result = collect(native)
    assert result["status"] == "succeeded"
    snapshot = NativePublishedSnapshot.objects.get(version__run=run)
    assert snapshot.version.coverage["pagingComplete"] is True
    assert len(snapshot.data["rows"]) == 2
    assert "PRIVATE" not in json.dumps(snapshot.data)
    assert NativeStagedRecord.objects.count() == 2
    assert all(client.closed for client in native["clients"])
    assert execute_sync(str(run.pk))["status"] == "succeeded"
    assert DatasetVersion.objects.count() == 1
    native["connection"].refresh_from_db()
    assert native["connection"].active_run_id is None


def test_dashboard_selects_snapshot_covering_requested_dates(native):
    from agione_ops.queries import query_dashboard

    start, end = native["start"], native["end"]
    _, first = collect(native)
    native["start"] = start - timedelta(days=3)
    native["end"] = start - timedelta(days=1)
    _, second = collect(native)
    assert second["status"] == "succeeded"
    result = query_dashboard(
        native["connection"], native["user"], window_start=start,
        window_end=end,
    )
    assert str(result["dataVersion"]) == str(first["dataVersion"])
    missing = query_dashboard(
        native["connection"], native["user"],
        window_start=start - timedelta(days=10), window_end=end,
    )
    assert missing["state"] == "ready"
    assert missing["coverage"]["partial"] is True
    assert missing["coverage"]["missingDays"]
    assert missing["summary"]["requestCount"] == 2



def test_dashboard_combines_complete_snapshots_without_upstream(native):
    from agione_ops.queries import query_dashboard
    from agione_ops.snapshot_queries import query_operation

    start = native["start"]
    for day in (2, 3):
        row = deepcopy(native["rows"][0])
        row["id"] = str(1000 + day)
        at = start + timedelta(days=day, hours=1)
        row["createTime"] = int(at.timestamp() * 1000)
        native["rows"].append(row)
    collect(native)
    native["start"] = start + timedelta(days=2)
    native["end"] = start + timedelta(days=4)
    collect(native)
    before = len(native["calls"])
    frame = query_dashboard(native["connection"], native["user"],
                            window_start=start, window_end=native["end"])
    assert frame["state"] == "ready"
    assert frame["snapshotResponse"]["data"]["summary"]["requestCount"] == 4
    query = {"operation": "analysis", "data_version": frame["dataVersion"],
             "window": {"start": start, "end_exclusive": native["end"],
                        "timezone": "Asia/Shanghai"},
             "payload": {"group_by": ["customerTenantId"],
                         "metrics": ["requestCount"]}}
    result = query_operation(native["connection"], native["user"], query)
    assert result["data"]["rows"][0]["metrics"]["requestCount"] == 4
    assert len(native["calls"]) == before
    native["rows"].pop()
    collect(native)
    pinned = query_operation(native["connection"], native["user"], query)
    assert pinned["data"]["rows"][0]["metrics"]["requestCount"] == 4

def test_daily_finance_projection_passes_snapshot_validation(native):
    from agione_ops.native_finance import aggregate_finance
    from agione_ops.native_sync import digest, validate_snapshot_data

    _, result = collect(native)
    snapshot = NativePublishedSnapshot.objects.get(
        version_id=result["dataVersion"],
    )
    day = native["start"].date().isoformat()
    finance = aggregate_finance([("200", [], {
        "currentCycle": day[:7],
        "trend": [{"date": day, "consumedCredit": "2.50",
                   "topUpCredit": "10"}],
    })], 1, day[:7], timezone.now().isoformat())
    finance["mode"] = "snapshot"
    data = {**snapshot.data, "finance": finance}
    validate_snapshot_data(data, digest(data))


def test_native_submit_is_uuid_only_no_source_and_single_inflight(native):
    run = submit(native, "same")
    again = submit(native, "same")
    assert again.pk == run.pk
    assert not native["calls"] and not native["clients"]
    with pytest.raises(AgioneOpsError, match="CONNECTION_BUSY"):
        submit(native, "different")


def test_failed_shard_alone_retries_and_does_not_expose_partial_version(native):
    native["fail_day"] = (native["start"] + timedelta(days=1)).date()
    run, result = collect(native)
    assert result["status"] == "retrying"
    assert not DatasetVersion.objects.exists()
    assert NativeSyncShard.objects.filter(status="succeeded").count() == 1
    assert NativeSyncShard.objects.filter(status="failed").count() == 1
    before = len(native["calls"])
    native["fail_day"] = None
    SourceConnection.objects.filter(pk=native["connection"].pk).update(
        lease_expires_at=timezone.now() + timedelta(seconds=LEASE_SECONDS),
    )
    _, result = collect(native, run)
    assert result["status"] == "succeeded"
    log_calls = [p for path, p in native["calls"][before:]
                 if path.endswith("call-logs")]
    assert len(log_calls) == 1
    assert log_calls[0]["startTime"].startswith(str(
        (native["start"] + timedelta(days=1)).date(),
    ))
    assert NativeStagedRecord.objects.count() == 2


def test_oversized_days_split_to_hours_and_publish_once(native, settings):
    native["dense"] = True
    settings.AGIONE_OPS_NATIVE_SHARD_MAX_PAGES = 1
    _, result = collect(native)
    assert result["status"] == "succeeded"
    assert NativeSyncShard.objects.filter(status="split").count() == 2
    assert NativeSyncShard.objects.filter(status="succeeded").count() == 48
    assert NativeStagedRecord.objects.count() == 2


@pytest.mark.parametrize("mutation", ["inactive", "credential", "grant"])
def test_fresh_authority_or_epoch_change_cannot_publish(native, mutation):
    def change():
        native["mutation"] = None
        if mutation == "inactive":
            get_user_model().objects.filter(pk=native["user"].pk).update(
                is_active=False,
            )
        elif mutation == "credential":
            SourceConnection.objects.filter(pk=native["connection"].pk).update(
                credential_version=2,
            )
        else:
            native["grant"].can_sync = False
            native["grant"].save()

    native["mutation"] = change
    _, result = collect(native)
    assert result["status"] == "revoked"
    assert not DatasetVersion.objects.exists()
    assert not NativePublishedSnapshot.objects.exists()


def test_publication_insert_failure_rolls_back_dataset_version(native, monkeypatch):
    def broken(**kwargs):
        raise RuntimeError("fake publication failure")

    monkeypatch.setattr(NativePublishedSnapshot.objects, "create", broken)
    _, result = collect(native)
    assert result["status"] == "failed"
    assert not DatasetVersion.objects.exists()
    assert not NativePublishedSnapshot.objects.exists()




def test_two_daily_shards_are_fetched_concurrently(native, settings):
    from threading import Barrier

    settings.AGIONE_OPS_NATIVE_SHARD_CONCURRENCY = 2
    barrier = Barrier(2, timeout=3)
    native["mutation"] = barrier.wait
    _, result = collect(native)
    assert result["status"] == "succeeded"
    snapshot = NativePublishedSnapshot.objects.get(
        version_id=result["dataVersion"],
    )
    assert len(snapshot.data["rows"]) == 2

def test_deadline_allows_new_run_to_reuse_completed_shard(native, monkeypatch):
    from types import SimpleNamespace
    from agione_ops import native_sync

    clock = [0]
    monkeypatch.setattr(native_sync, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    calls = [0]
    def expire_on_second_day():
        calls[0] += 1
        if calls[0] == 2:
            clock[0] = 121
    native["mutation"] = expire_on_second_day
    run, result = collect(native)
    assert result["status"] == "failed"
    run.refresh_from_db()
    assert run.error_code == "NATIVE_SYNC_DEADLINE"
    assert run.native_shards.filter(status="succeeded").count() == 1
    clock[0] = 0
    native["mutation"] = None
    before = len(native["calls"])
    _, result = collect(native)
    assert result["status"] == "succeeded"
    logs = [p for path, p in native["calls"][before:]
            if path.endswith("call-logs")]
    assert len(logs) == 1
    assert len(NativePublishedSnapshot.objects.get(
        version_id=result["dataVersion"],
    ).data["rows"]) == 2

def test_overlap_incremental_keeps_old_revision_and_deduplicates(native):
    _, first = collect(native)
    old = NativePublishedSnapshot.objects.get(version_id=first["dataVersion"])
    native["rows"][1]["promptTokens"] = 22
    before = len(native["calls"])
    _, second = collect(native)
    assert second["status"] == "succeeded"
    newest = NativePublishedSnapshot.objects.get(
        version_id=second["dataVersion"],
    )
    assert [row["input_tokens"] for row in old.data["rows"]] == [10, 10]
    assert [row["input_tokens"] for row in newest.data["rows"]] == [10, 22]
    logs = [p for path, p in native["calls"][before:]
            if path.endswith("call-logs")]
    assert len(logs) == 1
    assert len({row["record_id"] for row in newest.data["rows"]}) == 2



def test_incremental_reuses_multiple_complete_snapshots(native):
    start = native["start"]
    for day in (2, 3):
        row = deepcopy(native["rows"][0])
        row["id"] = str(1000 + day)
        at = start + timedelta(days=day, hours=1)
        row["createTime"] = int(at.timestamp() * 1000)
        native["rows"].append(row)
    _, first = collect(native)
    assert first["status"] == "succeeded"
    native["start"] = start + timedelta(days=2)
    native["end"] = start + timedelta(days=4)
    _, second = collect(native)
    assert second["status"] == "succeeded"
    native["start"] = start
    before = len(native["calls"])
    _, combined = collect(native)
    assert combined["status"] == "succeeded"
    snapshot = NativePublishedSnapshot.objects.get(
        version_id=combined["dataVersion"],
    )
    assert len(snapshot.data["rows"]) == 4
    logs = [p for path, p in native["calls"][before:]
            if path.endswith("call-logs")]
    assert len(logs) == 1

def test_http_compatibility_query_never_constructs_a_native_client(native):
    factory = Mock(side_effect=AssertionError("source IO forbidden"))
    result = query_live_operation(
        native["connection"], native["user"], {"operation": "dashboard"},
        client_factory=factory,
    )
    assert result["state"] == "not_collected"
    assert result["dataVersion"] is None
    assert result["provenance"]["mode"] == "snapshot"
    assert result["provenance"]["kind"] == "native_snapshot"
    assert result["capabilities"]["directUpstream"] is False
    factory.assert_not_called()


@pytest.mark.parametrize("operation", [
    "dashboard", "trend", "analysis", "customers", "profile", "schema",
    "requests", "evidence", "finance",
])
def test_local_published_operation_dtos(native, operation):
    _, publication = collect(native)
    before = len(native["calls"])
    payload = {
        "profile": {"customerId": "200"},
        "evidence": {"evidenceId": "1000"},
    }.get(operation, {})
    result = query_native_snapshot(native["connection"], native["user"], {
        "operation": operation, "payload": payload,
        "data_version": publication["dataVersion"],
    })
    assert result["state"] == "ready"
    assert result["dataVersion"] == publication["dataVersion"]
    assert result["data"] is not None
    assert len(native["calls"]) == before
    if operation == "finance":
        assert result["data"]["reason"] == "OPERATOR_VIEW_REQUIRED"
    if operation == "profile":
        assert result["data"]["value"]["finance"]["reason"] == (
            "NATIVE_FINANCE_NOT_COLLECTED"
        )


def test_cache_hit_validator_reloads_user_grant_and_small_fields(native):
    _, publication = collect(native)
    query = {"operation": "dashboard", "data_version": publication["dataVersion"]}
    signature = validate_native_snapshot(
        native["connection"], native["user"], query,
    )
    assert signature["state"] == "ready"
    assert signature["contentDigest"]
    native["grant"].can_view = False
    native["grant"].save()
    with pytest.raises(Exception):
        validate_native_snapshot(
            native["connection"], native["user"], query, signature,
        )


def test_historical_epoch_is_not_readable_and_missing_version_is_404(native):
    _, publication = collect(native)
    SourceConnection.objects.filter(pk=native["connection"].pk).update(
        credential_version=2,
    )
    with pytest.raises(AgioneOpsError, match="SNAPSHOT_EPOCH_CHANGED"):
        query_native_snapshot(native["connection"], native["user"], {
            "operation": "dashboard", "data_version": publication["dataVersion"],
        })
    result = query_native_snapshot(
        native["connection"], native["user"], {"operation": "dashboard"},
    )
    assert result["state"] == "not_collected"
    with pytest.raises(AgioneOpsError) as error:
        query_native_snapshot(native["connection"], native["user"], {
            "operation": "dashboard", "data_version": str(uuid.uuid4()),
        })
    assert error.value.status_code == 404


def test_integrity_failure_is_stable_and_never_returns_snapshot(native, monkeypatch):
    collect(native)
    from agione_ops import native_snapshot_queries

    def corrupted(*args):
        raise ValidationError("fake corrupt normalized content")

    monkeypatch.setattr(native_snapshot_queries, "validate_snapshot_data", corrupted)
    with pytest.raises(AgioneOpsError, match="SNAPSHOT_CONTENT_INVALID"):
        query_native_snapshot(
            native["connection"], native["user"], {"operation": "dashboard"},
        )


def test_independent_finance_publishes_without_blocking_and_fences_access(
    native, settings, monkeypatch,
):
    from agione_ops.native_finance import unavailable_finance
    from agione_ops.native_finance_refresh import execute_finance, finance_for
    from agione_ops.native_sync_models import NativeFinanceProjection
    from agione_ops.snapshot_queries import query_operation

    settings.AGIONE_OPS_FINANCE_REFRESH_ON_SYNC = False
    operator = SourceConnection.objects.create(
        name="Operator", platform="pro", principal_kind="operator",
        source_kind="native", endpoint="https://fake-native.example",
        expected_tenant_id="101", enabled=True, created_by=native["user"],
    )
    grant = ConnectionGrant.objects.create(
        connection=operator, user=native["user"], can_view=True,
    )
    operator.refresh_from_db()
    finance = unavailable_finance("TEST_FINANCE")
    finance["mode"] = "snapshot"
    finance["fetchedAt"] = timezone.now().isoformat()
    source_read = Mock(return_value=finance)
    monkeypatch.setattr(
        "agione_ops.native_queries.collect_native_finance", source_read,
    )
    run, result = collect(native)
    assert result["status"] == "succeeded"
    source_read.assert_not_called()
    row = NativeFinanceProjection.objects.get(run=run)
    assert row.status == "queued"
    connection = SourceConnection.objects.get(pk=native["connection"].pk)
    query = {"operation": "finance", "data_version": result["dataVersion"],
             "payload": {}}
    before = query_operation(connection, native["user"], query)
    assert before["data"]["refreshState"] == "queued"
    execute_finance(row.pk, str(run.pk))
    row.refresh_from_db()
    assert row.status == "ready"
    after = query_operation(connection, native["user"], query)
    assert after["data"]["refreshState"] == "ready"
    assert after["data"]["reason"] == "TEST_FINANCE"
    source_read.assert_called_once()
    other = get_user_model().objects.create_user(username=str(uuid.uuid4()))
    other.user_permissions.add(*Permission.objects.filter(
        content_type__app_label="agione_ops", codename="view_business",
    ))
    ConnectionGrant.objects.create(
        connection=operator, user=other, can_view=True,
    )
    separate, version = finance_for(connection, other)
    assert version is None
    assert separate["reason"] == "NATIVE_FINANCE_NOT_COLLECTED"
    grant.can_view = False
    grant.save()
    denied, version = finance_for(connection, native["user"])
    assert version is None
    assert denied["reason"] == "NATIVE_FINANCE_NOT_COLLECTED"


def test_independent_finance_failure_keeps_last_result(native, settings, monkeypatch):
    from agione_ops.native_finance import unavailable_finance
    from agione_ops.native_finance_refresh import execute_finance
    from agione_ops.native_sync_models import NativeFinanceProjection

    settings.AGIONE_OPS_FINANCE_REFRESH_ON_SYNC = False
    operator = SourceConnection.objects.create(
        name="Operator", platform="pro", principal_kind="operator",
        source_kind="native", endpoint="https://fake-native.example",
        expected_tenant_id="101", enabled=True, created_by=native["user"],
    )
    ConnectionGrant.objects.create(
        connection=operator, user=native["user"], can_view=True,
    )
    run, result = collect(native)
    assert result["status"] == "succeeded"
    row = NativeFinanceProjection.objects.get(run=run)
    old = unavailable_finance("LAST_GOOD")
    row.data = old
    row.save(update_fields=["data", "updated_at"])
    monkeypatch.setattr(
        "agione_ops.native_queries.collect_native_finance",
        Mock(side_effect=AgioneOpsError("SOURCE_TIMEOUT", status_code=504)),
    )
    execute_finance(row.pk, str(run.pk))
    row.refresh_from_db()
    assert row.status == "failed"
    assert row.data == old
    assert row.error_code == "FINANCE_REFRESH_FAILED"


def test_independent_finance_deduplicates_and_rejects_stale_task(
    native, settings, monkeypatch,
):
    from agione_ops.native_finance_refresh import execute_finance, schedule_finance
    from agione_ops.native_sync_models import NativeFinanceProjection

    settings.AGIONE_OPS_FINANCE_REFRESH_ON_SYNC = False
    operator = SourceConnection.objects.create(
        name="Operator", platform="pro", principal_kind="operator",
        source_kind="native", endpoint="https://fake-native.example",
        expected_tenant_id="101", enabled=True, created_by=native["user"],
    )
    ConnectionGrant.objects.create(
        connection=operator, user=native["user"], can_view=True,
    )
    run, result = collect(native)
    assert result["status"] == "succeeded"
    row = NativeFinanceProjection.objects.get(run=run)
    schedule_finance(run.pk)
    assert NativeFinanceProjection.objects.count() == 1
    source_read = Mock()
    monkeypatch.setattr(
        "agione_ops.native_queries.collect_native_finance", source_read,
    )
    execute_finance(row.pk, str(uuid.uuid4()))
    row.refresh_from_db()
    assert row.status == "queued"
    source_read.assert_not_called()


def test_finance_refresh_endpoint_uses_authorized_projection(native, settings):
    from rest_framework.test import APIClient

    settings.AGIONE_OPS_FINANCE_REFRESH_ON_SYNC = False
    operator = SourceConnection.objects.create(
        name="Operator", platform="pro", principal_kind="operator",
        source_kind="native", endpoint="https://fake-native.example",
        expected_tenant_id="101", enabled=True, created_by=native["user"],
    )
    ConnectionGrant.objects.create(
        connection=operator, user=native["user"], can_view=True,
    )
    collect(native)
    client = APIClient()
    client.force_authenticate(native["user"])
    response = client.post(
        f'/api/v1/agione-ops/connections/{native["connection"].pk}/finance/refresh/',
        {}, format="json",
    )
    assert response.status_code == 202
    assert response.data["data"]["state"] == "queued"


def test_finance_dispatch_waits_for_publication_commit(
    native, settings, monkeypatch, django_capture_on_commit_callbacks,
):
    from agione_ops.tasks import refresh_native_finance

    settings.AGIONE_OPS_FINANCE_REFRESH_ON_SYNC = False
    operator = SourceConnection.objects.create(
        name="Operator", platform="pro", principal_kind="operator",
        source_kind="native", endpoint="https://fake-native.example",
        expected_tenant_id="101", enabled=True, created_by=native["user"],
    )
    ConnectionGrant.objects.create(
        connection=operator, user=native["user"], can_view=True,
    )
    run = submit(native)
    dispatch = Mock()
    monkeypatch.setattr(refresh_native_finance, "delay", dispatch)
    with django_capture_on_commit_callbacks(execute=True):
        _, result = collect(native, run)
        assert result["status"] == "succeeded"
        dispatch.assert_not_called()
    dispatch.assert_called_once()
    assert dispatch.call_args.args[1] == str(run.pk)


def test_month_end_shard_clips_query_and_checks_precision():
    from types import SimpleNamespace
    from agione_ops.native_sync import _read_shard

    shard = SimpleNamespace(
        window_start=datetime(2026, 7, 31, tzinfo=ZONE),
        window_end=datetime(2026, 8, 1, tzinfo=ZONE),
    )
    client = Mock()
    client.get.return_value = {"records": [], "total": 0}
    assert _read_shard(client, shard, 1, lambda _: None) == ([], 1)
    assert client.get.call_args.args[1]["endTime"] == "2026-07-31 23:59:59"
    client.get.return_value = {
        "records": [{"id": "1", "createTime": 1234567890123}], "total": 1,
    }
    with pytest.raises(AgioneOpsError) as exc:
        _read_shard(client, shard, 1, lambda _: None)
    assert exc.value.code == "SOURCE_TIME_PRECISION_CHANGED"


def test_recent_prefetch_uses_authorized_grant(native, monkeypatch):
    from agione_ops import tasks

    SourceConnection.objects.filter(pk=native['connection'].pk).update(
        verified_at=timezone.now(), verified_tenant_id='100',
    )
    dispatch = Mock()
    monkeypatch.setattr(tasks, 'submit_recent_sync', dispatch)
    tasks.prefetch_recent_native_data()
    assert dispatch.call_count == 1
    assert dispatch.call_args.args[0].pk == native['connection'].pk
    assert dispatch.call_args.args[1].pk == native['user'].pk
    native['grant'].can_sync = False
    native['grant'].save()
    tasks.prefetch_recent_native_data()
    assert dispatch.call_count == 1


def test_partial_window_reports_missing_shanghai_dates(native):
    from agione_ops.queries import query_dashboard

    start = native['start']
    collect(native)
    frame = query_dashboard(
        native['connection'], native['user'],
        window_start=start - timedelta(days=1), window_end=native['end'],
    )
    assert frame['coverage']['partial'] is True
    assert frame['coverage']['missingDays'] == [
        (start - timedelta(days=1)).date().isoformat(),
    ]
    assert frame['snapshotResponse']['data']['comparison']['state'] != 'READY'


def test_cleanup_removes_only_old_successful_staging(native):
    from agione_ops.tasks import cleanup_native_staging

    run, result = collect(native)
    assert result['status'] == 'succeeded'
    snapshot = NativePublishedSnapshot.objects.get(version_id=result['dataVersion'])
    SyncRun.objects.filter(pk=run.pk).update(
        finished_at=timezone.now() - timedelta(days=31),
    )
    assert cleanup_native_staging() == 2
    assert not NativeStagedRecord.objects.filter(run=run).exists()
    snapshot.refresh_from_db()
    assert len(snapshot.data['rows']) == 2


def test_dashboard_compares_previous_split_snapshots(native):
    from agione_ops.snapshot_queries import query_operation

    start = native['start']
    _, current = collect(native)
    for offset in (-2, -1):
        row = deepcopy(native['rows'][0])
        row['id'] = str(2000 - offset)
        row['createTime'] = int((start + timedelta(days=offset, hours=1)).timestamp() * 1000)
        native['rows'].append(row)
        native['start'] = start + timedelta(days=offset)
        native['end'] = native['start'] + timedelta(days=1)
        _, prior = collect(native)
        assert prior['status'] == 'succeeded'
    result = query_operation(native['connection'], native['user'], {
        'operation': 'dashboard', 'data_version': current['dataVersion'],
        'payload': {},
    })
    assert result['data']['comparison']['state'] == 'READY'
    assert result['data']['comparison']['summary']['requestCount'] == 2


def test_retention_preserves_active_and_latest_snapshots(native):
    from django.db import models
    from agione_ops.models import DatasetVersion
    from agione_ops.native_sync_models import NativeSnapshotLease
    from agione_ops.snapshot_queries import query_operation
    from agione_ops.tasks import cleanup_native_snapshots

    _, first = collect(native)
    _, second = collect(native)
    old = first['dataVersion']
    models.QuerySet(model=DatasetVersion).filter(pk=old).update(
        published_at=timezone.now() - timedelta(days=91),
    )
    query = {'operation': 'dashboard', 'data_version': old, 'payload': {}}
    query_operation(native['connection'], native['user'], query)
    assert NativeSnapshotLease.objects.filter(version_id=old).exists()
    assert cleanup_native_snapshots() == 0
    NativeSnapshotLease.objects.filter(version_id=old).update(
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    assert cleanup_native_snapshots() == 1
    assert DatasetVersion.objects.filter(pk=old).exists()
    assert NativePublishedSnapshot.objects.filter(version_id=second['dataVersion']).exists()
    with pytest.raises(AgioneOpsError, match='DATA_VERSION_EXPIRED'):
        query_operation(native['connection'], native['user'], query)


def test_comparison_cache_refreshes_after_prior_snapshot_expires(native):
    from django.db import models
    from agione_ops.models import DatasetVersion
    from agione_ops.native_sync_models import NativeSnapshotLease
    from agione_ops.snapshot_queries import query_operation
    from agione_ops.tasks import cleanup_native_snapshots

    start = native['start']
    _, current = collect(native)
    native['start'] = start - timedelta(days=2)
    native['end'] = start
    _, prior = collect(native)
    models.QuerySet(model=DatasetVersion).filter(pk=prior['dataVersion']).update(
        published_at=timezone.now() - timedelta(days=91),
    )
    query = {'operation': 'dashboard', 'data_version': current['dataVersion'],
             'payload': {}}
    before = query_operation(native['connection'], native['user'], query)
    assert before['data']['comparison']['state'] == 'READY'
    NativeSnapshotLease.objects.filter(version_id=prior['dataVersion']).update(
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    assert cleanup_native_snapshots() == 1
    after = query_operation(native['connection'], native['user'], query)
    assert after['data']['comparison']['state'] == 'UNAVAILABLE'
