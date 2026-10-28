"""Synthetic-only API acceptance with real permissions and an in-memory DB."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.utils import timezone
from rest_framework.test import APIClient

from agione_ops.models import (
    ConnectionGrant,
    DatasetVersion,
    SourceConnection,
    SyncRun,
)

pytestmark = pytest.mark.django_db
BASE = "/api/v1/agione-ops/connections/"


def allow(user, *actions):
    for action in actions:
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="agione_ops",
                codename=action,
            )
        )


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def actors():
    users = get_user_model()
    manager = users.objects.create_user(username="synthetic-configurator")
    owner = users.objects.create_user(username="synthetic-operator")
    other = users.objects.create_user(username="synthetic-other")
    allow(manager, "manage_connections")
    allow(owner, "view_business", "run_sync")
    allow(other, "view_business", "run_sync")
    return manager, owner, other


@pytest.fixture
def connection(actors):
    manager, owner, _ = actors
    connection = SourceConnection.objects.create(
        name="Synthetic API source",
        platform="pro",
        principal_kind="provider",
        created_by=manager,
        expected_tenant_id="synthetic-basic-tenant",
        enabled=True,
    )
    ConnectionGrant.objects.create(
        connection=connection,
        user=owner,
        can_view=True,
        can_sync=True,
    )
    result = client_for(manager).post(
        f"{BASE}{connection.pk}/verify/",
        {},
        format="json",
    )
    assert result.status_code == 200, result.data
    connection.refresh_from_db()
    return connection


@pytest.fixture
def payload():
    end = timezone.now().replace(microsecond=0) - timedelta(hours=1)
    return {
        "window": {
            "start": (end - timedelta(days=1)).isoformat(),
            "endExclusive": end.isoformat(),
            "timezone": "Asia/Shanghai",
        }
    }


def test_local_workflow_publishes_a_fixed_version(
    actors,
    connection,
    payload,
    django_capture_on_commit_callbacks,
):
    _, owner, _ = actors
    client = client_for(owner)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            f"{BASE}{connection.pk}/sync-runs/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="local-workflow-1",
        )
    assert response.status_code == 202, response.data
    run_id = response.data["data"]["runId"]
    progress = client.get(response.data["data"]["statusUrl"])
    assert progress.status_code == 200, progress.data
    assert progress.data["data"]["status"] == "succeeded"
    version_id = progress.data["data"]["dataVersion"]
    assert version_id
    response = client.post(
        f"{BASE}{connection.pk}/dashboard/query/",
        {"dataVersion": version_id},
        format="json",
    )
    assert response.status_code == 200, response.data
    data = response.data["data"]
    assert data["dataVersion"] == version_id
    assert data["summary"]["requests"] == 4
    assert data["summary"]["success"] == 2
    assert data["summary"]["failure"] == 1
    assert data["summary"]["unknown"] == 1
    assert data["summary"]["successRate"] == 50
    assert data["comparison"]["summary"] is None
    repeated = client.post(
        f"{BASE}{connection.pk}/sync-runs/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY="local-workflow-1",
    )
    assert repeated.status_code == 200
    assert repeated.data["data"]["runId"] == run_id
    assert SyncRun.objects.count() == 1
    assert DatasetVersion.objects.count() == 1


def test_connection_directory_is_scoped_and_has_no_read_side_effects(
    actors,
    connection,
):
    manager, owner, other = actors
    before = SourceConnection.objects.values().get(pk=connection.pk)
    listed = client_for(owner).get(BASE)
    assert listed.status_code == 200
    assert listed.data["data"]["count"] == 1
    assert client_for(other).get(BASE).data["data"]["count"] == 0
    assert client_for(manager).get(BASE).status_code == 200
    assert SourceConnection.objects.values().get(pk=connection.pk) == before
    assert not SyncRun.objects.exists()


def test_configuration_is_write_only_and_does_not_grant_data_access(actors):
    manager, _, _ = actors
    secret = "synthetic-secret-not-a-real-credential"
    response = client_for(manager).post(
        BASE,
        {
            "name": "Encrypted synthetic configuration",
            "platform": "cc",
            "principalKind": "operator",
            "expectedTenantId": "synthetic-basic-tenant",
            "credentials": {"access_key": secret},
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    data = response.data["data"]
    assert data["hasCredentials"] is True
    assert "credentials" not in data
    assert "credentialCiphertext" not in data
    assert secret not in response.content.decode()
    saved = SourceConnection.objects.get(pk=data["id"])
    assert saved.get_credentials() == {"access_key": secret}
    assert not saved.enabled
    assert not ConnectionGrant.objects.filter(connection=saved).exists()
    assert (
        client_for(manager)
        .post(
            f"{BASE}{saved.pk}/dashboard/query/",
            {},
            format="json",
        )
        .status_code
        == 403
    )


@pytest.mark.parametrize("staff,superuser", [(True, False), (True, True)])
def test_staff_and_superuser_have_no_implicit_data_permission(
    connection,
    staff,
    superuser,
):
    user = get_user_model().objects.create_user(
        username=f"synthetic-staff-{superuser}",
        is_staff=staff,
        is_superuser=superuser,
    )
    client = client_for(user)
    assert client.get(BASE).status_code == 403
    allow(user, "view_business")
    assert (
        client.post(
            f"{BASE}{connection.pk}/dashboard/query/",
            {},
            format="json",
        ).status_code
        == 404
    )


def test_grant_requires_explicit_configurator_and_does_not_grant_action(
    actors,
    connection,
):
    manager, _, other = actors
    user = get_user_model().objects.create_user(username="synthetic-no-action")
    path = f"{BASE}{connection.pk}/grants/{user.pk}/"
    assert (
        client_for(other)
        .put(
            path,
            {
                "canView": True,
                "canSync": False,
            },
            format="json",
        )
        .status_code
        == 403
    )
    assert (
        client_for(manager)
        .put(
            path,
            {
                "canView": True,
                "canSync": False,
            },
            format="json",
        )
        .status_code
        == 200
    )
    assert (
        client_for(user)
        .post(
            f"{BASE}{connection.pk}/dashboard/query/",
            {},
            format="json",
        )
        .status_code
        == 403
    )


def test_unauthorized_object_and_unknown_version_do_not_leak(
    actors, connection
):
    _, owner, other = actors
    path = f"{BASE}{connection.pk}/dashboard/query/"
    assert client_for(other).post(path, {}, format="json").status_code == 404
    assert (
        client_for(owner)
        .post(
            path,
            {
                "dataVersion": "00000000-0000-4000-8000-000000000001",
            },
            format="json",
        )
        .status_code
        == 404
    )


def test_finance_refresh_requires_grant_and_existing_projection(actors, connection):
    _, owner, other = actors
    path = f"{BASE}{connection.pk}/finance/refresh/"
    assert client_for(other).post(path, {}, format="json").status_code == 404
    assert client_for(owner).post(path, {}, format="json").status_code == 409


def test_naive_future_unsupported_and_unknown_inputs_are_rejected(
    actors,
    connection,
    payload,
):
    _, owner, _ = actors
    client = client_for(owner)
    path = f"{BASE}{connection.pk}/sync-runs/"
    bad = {"window": {**payload["window"], "start": "2026-01-01T00:00:00"}}
    assert (
        client.post(
            path, bad, format="json", HTTP_IDEMPOTENCY_KEY="naive"
        ).status_code
        == 400
    )
    assert (
        client.post(
            path,
            {**payload, "kind": "previous"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="previous",
        ).status_code
        == 400
    )
    assert (
        client.post(
            path,
            {**payload, "sourcePayload": []},
            format="json",
            HTTP_IDEMPOTENCY_KEY="raw-input",
        ).status_code
        == 400
    )
    assert client.post(path, payload, format="json").status_code == 400
    assert not SyncRun.objects.exists()


def test_credentials_and_disabled_global_mode_never_reach_a_source(
    actors,
    connection,
    settings,
):
    manager, owner, _ = actors
    settings.AGIONE_OPS_SYNTHETIC_ENABLED = False
    assert (
        client_for(manager)
        .post(
            f"{BASE}{connection.pk}/verify/",
            {},
            format="json",
        )
        .status_code
        == 403
    )
    assert (
        client_for(owner)
        .post(
            f"{BASE}{connection.pk}/dashboard/query/",
            {},
            format="json",
        )
        .status_code
        == 200
    )
    assert not SyncRun.objects.exists()


def test_identity_cannot_be_reassigned_to_old_history(actors, connection):
    manager, _, _ = actors
    before = connection.expected_tenant_id
    response = client_for(manager).patch(
        f"{BASE}{connection.pk}/",
        {
            "expectedTenantId": "synthetic-different-tenant",
        },
        format="json",
    )
    assert response.status_code == 400
    connection.refresh_from_db()
    assert connection.expected_tenant_id == before


def test_progress_is_private_even_with_shared_connection_scope(
    actors,
    connection,
    payload,
):
    _, owner, other = actors
    ConnectionGrant.objects.create(
        connection=connection,
        user=other,
        can_view=True,
        can_sync=True,
    )
    response = client_for(owner).post(
        f"{BASE}{connection.pk}/sync-runs/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY="private-progress",
    )
    assert response.status_code == 202, response.data
    url = response.data["data"]["statusUrl"]
    assert client_for(owner).get(url).status_code == 200
    assert client_for(other).get(url).status_code == 404
    owner.user_permissions.remove(
        Permission.objects.get(
            content_type__app_label="agione_ops",
            codename="run_sync",
        )
    )
    assert client_for(owner).get(url).status_code == 403


def test_readonly_and_unknown_configuration_fields_are_rejected(
    actors,
    connection,
):
    manager, _, _ = actors
    for payload in (
        {"credentialCiphertext": "synthetic-private"},
        {"verifiedAt": "2026-01-01T00:00:00Z"},
        {"configVersion": 0},
        {"activeRunId": None},
    ):
        result = client_for(manager).patch(
            f"{BASE}{connection.pk}/",
            payload,
            format="json",
        )
        assert result.status_code == 400, result.data
    assert (
        client_for(manager)
        .post(
            f"{BASE}{connection.pk}/verify/",
            {"credentials": {"token": "synthetic"}},
            format="json",
        )
        .status_code
        == 400
    )


def test_credentials_require_a_dedicated_key_without_partial_creation(
    actors,
    settings,
):
    manager, _, _ = actors
    settings.AGIONE_OPS_ENCRYPTION_KEYS = {}
    secret = "synthetic-must-not-appear-in-error"
    result = client_for(manager).post(
        BASE,
        {
            "name": "Missing key",
            "platform": "pro",
            "principalKind": "provider",
            "expectedTenantId": "synthetic-basic-tenant",
            "credentials": {"token": secret},
        },
        format="json",
    )
    assert result.status_code == 503
    assert secret not in result.content.decode()
    assert not SourceConnection.objects.exists()


def test_core_registration_does_not_enable_sources_or_legacy_authorization():
    from pathlib import Path
    import ast

    root = Path(__file__).resolve().parents[2]
    base = ast.parse((root / "core/settings/base.py").read_text())
    literal_flags = {
        statement.targets[0].id: statement.value.value
        for statement in base.body
        if isinstance(statement, ast.Assign)
        and isinstance(statement.targets[0], ast.Name)
        and isinstance(statement.value, ast.Constant)
    }
    assert literal_flags["AGIONE_OPS_SYNTHETIC_ENABLED"] is False
    assert literal_flags["AGIONE_OPS_TASK_PROJECTION_ENABLED"] is False
    assert '"agione_ops.tasks"' in (root / "core/celery.py").read_text()
    assert "include('agione_ops.urls')" in (root / "core/urls.py").read_text()


def test_default_api_is_authenticated(connection):
    assert APIClient().get(BASE).status_code in {401, 403}


def test_new_feature_is_not_a_legacy_alias_or_default():
    from accounts.access import (
        FEATURE_ALIASES,
        FEATURE_KEYS,
        LEGACY_DEFAULT_FEATURES,
    )

    assert "agione_ops" in FEATURE_KEYS
    assert "agione_ops" not in LEGACY_DEFAULT_FEATURES
    assert "agione_ops" not in FEATURE_ALIASES.values()
