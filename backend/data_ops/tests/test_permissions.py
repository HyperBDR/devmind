from types import SimpleNamespace

from data_ops.permissions import HasDataOpsAdminAccess


def test_data_ops_admin_access_allows_staff(monkeypatch):
    monkeypatch.setattr(
        "data_ops.permissions.get_effective_feature_keys",
        lambda user: ["data_ops"],
    )
    request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=True, is_staff=True),
    )

    assert HasDataOpsAdminAccess().has_permission(request, None) is True


def test_data_ops_admin_access_allows_data_ops_role(monkeypatch):
    monkeypatch.setattr(
        "data_ops.permissions.get_effective_feature_keys",
        lambda user: ["data_ops"],
    )
    request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=True, is_staff=False),
    )

    assert HasDataOpsAdminAccess().has_permission(request, None) is True


def test_data_ops_admin_access_rejects_without_data_ops_role(monkeypatch):
    monkeypatch.setattr(
        "data_ops.permissions.get_effective_feature_keys",
        lambda user: ["admin_console"],
    )
    request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=True, is_staff=False),
    )

    assert HasDataOpsAdminAccess().has_permission(request, None) is False
