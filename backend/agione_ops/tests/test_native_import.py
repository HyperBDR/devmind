"""Native provisioning is explicit, transactional and never prints secrets."""

import io
import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from agione_ops.models import ConnectionGrant, SourceConnection

pytestmark = pytest.mark.django_db


def row(tenant="123"):
    return {
        "platform": "pro", "principal_kind": "provider",
        "endpoint": "https://allowed.example", "expected_tenant_id": tenant,
        "credentials": {
            "auth_mode": "aksk", "access_key": "test-access",
            "secret_key": "test-secret",
        },
    }


@pytest.fixture
def provision(settings):
    settings.AGIONE_OPS_NATIVE_ENABLED = True
    settings.AGIONE_OPS_ALLOWED_ENDPOINT_HOSTS = ["allowed.example"]
    return get_user_model().objects.create_user(username="native-owner")


def invoke(user, rows, *options):
    output = io.StringIO()
    with patch("sys.stdin", io.StringIO(json.dumps(rows))):
        call_command(
            "import_agione_native_credentials", "--user-id", str(user.pk),
            *options, stdout=output,
        )
    return output.getvalue()


def test_import_native_without_demo_binding_with_explicit_sync(provision):
    result = invoke(provision, [row()], "--allow-sync")
    connection = SourceConnection.objects.get(source_kind="native")
    assert connection.expected_tenant_id == "123"
    assert connection.credential_ciphertext
    assert "test-secret" not in connection.credential_ciphertext
    assert "test-secret" not in result
    grant = ConnectionGrant.objects.get(connection=connection, user=provision)
    assert grant.can_view and grant.can_sync
    assert provision.user_permissions.filter(codename="run_sync").exists()
    assert not provision.user_permissions.filter(
        codename="manage_connections",
    ).exists()


def test_reimport_does_not_revoke_sync_permission(provision):
    invoke(provision, [row()], "--allow-sync")
    invoke(provision, [row()])
    assert ConnectionGrant.objects.get(user=provision).can_sync


def test_invalid_input_rolls_back_without_disclosing_secret(provision):
    invalid = row("124")
    invalid["endpoint"] = "https://forbidden.example"
    with pytest.raises(CommandError) as failure:
        invoke(provision, [row(), invalid], "--allow-sync")
    assert "test-secret" not in str(failure.value)
    assert not SourceConnection.objects.filter(source_kind="native").exists()
    assert not ConnectionGrant.objects.filter(user=provision).exists()


def test_duplicate_identity_is_rejected(provision):
    with pytest.raises(CommandError):
        invoke(provision, [row(), row()])
    assert not SourceConnection.objects.filter(source_kind="native").exists()
