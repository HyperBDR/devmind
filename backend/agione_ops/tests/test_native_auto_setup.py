"""Deployment provisioning consumes secrets without exposing them."""
import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from agione_ops.models import SourceConnection

pytestmark = pytest.mark.django_db


def test_auto_setup_imports_only_when_no_native_connection(settings, monkeypatch):
    from agione_ops.native_auto_setup import initialize_native_connections

    settings.AGIONE_OPS_NATIVE_ENABLED = True
    settings.AGIONE_OPS_ALLOWED_ENDPOINT_HOSTS = ["allowed.example"]
    user = get_user_model().objects.create_user(username="automatic-owner")
    credentials = [{
        "platform": "pro", "principal_kind": "provider",
        "endpoint": "https://allowed.example", "expected_tenant_id": "123",
        "credentials": {"auth_mode": "aksk", "access_key": "fake-ak",
                        "secret_key": "fake-sk"},
    }]
    monkeypatch.setenv("AGIONE_OPS_BOOTSTRAP_CREDENTIALS", json.dumps(credentials))
    monkeypatch.setenv("AGIONE_OPS_BOOTSTRAP_USER_ID", str(user.pk))
    with patch("agione_ops.tasks.start_initial_native_sync") as start, patch(
        "agione_ops.native_auto_setup.NativeClient"
    ) as client:
        client.return_value.__enter__.return_value.identity.return_value = {
            "tenant_id": "123", "platform": "pro", "principal_kind": "provider",
        }
        initialize_native_connections()
        connection = SourceConnection.objects.get(source_kind="native")
        ciphertext = connection.credential_ciphertext
        initialize_native_connections()
        connection.refresh_from_db()
        assert connection.credential_ciphertext == ciphertext
        assert connection.verified_at is not None
        assert start.call_count == 1


def test_auto_setup_disabled_when_no_secret(monkeypatch):
    from agione_ops.native_auto_setup import initialize_native_connections

    monkeypatch.delenv("AGIONE_OPS_BOOTSTRAP_CREDENTIALS", raising=False)
    initialize_native_connections()
    assert not SourceConnection.objects.exists()


def test_auto_setup_rolls_back_if_source_identity_is_wrong(settings, monkeypatch):
    from django.core.management.base import CommandError
    from agione_ops.native_auto_setup import initialize_native_connections

    settings.AGIONE_OPS_NATIVE_ENABLED = True
    settings.AGIONE_OPS_ALLOWED_ENDPOINT_HOSTS = ["allowed.example"]
    user = get_user_model().objects.create_user(username="mismatch-owner")
    rows = [{"platform": "pro", "principal_kind": "provider",
             "endpoint": "https://allowed.example", "expected_tenant_id": "123",
             "credentials": {"auth_mode": "aksk", "access_key": "fake-ak",
                             "secret_key": "fake-sk"}}]
    monkeypatch.setenv("AGIONE_OPS_BOOTSTRAP_CREDENTIALS", json.dumps(rows))
    monkeypatch.setenv("AGIONE_OPS_BOOTSTRAP_USER_ID", str(user.pk))
    with patch("agione_ops.tasks.start_initial_native_sync"), patch(
        "agione_ops.native_auto_setup.NativeClient"
    ) as client:
        client.return_value.__enter__.return_value.identity.return_value = {
            "tenant_id": "999", "platform": "pro", "principal_kind": "provider",
        }
        with pytest.raises(CommandError):
            initialize_native_connections()
    assert not SourceConnection.objects.exists()
