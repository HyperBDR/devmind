"""Guarded explicit demo initialization, with no real network or database."""

from io import StringIO
from unittest.mock import Mock

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.core.management.base import CommandError

if not apps.is_installed("accounts"):
    pytest.skip(
        "Run local-demo tests with agione_ops.tests.local_demo_settings.",
        allow_module_level=True,
    )

from accounts.models import Role
from agione_ops.management.commands.setup_agione_ops_local_demo import MARKER
from agione_ops.models import (
    ConnectionGrant,
    DatasetVersion,
    SourceConnection,
    SyncRun,
)
from agione_ops.sync import _dispatch
from agione_ops.tasks import run_sync

pytestmark = pytest.mark.django_db(transaction=True)
PASSWORD = "synthetic-demo-password-not-real-2026"


def setup(monkeypatch, **kwargs):
    """Supply an explicit test-only environment password without argv echo."""

    monkeypatch.setenv("AGIONE_TEST_DEMO_PASSWORD", PASSWORD)
    output = StringIO()
    call_command(
        "setup_agione_ops_local_demo",
        password_env="AGIONE_TEST_DEMO_PASSWORD",
        stdout=output,
        **kwargs,
    )
    assert PASSWORD not in output.getvalue()
    return output.getvalue()


def test_command_creates_four_ready_synthetic_connections_and_minimal_user(
    monkeypatch,
):
    """The app-local inline path needs no broker or global eager mode."""

    broker = Mock(
        side_effect=AssertionError("A broker must never be contacted")
    )
    monkeypatch.setattr(run_sync, "apply_async", broker)
    text = setup(monkeypatch)
    user = get_user_model().objects.get(username="agione-local-demo")
    assert user.last_name == MARKER
    assert user.check_password(PASSWORD)
    assert not user.is_staff and not user.is_superuser
    assert user.profile.registration_completed
    role = user.platform_roles.get()
    assert role.visible_features == ["agione_ops"]
    assert role.preferred_platform == "agione_ops"
    assert set(user.user_permissions.values_list("codename", flat=True)) == {
        "view_business",
        "run_sync",
    }
    assert SourceConnection.objects.count() == 4
    assert set(
        SourceConnection.objects.values_list("platform", "principal_kind")
    ) == {
        ("pro", "provider"),
        ("pro", "operator"),
        ("cc", "provider"),
        ("cc", "operator"),
    }
    assert not SourceConnection.objects.exclude(
        endpoint="", credential_ciphertext=""
    ).exists()
    assert (
        ConnectionGrant.objects.filter(
            user=user, can_view=True, can_sync=True
        ).count()
        == 4
    )
    assert SyncRun.objects.filter(status="succeeded").count() == 4
    assert DatasetVersion.objects.count() == 4
    assert "Four synthetic connections are ready" in text
    broker.assert_not_called()


def test_rerun_preserves_password_and_reuses_resources_without_new_runs(
    monkeypatch,
):
    setup(monkeypatch)
    user = get_user_model().objects.get(username="agione-local-demo")
    previous = user.password
    output = StringIO()
    call_command("setup_agione_ops_local_demo", stdout=output)
    user.refresh_from_db()
    assert user.password == previous
    assert get_user_model().objects.count() == 1
    assert Role.objects.count() == 1
    assert SourceConnection.objects.count() == 4
    assert SyncRun.objects.count() == 4
    assert DatasetVersion.objects.count() == 4


@pytest.mark.parametrize(
    "flag",
    [
        "AGIONE_OPS_LOCAL_DEMO_ENABLED",
        "AGIONE_OPS_SYNTHETIC_ENABLED",
        "AGIONE_OPS_LOCAL_EAGER",
    ],
)
@pytest.mark.parametrize("value", [False, "true", 1])
def test_all_three_flags_require_literal_true(
    settings, monkeypatch, flag, value
):
    setattr(settings, flag, value)
    with pytest.raises(CommandError, match="flags"):
        setup(monkeypatch)
    assert not get_user_model().objects.exists()
    assert not SourceConnection.objects.exists()


def test_existing_unmarked_demo_username_is_not_claimed_or_reset(monkeypatch):
    user = get_user_model().objects.create_user(
        username="agione-local-demo",
        password="existing-non-demo-password",
    )
    before = user.password
    with pytest.raises(CommandError, match="non-demo"):
        setup(monkeypatch)
    user.refresh_from_db()
    assert user.password == before
    assert user.last_name == ""
    assert not SourceConnection.objects.exists()


def test_real_username_and_default_password_are_rejected():
    with pytest.raises(CommandError, match="namespace"):
        call_command("setup_agione_ops_local_demo", username="admin")
    with pytest.raises(CommandError, match="explicit password"):
        call_command("setup_agione_ops_local_demo")
    assert not get_user_model().objects.exists()


def test_explicit_existing_admin_grant_does_not_change_password_roles_or_flags(
    monkeypatch,
):
    admin = get_user_model().objects.create_user(
        username="synthetic-admin",
        password="existing-admin-password",
        is_staff=True,
        is_superuser=True,
    )
    unrelated = get_user_model().objects.create_user(
        username="synthetic-unrelated"
    )
    before = (admin.password, admin.is_staff, admin.is_superuser)
    setup(monkeypatch, grant_existing_user=admin.username)
    admin.refresh_from_db()
    assert (admin.password, admin.is_staff, admin.is_superuser) == before
    assert not admin.platform_roles.exists()
    assert set(admin.user_permissions.values_list("codename", flat=True)) == {
        "view_business",
        "run_sync",
    }
    assert (
        ConnectionGrant.objects.filter(
            user=admin, can_view=True, can_sync=True
        ).count()
        == 4
    )
    assert not ConnectionGrant.objects.filter(user=unrelated).exists()
    assert not unrelated.user_permissions.exists()


def test_existing_user_without_feature_visibility_is_not_silently_expanded(
    monkeypatch,
):
    user = get_user_model().objects.create_user(
        username="synthetic-hidden-user"
    )
    before = user.password
    with pytest.raises(CommandError, match="visibility"):
        setup(monkeypatch, grant_existing_user=user.username)
    user.refresh_from_db()
    assert user.password == before
    assert not user.platform_roles.exists()
    assert not user.user_permissions.exists()
    assert get_user_model().objects.count() == 1
    assert not SourceConnection.objects.exists()


def test_managed_connection_tampering_is_rejected_without_new_objects(
    monkeypatch,
):
    setup(monkeypatch)
    connection = SourceConnection.objects.first()
    SourceConnection.objects.filter(pk=connection.pk).update(
        synthetic_fixture="modified"
    )
    with pytest.raises(CommandError, match="unmarked or real"):
        call_command("setup_agione_ops_local_demo", stdout=StringIO())
    assert SourceConnection.objects.count() == 4
    assert SyncRun.objects.count() == 4


@pytest.mark.parametrize("inline", [False, "true", 1, None])
def test_non_literal_local_eager_values_preserve_broker_dispatch(
    settings, monkeypatch, inline
):
    settings.AGIONE_OPS_LOCAL_EAGER = inline
    from agione_ops import sync

    run = Mock(celery_id="synthetic-celery")
    monkeypatch.setattr(sync.SyncRun.objects, "get", Mock(return_value=run))
    monkeypatch.setattr(sync, "_project", Mock())
    broker = Mock()
    eager = Mock(side_effect=AssertionError("Unexpected inline execution"))
    monkeypatch.setattr(run_sync, "apply_async", broker)
    monkeypatch.setattr(run_sync, "apply", eager)
    _dispatch("synthetic-run")
    broker.assert_called_once_with(
        args=["synthetic-run"],
        task_id="synthetic-celery",
        retry=False,
    )
    eager.assert_not_called()
