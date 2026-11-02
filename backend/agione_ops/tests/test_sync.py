"""Synthetic-only synchronization regression tests with no real transport."""

import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.utils import timezone

from agione_ops.client import (
    SYNTHETIC_TENANT_ID,
    AgioneOpsError,
    SyntheticClient,
    get_client,
)
from agione_ops.models import (
    CallFact,
    ConnectionGrant,
    DatasetVersion,
    SourceConnection,
    SyncRun,
    VersionCall,
)
from agione_ops.sync import (
    _checkpoint,
    _claim,
    _collect,
    _finish_failure,
    _publish,
    execute_sync,
    submit_sync,
    validate_window,
    verify_connection,
)
from agione_ops.tasks import run_sync

pytestmark = pytest.mark.django_db


def make_prepared():
    """Create only synthetic permissions, identity and an authorized source."""

    user = get_user_model().objects.create_user(
        username=f"sync-{uuid.uuid4()}"
    )
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="agione_ops",
            codename__in=["manage_connections", "run_sync", "view_business"],
        )
    )
    connection = SourceConnection.objects.create(
        name="Synthetic connection",
        platform="pro",
        principal_kind="provider",
        expected_tenant_id=SYNTHETIC_TENANT_ID,
        enabled=True,
        created_by=user,
    )
    grant = ConnectionGrant.objects.create(
        connection=connection, user=user, can_view=True, can_sync=True
    )
    verify_connection(connection, user)
    connection.refresh_from_db()
    start = timezone.now().replace(microsecond=0) - timedelta(days=3)
    return user, connection, grant, start, start + timedelta(days=1)


@pytest.fixture
def prepared():
    return make_prepared()


@pytest.fixture(autouse=True)
def no_broker(monkeypatch):
    """Never use a real Celery transport, even when commit callbacks run."""

    dispatch = Mock(return_value=SimpleNamespace(id="synthetic-celery-id"))
    monkeypatch.setattr(run_sync, "apply_async", dispatch)
    return dispatch


def submit(prepared, key="synthetic-key"):
    user, connection, _grant, start, end = prepared
    return submit_sync(connection, user, start, end, "Asia/Shanghai", key)


def test_explicit_verify_and_complete_publication(prepared):
    run, created = submit(prepared)
    assert created
    assert execute_sync(run.pk)["status"] == "succeeded"
    run.refresh_from_db()
    assert run.status == "succeeded"
    assert run.processed_count == run.total_count == 5
    assert CallFact.objects.count() == 4
    assert VersionCall.objects.count() == 4
    version = DatasetVersion.objects.get(run=run)
    assert version.coverage["excludedUnknownCustomers"] == 1
    assert version.coverage["pagingComplete"] is True
    assert all(
        isinstance(row.upstream_record_id, str)
        for row in CallFact.objects.all()
    )
    prepared[1].refresh_from_db()
    assert prepared[1].active_run_id is None
    assert prepared[1].lease_token is None
    assert execute_sync(run.pk)["status"] == "succeeded"
    assert DatasetVersion.objects.count() == 1


def test_idempotency_is_per_actor_and_window(prepared):
    run, created = submit(prepared)
    duplicate, again = submit(prepared)
    assert created and not again and duplicate.pk == run.pk
    user, connection, _, start, end = prepared
    with pytest.raises(AgioneOpsError, match="IDEMPOTENCY_CONFLICT"):
        submit_sync(
            connection,
            user,
            start - timedelta(seconds=1),
            end,
            "Asia/Shanghai",
            run.idempotency_key,
        )
    with pytest.raises(AgioneOpsError, match="CONNECTION_BUSY"):
        submit(prepared, "different-key")
    assert SyncRun.objects.count() == 1


def test_dispatch_happens_after_commit_with_uuid_only(
    prepared, django_capture_on_commit_callbacks, no_broker
):
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        run, _ = submit(prepared)
        no_broker.assert_not_called()
    assert len(callbacks) == 1
    no_broker.assert_called_once_with(
        args=[str(run.pk)], task_id=run.celery_id, retry=False
    )
    assert run.celery_id


def test_dispatch_failure_is_terminal_and_releases_connection(
    prepared, django_capture_on_commit_callbacks, no_broker
):
    no_broker.side_effect = RuntimeError("synthetic dispatch failure")
    with django_capture_on_commit_callbacks(execute=True):
        run, _ = submit(prepared)
    run.refresh_from_db()
    assert run.status == "dispatch_failed"
    assert run.error_code == "DISPATCH_FAILED"
    prepared[1].refresh_from_db()
    assert prepared[1].active_run_id is None


@pytest.mark.parametrize(
    "alter", ["naive", "future", "zero", "too_long", "precision", "zone"]
)
def test_window_validation_rejects_unsupported_input(prepared, alter):
    _, _, _, start, end = prepared
    zone = "Asia/Shanghai"
    if alter == "naive":
        start = start.replace(tzinfo=None)
    elif alter == "future":
        end = timezone.now() + timedelta(days=1)
    elif alter == "zero":
        end = start
    elif alter == "too_long":
        start = end - timedelta(days=32)
    elif alter == "precision":
        start = start.replace(microsecond=1)
    else:
        zone = "UTC"
    with pytest.raises(AgioneOpsError):
        validate_window(start, end, zone)


def test_source_default_disabled_and_real_inputs_rejected(prepared, settings):
    user, connection, _, _, _ = prepared
    settings.AGIONE_OPS_SYNTHETIC_ENABLED = False
    with pytest.raises(AgioneOpsError, match="SYNTHETIC_DISABLED"):
        verify_connection(connection, user)
    settings.AGIONE_OPS_SYNTHETIC_ENABLED = True
    connection.endpoint = "https://not-contacted.invalid"
    with pytest.raises(AgioneOpsError, match="REAL_SOURCE_FORBIDDEN"):
        get_client(connection)
    connection.endpoint = ""
    connection.credential_ciphertext = "synthetic-not-a-real-credential"
    with pytest.raises(AgioneOpsError, match="REAL_CREDENTIALS_FORBIDDEN"):
        get_client(connection)


def test_verify_is_identity_check_not_an_echo(prepared):
    user, connection, _, _, _ = prepared
    connection = SourceConnection.objects.create(
        name="Wrong expected identity",
        platform="pro",
        principal_kind="provider",
        expected_tenant_id="wrong-synthetic-tenant",
        enabled=True,
        created_by=user,
    )
    with pytest.raises(AgioneOpsError, match="SOURCE_IDENTITY_MISMATCH"):
        verify_connection(connection, user)


@pytest.mark.parametrize(
    "failure",
    [
        "duplicate",
        "missing_id",
        "empty",
        "changed_total",
        "wrong_page",
        "range",
        "identity",
        "tokens",
    ],
)
def test_incomplete_or_invalid_pages_never_publish(
    prepared, monkeypatch, failure
):
    original = SyntheticClient.page_calls

    def broken(self, start, end, page):
        payload = original(self, start, end, page)
        if failure == "duplicate" and page == 2:
            payload["items"][0] = original(self, start, end, 1)["items"][0]
        elif failure == "missing_id" and page == 1:
            payload["items"][0].pop("upstream_record_id")
        elif failure == "empty" and page == 1:
            payload["items"] = []
        elif failure == "changed_total" and page == 2:
            payload["total"] += 1
        elif failure == "wrong_page" and page == 1:
            payload["page"] = 2
        elif failure == "range" and page == 1:
            payload["items"][0]["occurred_at"] = end
        elif failure == "identity" and page == 1:
            payload["identity"]["tenant_id"] = "changed-tenant"
        elif failure == "tokens" and page == 1:
            payload["items"][0]["input_tokens"] = -1
        return payload

    monkeypatch.setattr(SyntheticClient, "page_calls", broken)
    run, _ = submit(prepared)
    assert execute_sync(run.pk)["status"] == "failed"
    assert not DatasetVersion.objects.exists()
    assert not CallFact.objects.exists()


@pytest.mark.parametrize(
    "change",
    ["grant", "permission", "disabled", "config", "regrant", "inactive"],
)
def test_authority_rechecked_after_each_source_page(
    prepared, monkeypatch, change
):
    user, connection, grant, _, _ = prepared
    original = SyntheticClient.page_calls

    def revoke(self, start, end, page):
        payload = original(self, start, end, page)
        if page == 1:
            if change == "grant":
                grant.can_sync = False
                grant.save()
            elif change == "permission":
                user.user_permissions.remove(
                    Permission.objects.get(
                        content_type__app_label="agione_ops",
                        codename="run_sync",
                    )
                )
            elif change == "disabled":
                connection.enabled = False
                connection.save()
            elif change == "config":
                connection.name = "Changed configuration"
                connection.save()
            elif change == "regrant":
                grant.delete()
                ConnectionGrant.objects.create(
                    connection=connection,
                    user=user,
                    can_sync=True,
                    can_view=True,
                )
            else:
                user.is_active = False
                user.save(update_fields=["is_active"])
        return payload

    monkeypatch.setattr(SyntheticClient, "page_calls", revoke)
    run, _ = submit(prepared)
    assert execute_sync(run.pk)["status"] == "revoked"
    assert not DatasetVersion.objects.exists()


def test_expired_worker_cannot_renew_or_publish_after_takeover(prepared):
    run, _ = submit(prepared)
    old_run, old_connection, old_token, old_epoch = _claim(run.pk)
    SourceConnection.objects.filter(pk=old_connection.pk).update(
        lease_expires_at=timezone.now() - timedelta(seconds=1)
    )
    fresh_run, fresh_connection, fresh_token, fresh_epoch = _claim(run.pk)
    assert fresh_epoch > old_epoch
    with pytest.raises(AgioneOpsError, match="LEASE_LOST"):
        _checkpoint(run.pk, old_token, old_epoch, "calls")
    with pytest.raises(AgioneOpsError, match="LEASE_LOST"):
        _publish(old_run, old_connection, old_token, old_epoch, [], {})
    assert (
        _finish_failure(
            old_run,
            old_connection,
            old_token,
            old_epoch,
            AgioneOpsError("SOURCE_TIMEOUT"),
        )["status"]
        == "skipped"
    )
    rows, coverage = _collect(
        fresh_run,
        fresh_connection,
        get_client(fresh_connection),
        fresh_token,
        fresh_epoch,
    )
    assert (
        _publish(
            fresh_run,
            fresh_connection,
            fresh_token,
            fresh_epoch,
            rows,
            coverage,
        )["status"]
        == "succeeded"
    )


def test_expired_old_run_cannot_publish_over_a_new_run(prepared):
    run, _ = submit(prepared)
    old_run, connection, token, epoch = _claim(run.pk)
    SourceConnection.objects.filter(pk=connection.pk).update(
        lease_expires_at=timezone.now() - timedelta(seconds=1)
    )
    new_run, _ = submit(prepared, "new-run")
    run.refresh_from_db()
    assert run.status == "interrupted"
    with pytest.raises(AgioneOpsError, match="LEASE_LOST"):
        _publish(old_run, connection, token, epoch, [], {})
    assert execute_sync(new_run.pk)["status"] == "succeeded"


def test_same_facts_are_reused_but_changed_content_is_a_new_revision(
    prepared, monkeypatch
):
    first, _ = submit(prepared)
    execute_sync(first.pk)
    second, _ = submit(prepared, "second")
    execute_sync(second.pk)
    assert CallFact.objects.count() == 4
    assert DatasetVersion.objects.count() == 2
    original = SyntheticClient.page_calls

    def amended(self, start, end, page):
        payload = original(self, start, end, page)
        if page == 1:
            payload["items"][0]["input_tokens"] = 300
        return payload

    monkeypatch.setattr(SyntheticClient, "page_calls", amended)
    third, _ = submit(prepared, "third")
    execute_sync(third.pk)
    assert CallFact.objects.count() == 5
    assert VersionCall.objects.count() == 12
    first_fact = (
        VersionCall.objects.filter(version__run=first)
        .order_by("upstream_record_id")
        .first()
        .fact
    )
    assert first_fact.input_tokens == 100


def test_temporary_retries_are_bounded_and_permanent_errors_do_not_retry(
    prepared, monkeypatch
):
    monkeypatch.setattr(
        SyntheticClient,
        "page_calls",
        Mock(side_effect=AgioneOpsError("SOURCE_TIMEOUT", retryable=True)),
    )
    run, _ = submit(prepared)
    results = []
    for _ in range(3):
        SourceConnection.objects.filter(pk=run.connection_id).update(
            lease_expires_at=timezone.now() + timedelta(seconds=119)
        )
        results.append(execute_sync(run.pk)["status"])
    assert results == ["retrying", "retrying", "failed"]
    run.refresh_from_db()
    assert run.attempt == 3
    monkeypatch.setattr(
        SyntheticClient,
        "page_calls",
        Mock(
            side_effect=AgioneOpsError(
                "SOURCE_IDENTITY_MISMATCH", retryable=True
            )
        ),
    )
    permanent, _ = submit(prepared, "permanent")
    assert execute_sync(permanent.pk)["status"] == "failed"
    permanent.refresh_from_db()
    assert permanent.attempt == 1


def test_publication_error_rolls_back_entire_new_dataset(
    prepared, monkeypatch
):
    original = VersionCall.objects.create
    calls = []

    def fail_midway(**kwargs):
        calls.append(kwargs)
        if len(calls) == 3:
            raise RuntimeError("synthetic publication failure")
        return original(**kwargs)

    monkeypatch.setattr(VersionCall.objects, "create", fail_midway)
    run, _ = submit(prepared)
    assert execute_sync(run.pk)["status"] == "failed"
    assert not DatasetVersion.objects.exists()
    assert not CallFact.objects.exists()
    assert not VersionCall.objects.exists()


def test_task_name_and_payload_are_compatible(prepared):
    run, _ = submit(prepared)
    assert run_sync.name == "agione_ops.tasks.run_sync"
    assert run_sync.run(str(run.pk))["status"] == "succeeded"
    assert execute_sync("invalid-uuid")["errorCode"] == "RUN_NOT_FOUND"


def test_eager_execution_never_changes_the_preallocated_task_id(
    prepared, django_capture_on_commit_callbacks, no_broker
):
    observed = []

    def eager(*, args, task_id, retry):
        run = SyncRun.objects.get(pk=args[0])
        observed.append(run.celery_id)
        assert run.celery_id == task_id
        assert retry is False
        assert execute_sync(run.pk)["status"] == "succeeded"
        observed.append(SyncRun.objects.get(pk=run.pk).celery_id)
        return SimpleNamespace(id="not-the-authoritative-task-id")

    no_broker.side_effect = eager
    with django_capture_on_commit_callbacks(execute=True):
        run, _ = submit(prepared)
    run.refresh_from_db()
    assert observed == [run.celery_id, run.celery_id]
    assert run.status == "succeeded"


def test_early_retry_delivery_does_not_claim_or_reschedule(
    prepared, monkeypatch
):
    monkeypatch.setattr(
        SyntheticClient,
        "page_calls",
        Mock(side_effect=AgioneOpsError("SOURCE_TIMEOUT", retryable=True)),
    )
    run, _ = submit(prepared)
    result = execute_sync(run.pk)
    assert result["status"] == "retrying"
    assert result["retryAfter"] > 0
    retry = Mock(side_effect=AssertionError("Duplicate delivery rescheduled"))
    monkeypatch.setattr(run_sync, "retry", retry)
    assert run_sync.run(str(run.pk)) == {"status": "retrying"}
    retry.assert_not_called()
    run.refresh_from_db()
    assert run.attempt == 1


def test_lease_expiry_during_publication_rolls_back_new_facts(
    prepared, monkeypatch
):
    original_create = VersionCall.objects.create
    original_now = timezone.now

    def expire(**kwargs):
        result = original_create(**kwargs)
        monkeypatch.setattr(
            "agione_ops.sync.django_timezone.now",
            lambda: original_now() + timedelta(seconds=121),
        )
        return result

    monkeypatch.setattr(VersionCall.objects, "create", expire)
    run, _ = submit(prepared)
    result = execute_sync(run.pk)
    assert result["errorCode"] == "LEASE_LOST"
    assert not DatasetVersion.objects.exists()
    assert not CallFact.objects.exists()


def test_final_publication_rechecks_the_global_execution_gate(
    prepared, monkeypatch, settings
):
    original_create = VersionCall.objects.create

    def disable_execution(**kwargs):
        result = original_create(**kwargs)
        settings.AGIONE_OPS_SYNTHETIC_ENABLED = False
        return result

    monkeypatch.setattr(VersionCall.objects, "create", disable_execution)
    run, _ = submit(prepared)
    assert execute_sync(run.pk)["status"] == "revoked"
    assert not DatasetVersion.objects.exists()
    assert not CallFact.objects.exists()
