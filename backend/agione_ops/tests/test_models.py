"""Synthetic-only model and publication invariants."""

from datetime import timedelta
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone

from agione_ops.models import (
    CallFact,
    ConnectionGrant,
    DatasetVersion,
    SourceConnection,
    SyncRun,
    VersionCall,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def graph():
    """Build one entirely synthetic published dataset."""

    user = get_user_model().objects.create_user(username="model-owner")
    connection = SourceConnection.objects.create(
        name="Synthetic",
        platform="pro",
        principal_kind="provider",
        created_by=user,
        enabled=True,
    )
    grant = ConnectionGrant.objects.create(
        connection=connection,
        user=user,
        can_view=True,
        can_sync=True,
    )
    connection.refresh_from_db()
    start = timezone.now().replace(microsecond=0) - timedelta(days=2)
    run = SyncRun.objects.create(
        connection=connection,
        initiated_by=user,
        window_start=start,
        window_end=start + timedelta(days=1),
        idempotency_key="model-run",
        status="running",
        request_hash="a" * 64,
        credential_version=connection.credential_version,
        config_version=connection.config_version,
        grant_revision=grant.revision,
    )
    version = DatasetVersion.objects.create(
        connection=connection,
        run=run,
        window_start=run.window_start,
        window_end=run.window_end,
    )
    fact = CallFact.objects.create(
        connection=connection,
        upstream_record_id="9007199254740993123",
        content_hash="b" * 64,
        occurred_at=start + timedelta(hours=1),
        customer_id="customer-1",
        model_id="model-1",
        status="unknown",
        input_tokens=None,
        output_tokens=0,
    )
    link = VersionCall.objects.create(
        version=version,
        fact=fact,
        upstream_record_id=fact.upstream_record_id,
    )
    return user, connection, grant, run, version, fact, link


def test_defaults_are_disabled_and_synthetic_only(graph):
    user, *_ = graph
    connection = SourceConnection.objects.create(
        name="Off by default",
        platform="cc",
        principal_kind="operator",
        created_by=user,
    )
    assert connection.enabled is False
    assert connection.source_kind == "synthetic"
    assert connection.credential_ciphertext == ""
    assert connection.active_run_id is None
    assert (
        ConnectionGrant.objects.create(
            connection=connection,
            user=user,
        ).can_view
        is False
    )


@pytest.mark.parametrize("index", [4, 5, 6])
def test_published_rows_are_immutable(graph, index):
    instance = graph[index]
    with pytest.raises(ValidationError, match="immutable"):
        instance.save()
    with pytest.raises(ValidationError, match="immutable"):
        instance.delete()
    with pytest.raises(ValidationError, match="immutable"):
        type(instance).objects.filter(pk=instance.pk).update(id=instance.pk)
    with pytest.raises(ValidationError, match="immutable"):
        type(instance).objects.filter(pk=instance.pk).delete()
    with pytest.raises(ValidationError, match="immutable"):
        type(instance).objects.bulk_update([instance], ["id"])
    with pytest.raises(ValidationError, match="immutable"):
        type(instance).objects.bulk_create([], update_conflicts=True)


@pytest.mark.parametrize("index", [4, 5, 6])
def test_reconstructed_publication_cannot_overwrite_existing_primary_key(
    graph,
    index,
):
    instance = graph[index]
    model = type(instance)
    values = {
        field.attname: getattr(instance, field.attname)
        for field in model._meta.concrete_fields
    }
    clone = model(**values)
    assert clone._state.adding
    with pytest.raises(IntegrityError), transaction.atomic():
        clone.save()
    with pytest.raises(ValidationError, match="immutable"):
        model(**values).save(force_update=True)
    assert model.objects.values().get(pk=instance.pk) == values


def test_version_links_validate_connection_identity_and_window(graph):
    user, connection, _, run, version, fact, _ = graph
    second = SourceConnection.objects.create(
        name="Other",
        platform="cc",
        principal_kind="provider",
        created_by=user,
    )
    foreign = CallFact.objects.create(
        connection=second,
        upstream_record_id="foreign",
        content_hash="c" * 64,
        occurred_at=fact.occurred_at,
        customer_id="customer-1",
        model_id="model-1",
        status="success",
    )
    with pytest.raises(ValidationError, match="connection"):
        VersionCall.objects.create(
            version=version,
            fact=foreign,
            upstream_record_id="foreign",
        )
    with pytest.raises(ValidationError, match="identity"):
        VersionCall.objects.bulk_create(
            [
                VersionCall(
                    version=version, fact=fact, upstream_record_id="wrong"
                ),
            ]
        )
    outside = CallFact.objects.create(
        connection=connection,
        upstream_record_id="outside",
        content_hash="d" * 64,
        occurred_at=run.window_end,
        customer_id="customer-1",
        model_id="model-1",
        status="failure",
    )
    with pytest.raises(ValidationError, match="outside"):
        VersionCall.objects.create(
            version=version,
            fact=outside,
            upstream_record_id="outside",
        )
    with pytest.raises(ValidationError, match="connection"):
        DatasetVersion.objects.create(
            connection=second,
            run=run,
            window_start=run.window_start,
            window_end=run.window_end,
        )


def test_fact_identity_is_string_and_unknown_differs_from_zero(graph):
    fact = graph[5]
    fact.refresh_from_db()
    assert fact.upstream_record_id == "9007199254740993123"
    assert fact.input_tokens is None
    assert fact.output_tokens == 0
    assert fact.status == "unknown"


def test_grant_revoke_regrant_and_recreate_advance_parent_epoch(graph):
    user, connection, grant, *_ = graph
    versions = [SourceConnection.objects.get(pk=connection.pk).config_version]
    grant.can_sync = False
    grant.save()
    versions.append(
        SourceConnection.objects.get(pk=connection.pk).config_version
    )
    revision = grant.revision
    ConnectionGrant.objects.filter(pk=grant.pk).update(can_sync=True)
    grant.refresh_from_db()
    assert grant.revision > revision
    versions.append(
        SourceConnection.objects.get(pk=connection.pk).config_version
    )
    grant.delete()
    versions.append(
        SourceConnection.objects.get(pk=connection.pk).config_version
    )
    ConnectionGrant.objects.create(
        connection=connection, user=user, can_sync=True
    )
    versions.append(
        SourceConnection.objects.get(pk=connection.pk).config_version
    )
    assert all(left < right for left, right in zip(versions, versions[1:]))


def test_config_epoch_changes_but_lease_updates_do_not(graph):
    connection = graph[1]
    before = connection.config_version
    connection.enabled = False
    connection.save(update_fields=["enabled"])
    connection.enabled = True
    connection.save(update_fields=["enabled"])
    assert connection.config_version == before + 2
    SourceConnection.objects.filter(pk=connection.pk).update(lease_epoch=7)
    connection.refresh_from_db()
    assert connection.config_version == before + 2
    SourceConnection.objects.filter(pk=connection.pk).update(enabled=False)
    connection.refresh_from_db()
    assert connection.config_version == before + 3


def test_grant_identity_cannot_be_reassigned(graph):
    user, connection, grant, *_ = graph
    other = get_user_model().objects.create_user(username="different-owner")
    with pytest.raises(ValidationError, match="identity"):
        ConnectionGrant.objects.filter(pk=grant.pk).update(user=other)
    grant.user = other
    with pytest.raises(ValidationError, match="identity"):
        grant.save()


def test_duplicate_run_idempotency_is_database_enforced(graph):
    user, connection, grant, run, *_ = graph
    with pytest.raises(IntegrityError), transaction.atomic():
        SyncRun.objects.create(
            connection=connection,
            initiated_by=user,
            window_start=run.window_start,
            window_end=run.window_end,
            idempotency_key=run.idempotency_key,
            request_hash="e" * 64,
            credential_version=1,
            config_version=1,
            grant_revision=grant.revision,
        )


@pytest.mark.parametrize(
    "field,value", [("enabled", False), ("name", "Updated name")]
)
@pytest.mark.parametrize("partial", [False, True])
def test_stale_configuration_save_preserves_worker_lease(
    graph, field, value, partial
):
    connection, run = graph[1], graph[3]
    token = uuid.uuid4()
    expires = timezone.now() + timedelta(minutes=5)
    expected_config = connection.config_version + 8
    SourceConnection.objects.filter(pk=connection.pk).update(
        active_run_id=run.pk,
        lease_token=token,
        lease_epoch=23,
        lease_expires_at=expires,
        config_version=expected_config,
    )
    assert connection.active_run_id is None
    setattr(connection, field, value)
    connection.save(**({"update_fields": [field]} if partial else {}))
    connection.refresh_from_db()
    assert connection.active_run_id == run.pk
    assert connection.lease_token == token
    assert connection.lease_epoch == 23
    assert connection.lease_expires_at == expires
    assert connection.config_version == expected_config + 1


def test_model_saves_cannot_rewrite_lease_fencing_epoch(graph):
    connection, run = graph[1], graph[3]
    token = uuid.uuid4()
    SourceConnection.objects.filter(pk=connection.pk).update(
        active_run_id=run.pk,
        lease_token=token,
        lease_epoch=31,
    )
    connection.active_run_id = None
    connection.lease_token = None
    connection.lease_epoch = 0
    connection.save(
        update_fields=["active_run_id", "lease_token", "lease_epoch"]
    )
    connection.refresh_from_db()
    assert connection.active_run_id == run.pk
    assert connection.lease_token == token
    assert connection.lease_epoch == 31


@pytest.mark.parametrize("bulk", [False, True])
@pytest.mark.parametrize(
    "terminal_status", ["succeeded", "failed", "revoked", "interrupted"]
)
def test_terminal_version_cannot_accept_new_links_even_with_stale_run_cache(
    graph,
    bulk,
    terminal_status,
):
    connection, run, version = graph[1], graph[3], graph[4]
    assert version.run.status == "running"
    before = list(version.calls.values("id", "fact_id", "upstream_record_id"))
    fact = CallFact.objects.create(
        connection=connection,
        upstream_record_id="later-request",
        content_hash="f" * 64,
        occurred_at=run.window_start + timedelta(hours=2),
        customer_id="customer-1",
        model_id="model-1",
        status="success",
        input_tokens=999,
        output_tokens=999,
    )
    SyncRun.objects.filter(pk=run.pk).update(status=terminal_status)
    assert version.run.status == "running"
    link = VersionCall(
        version=version,
        fact=fact,
        upstream_record_id=fact.upstream_record_id,
    )
    with pytest.raises(ValidationError, match="running"):
        if bulk:
            VersionCall.objects.bulk_create([link])
        else:
            link.save()
    with pytest.raises(ValidationError, match="running"):
        link.full_clean(validate_unique=False, validate_constraints=False)
    assert (
        list(version.calls.values("id", "fact_id", "upstream_record_id"))
        == before
    )
    assert not VersionCall.objects.filter(fact=fact).exists()


@pytest.mark.parametrize("bulk", [False, True])
def test_terminal_run_cannot_create_a_new_version(graph, bulk):
    connection, run = graph[1], graph[3]
    SyncRun.objects.filter(pk=run.pk).update(status="succeeded")
    assert run.status == "running"
    version = DatasetVersion(
        connection=connection,
        run=run,
        window_start=run.window_start,
        window_end=run.window_end,
    )
    with pytest.raises(ValidationError, match="running"):
        if bulk:
            DatasetVersion.objects.bulk_create([version])
        else:
            version.save()
    assert DatasetVersion.objects.filter(run=run).count() == 1


def test_migration_state_is_complete():
    call_command(
        "makemigrations",
        "agione_ops",
        check=True,
        dry_run=True,
        skip_checks=True,
    )
