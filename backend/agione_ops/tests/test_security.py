"""Explicit permissions and dedicated fail-closed credential security."""

import base64
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import override_settings
from rest_framework.exceptions import (
    NotAuthenticated,
    NotFound,
    PermissionDenied,
)

from agione_ops.encryption import (
    CredentialConfigurationError,
    CredentialDecryptionError,
    decrypt_credentials,
    encrypt_credentials,
)
from agione_ops.models import ConnectionGrant, SourceConnection
from agione_ops.permissions import (
    authorize_run,
    get_connection_for,
    has_action,
    require_action,
)

pytestmark = pytest.mark.django_db


def grant_action(user, codename):
    permission = Permission.objects.get(
        content_type__app_label="agione_ops",
        codename=codename,
    )
    user.user_permissions.add(permission)


@pytest.fixture
def authority():
    user = get_user_model().objects.create_user(username="security-owner")
    connection = SourceConnection.objects.create(
        name="Synthetic source",
        platform="pro",
        principal_kind="operator",
        created_by=user,
        enabled=True,
    )
    return user, connection


@pytest.mark.parametrize(
    "staff,superuser", [(False, False), (True, False), (True, True)]
)
def test_staff_and_superuser_have_no_implicit_action_or_connection(
    authority, staff, superuser
):
    user, connection = authority
    user.is_staff, user.is_superuser = staff, superuser
    user.save()
    assert not has_action(user, "view_business")
    with pytest.raises(PermissionDenied):
        get_connection_for(user, connection.pk)
    grant_action(user, "view_business")
    with pytest.raises(NotFound):
        get_connection_for(user, connection.pk)
    ConnectionGrant.objects.create(
        connection=connection, user=user, can_view=True
    )
    assert get_connection_for(user, connection.pk).pk == connection.pk


def test_group_permission_still_requires_correct_connection_grant(authority):
    user, connection = authority
    group = Group.objects.create(name="Synthetic viewers")
    group.permissions.add(
        Permission.objects.get(
            content_type__app_label="agione_ops", codename="view_business"
        )
    )
    user.groups.add(group)
    with pytest.raises(NotFound):
        get_connection_for(user, connection.pk)
    ConnectionGrant.objects.create(
        connection=connection, user=user, can_sync=True
    )
    with pytest.raises(NotFound):
        get_connection_for(user, connection.pk)


@pytest.mark.parametrize("via_group", [False, True])
def test_legacy_model_permission_name_cannot_authorize_new_domain(
    authority,
    via_group,
):
    """Same app and codename from an older Connection model is not a grant."""

    user, connection = authority
    old_type = ContentType.objects.create(
        app_label="agione_ops",
        model="connection",
    )
    old_permission = Permission.objects.create(
        content_type=old_type,
        codename="view_business",
        name="Synthetic legacy permission",
    )
    group = Group.objects.create(name="Synthetic legacy action group")
    if via_group:
        group.permissions.add(old_permission)
        user.groups.add(group)
    else:
        user.user_permissions.add(old_permission)
    ConnectionGrant.objects.create(
        connection=connection,
        user=user,
        can_view=True,
    )
    assert not has_action(user, "view_business")
    with pytest.raises(PermissionDenied):
        get_connection_for(user, connection.pk)
    new_permission = Permission.objects.get(
        content_type__app_label="agione_ops",
        content_type__model="sourceconnection",
        codename="view_business",
    )
    if via_group:
        group.permissions.add(new_permission)
    else:
        user.user_permissions.add(new_permission)
    assert get_connection_for(user, connection.pk).pk == connection.pk


def test_configuration_action_does_not_grant_business_data(authority):
    user, connection = authority
    grant_action(user, "manage_connections")
    assert (
        get_connection_for(user, connection.pk, "manage_connections").pk
        == connection.pk
    )
    with pytest.raises(PermissionDenied):
        get_connection_for(user, connection.pk, "view_business")


def test_action_access_requires_authentication_and_active_user(authority):
    user, _ = authority
    grant_action(user, "view_business")
    with pytest.raises(NotAuthenticated):
        require_action(None, "view_business")
    user.is_active = False
    user.save()
    with pytest.raises(PermissionDenied):
        require_action(user, "view_business")


def test_progress_access_requires_sync_grant_and_initiator(authority):
    user, connection = authority
    grant_action(user, "run_sync")
    ConnectionGrant.objects.create(
        connection=connection, user=user, can_sync=True
    )
    own = Mock(connection_id=connection.pk, initiated_by_id=user.pk)
    assert authorize_run(user, own).pk == connection.pk
    other = Mock(connection_id=connection.pk, initiated_by_id=user.pk + 1)
    with pytest.raises(NotFound):
        authorize_run(user, other)
    connection.enabled = False
    connection.save()
    with pytest.raises(NotFound):
        authorize_run(user, own)


def test_credentials_use_dedicated_keys_and_never_fall_back():
    payload = {"ak": "synthetic-ak", "sk": "synthetic-secret"}
    ciphertext, key_id = encrypt_credentials(payload)
    assert "synthetic-secret" not in ciphertext
    assert decrypt_credentials(ciphertext, key_id) == payload
    with pytest.raises(CredentialDecryptionError):
        decrypt_credentials("synthetic-plaintext", key_id)
    with override_settings(AGIONE_OPS_ENCRYPTION_KEYS={}):
        with pytest.raises(CredentialConfigurationError):
            encrypt_credentials(payload)
        with pytest.raises(CredentialConfigurationError):
            decrypt_credentials(ciphertext, key_id)
    replacement = base64.urlsafe_b64encode(b"1" * 32).decode("ascii")
    with override_settings(AGIONE_OPS_ENCRYPTION_KEYS={key_id: replacement}):
        with pytest.raises(CredentialDecryptionError):
            decrypt_credentials(ciphertext, key_id)


def test_rotation_preserves_connection_identity_and_advances_versions(
    authority,
):
    _, connection = authority
    pk, config = connection.pk, connection.config_version
    connection.set_credentials({"sk": "synthetic-first"})
    connection.save()
    first = connection.credential_version
    connection.set_credentials({"sk": "synthetic-second"})
    connection.save()
    assert connection.pk == pk
    assert connection.credential_version == first + 1
    assert connection.config_version == config + 2
    assert connection.get_credentials()["sk"] == "synthetic-second"
    assert "synthetic-second" not in repr(connection)


@pytest.mark.parametrize("bulk", [False, True])
@pytest.mark.parametrize(
    "field,value",
    [
        ("platform", "cc"),
        ("principal_kind", "provider"),
        ("source_kind", "unsupported"),
        ("expected_tenant_id", "another-tenant"),
    ],
)
def test_connection_identity_cannot_be_reassigned(
    authority, bulk, field, value
):
    connection = authority[1]
    if bulk:
        with pytest.raises(ValidationError):
            SourceConnection.objects.filter(pk=connection.pk).update(
                **{field: value}
            )
    else:
        setattr(connection, field, value)
        with pytest.raises(ValidationError):
            connection.save()


@pytest.mark.parametrize("bulk", [False, True])
def test_rotation_invalidates_old_identity_verification(authority, bulk):
    from django.utils import timezone

    connection = authority[1]
    connection.verified_tenant_id = "synthetic-verified"
    connection.verified_at = timezone.now()
    connection.save(update_fields=["verified_tenant_id", "verified_at"])
    if bulk:
        ciphertext, key_id = encrypt_credentials({"sk": "synthetic-rotated"})
        SourceConnection.objects.filter(pk=connection.pk).update(
            credential_ciphertext=ciphertext,
            key_id=key_id,
        )
    else:
        connection.set_credentials({"sk": "synthetic-rotated"})
        connection.save(update_fields=["credential_ciphertext", "key_id"])
    connection.refresh_from_db()
    assert connection.verified_tenant_id == ""
    assert connection.verified_at is None


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://allowed.invalid",
        "https://127.0.0.1/",
        "https://allowed.invalid:444/",
        "https://secret:password@allowed.invalid/",
        "https://allowed.invalid/?secret=x",
        "https://allowed.invalid/#fragment",
    ],
)
def test_endpoint_policy_rejects_uncontrolled_addresses(authority, endpoint):
    connection = authority[1]
    connection.endpoint = endpoint
    with override_settings(
        AGIONE_OPS_ALLOWED_ENDPOINT_HOSTS=["allowed.invalid"]
    ):
        with pytest.raises(ValidationError):
            connection.save()


def test_endpoint_configuration_is_explicit_and_never_probes(authority):
    connection = authority[1]
    connection.endpoint = "https://allowed.invalid/read-only"
    with override_settings(
        AGIONE_OPS_ALLOWED_ENDPOINT_HOSTS=["allowed.invalid"]
    ):
        connection.save()
    assert connection.endpoint == "https://allowed.invalid/read-only"
