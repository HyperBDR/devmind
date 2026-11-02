"""Tenant overrides are shared within an authorized Operator scope."""
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient

from agione_ops.models import SourceConnection

pytestmark = pytest.mark.django_db


def test_tenant_override_is_unique_per_operator_and_records_actor():
    from agione_ops.models import TenantClassification

    user = get_user_model().objects.create_user(username="tenant-operator")
    operator = SourceConnection.objects.create(
        name="Operator", platform="pro", principal_kind="operator",
        source_kind="native", created_by=user,
    )
    TenantClassification.objects.create(
        operator=operator, tenant_id="123", classification="internal",
        updated_by=user,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        TenantClassification.objects.create(
            operator=operator, tenant_id="123", classification="external",
            updated_by=user,
        )


def test_effective_classification_preserves_defaults_and_manual_override():
    from agione_ops.native_account_scope import tenant_classification

    fixed = "85086211957448704"
    assert tenant_classification(fixed, {}, {}) == ("internal", "automatic")
    assert tenant_classification(fixed, {}, {fixed: "external"}) == (
        "external", "manual",
    )
    assert tenant_classification("200", {"tenant:200": "internal"}, {}) == (
        "internal", "automatic",
    )
    assert tenant_classification("200", {"tenant:200": "internal"},
                                 {"200": "external"}) == ("external", "manual")
    assert tenant_classification("201", {}, {}) == ("unknown", "automatic")


def test_manual_external_tenant_includes_automatically_internal_users():
    from agione_ops.native_account_scope import external_rows

    row = {
        "customer_id": "200",
        "user_id": "internal-user",
        "subject_type": "USER",
    }
    types = {
        "tenant:200": "internal",
        "200:internal-user": "internal",
    }
    assert external_rows([row], types) == []
    assert external_rows([row], types, {"200": "external"}) == [row]


def test_directory_falls_back_when_upstream_rejects_larger_page(
    monkeypatch, settings,
):
    from types import SimpleNamespace

    from agione_ops.client import AgioneOpsError
    from agione_ops.tenant_directory import tenant_directory

    settings.AGIONE_OPS_NATIVE_ENABLED = True
    connection = SimpleNamespace(pk="connection", config_version=1,
                                 credential_version=1)
    operator = SimpleNamespace(pk="operator", config_version=1,
                               credential_version=1)
    user = SimpleNamespace(pk=1)
    sizes = []

    class Source:
        def __init__(self, *args):
            pass

        def pages(self, *args, **kwargs):
            size = kwargs.get("directory_page_size", 50)
            sizes.append(size)
            if size == 100:
                raise AgioneOpsError("SOURCE_REJECTED")
            return [{"tenantId": "123"}]

        def guard(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr("agione_ops.tenant_directory._operator", lambda *args: operator)
    monkeypatch.setattr("agione_ops.tenant_directory.LiveSource", Source)
    monkeypatch.setattr("agione_ops.tenant_directory.operator_overrides", lambda value: {})
    _, rows, _, _ = tenant_directory(connection, user)
    assert [row["tenantId"] for row in rows] == ["123"]
    assert sizes == [100, 50]


def test_preloaded_directory_is_scoped_to_credential_version(
    monkeypatch, settings,
):
    from types import SimpleNamespace

    from django.core.cache import cache

    from agione_ops.tenant_directory import cache_directory, tenant_directory

    settings.AGIONE_OPS_NATIVE_ENABLED = True
    cache.clear()
    operator = SimpleNamespace(pk="warm", config_version=1,
                               credential_version=1)
    monkeypatch.setattr(
        "agione_ops.tenant_directory._operator", lambda *args: operator,
    )
    monkeypatch.setattr(
        "agione_ops.tenant_directory.operator_overrides", lambda value: {},
    )
    cache_directory(operator, [{"tenantId": "123", "customerName": "A"}])
    _, rows, _, _ = tenant_directory(operator, object(), use_cache=True)
    assert rows == [{"tenantId": "123", "customerName": "A"}]
    operator.credential_version = 2
    monkeypatch.setattr(
        "agione_ops.tenant_directory.LiveSource",
        lambda *args: (_ for _ in ()).throw(RuntimeError("fresh read")),
    )
    with pytest.raises(RuntimeError, match="fresh read"):
        tenant_directory(operator, object(), use_cache=True)


def test_directory_requires_grant_and_uses_operator_scope(monkeypatch, settings):
    from agione_ops.models import (
        ConnectionGrant, TenantClassification, TenantClassificationChange,
    )
    from django.core.cache import cache

    settings.AGIONE_OPS_NATIVE_ENABLED = True
    cache.clear()
    reads = []
    users = get_user_model()
    user = users.objects.create_user(username="directory-user")
    other = users.objects.create_user(username="directory-other")
    permission = Permission.objects.get(
        content_type__app_label="agione_ops", codename="view_business",
    )
    user.user_permissions.add(permission)
    other.user_permissions.add(permission)
    operator = SourceConnection.objects.create(
        name="Operator", platform="pro", principal_kind="operator",
        source_kind="native", created_by=user, enabled=True,
    )
    grant = ConnectionGrant.objects.create(
        connection=operator, user=user, can_view=True,
    )
    other_grant = ConnectionGrant.objects.create(
        connection=operator, user=other, can_view=True,
    )
    TenantClassification.objects.create(
        operator=operator, tenant_id="123", classification="external",
        updated_by=user,
    )

    class Source:
        def __init__(self, connection, actor, factory):
            assert connection == operator
            assert actor in {user, other}

        def pages(self, *args, **kwargs):
            reads.append(1)
            return [
                {"tenantId": "123", "customerName": "Alpha",
                 "adminEmail": "a@oneprocloud.com"},
                {"tenantId": "456", "customerName": "beta@example.com",
                 "adminEmail": "b@example.com"},
            ]

        def guard(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr("agione_ops.tenant_directory.LiveSource", Source)
    client = APIClient()
    url = f"/api/v1/agione-ops/connections/{operator.pk}/tenant-classifications/"
    client.force_authenticate(user)
    response = client.get(url)
    assert response.status_code == 200
    assert response.data["data"]["results"][0]["classification"] == "external"
    assert response.data["data"]["results"][0]["source"] == "manual"
    assert response.data["data"]["results"][1]["name"] == "beta@example.com"
    assert "adminEmail" not in str(response.data)
    filtered = client.get(url, {"search": "ALP", "source": "manual"})
    assert filtered.data["data"]["count"] == 1
    assert filtered.data["data"]["results"][0]["tenantId"] == "123"
    page = client.get(url, {"limit": 1, "offset": 1})
    assert page.data["data"]["count"] == 2
    assert page.data["data"]["results"][0]["tenantId"] == "456"
    assert len(reads) == 1
    client.force_authenticate(other)
    assert client.get(url).status_code == 200
    assert len(reads) == 1
    client.force_authenticate(user)
    assert client.get(url, {"refresh": 1}).status_code == 200
    assert client.get(url).status_code == 200
    assert len(reads) == 2
    assert client.get(url, {"limit": 0}).status_code == 400
    assert client.get(url, {"source": "invalid"}).status_code == 400
    version = response.data["data"]["version"]
    payload = {"tenantId": "123", "classification": "internal",
               "version": version}
    assert client.post(url, payload, format="json").status_code == 403
    user.user_permissions.add(Permission.objects.get(
        content_type__app_label="agione_ops", codename="manage_connections",
    ))
    changed = client.post(url, payload, format="json")
    assert changed.status_code == 200, changed.data
    assert len(reads) == 2
    assert changed.data["data"]["classification"] == "internal"
    assert changed.data["data"]["included"] is False
    assert changed.data["data"]["financeState"] == "queued"
    assert TenantClassificationChange.objects.filter(operator=operator).count() == 1
    assert client.post(url, payload, format="json").status_code == 409
    assert TenantClassification.objects.get(operator=operator).classification == "internal"
    invalid = {**payload, "tenantId": "999", "version": changed.data["data"]["version"]}
    assert client.post(url, invalid, format="json").status_code == 404
    payload.update(classification="automatic", version=changed.data["data"]["version"])
    assert client.post(url, payload, format="json").status_code == 200
    assert not TenantClassification.objects.filter(operator=operator).exists()
    assert TenantClassificationChange.objects.filter(operator=operator).count() == 2
    grant.can_view = False
    grant.save()
    assert client.get(url).status_code == 404
    other_grant.can_view = False
    other_grant.save()
    client.force_authenticate(other)
    assert client.get(url).status_code == 404
