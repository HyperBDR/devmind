from types import SimpleNamespace

import pytest

from data_ops.models import DataOpsGlobalConfig
from data_ops.models import SyncIssueCode, SyncStatus, SyncTableStatus
from data_ops.services.feishu.client import FeishuBitableClient
from data_ops.services.feishu.client import run_bitable_access_check


def test_check_table_access_reports_missing_table_config(monkeypatch):
    def fail_list_fields(*args, **kwargs):
        raise AssertionError("list_fields should not be called")

    monkeypatch.setattr(
        "data_ops.services.feishu.client.FeishuBitableClient.list_fields",
        fail_list_fields,
    )
    client = FeishuBitableClient(app_id="app", app_secret="secret")

    result = client.check_table_access(
        app_token="",
        table_id="",
        table_name="Contracts",
        expected_fields=["合同编号"],
    )

    assert result.status == SyncStatus.FAILED
    assert result.issue_code == SyncIssueCode.CONFIG_MISSING
    assert "配置缺失" in result.message


@pytest.mark.django_db
def test_client_uses_global_config_before_environment_credentials(
    monkeypatch,
):
    monkeypatch.setenv("DATA_OPS_FEISHU_APP_ID", "env_app")
    monkeypatch.setenv("DATA_OPS_FEISHU_APP_SECRET", "env_secret")
    DataOpsGlobalConfig.objects.create(
        singleton_key=1,
        feishu_app_id="db_app",
        feishu_app_secret="db_secret",
    )

    client = FeishuBitableClient()
    config = DataOpsGlobalConfig.get_solo()

    assert client.app_id == "db_app"
    assert client.app_secret == "db_secret"
    assert config.feishu_app_secret != "db_secret"
    assert config.get_feishu_app_secret() == "db_secret"


@pytest.mark.django_db
def test_client_falls_back_to_environment_for_incomplete_global_config(
    monkeypatch,
):
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
    monkeypatch.setenv("DATA_OPS_FEISHU_APP_ID", "env_app")
    monkeypatch.setenv("DATA_OPS_FEISHU_APP_SECRET", "env_secret")
    DataOpsGlobalConfig.objects.create(
        singleton_key=1,
        feishu_app_id="db_app",
        feishu_app_secret="",
    )

    client = FeishuBitableClient()

    assert client.app_id == "env_app"
    assert client.app_secret == "env_secret"


@pytest.mark.django_db
def test_client_prefers_data_ops_environment_credentials(
    monkeypatch,
):
    monkeypatch.setenv("DATA_OPS_FEISHU_APP_ID", "data_ops_app")
    monkeypatch.setenv("DATA_OPS_FEISHU_APP_SECRET", "data_ops_secret")
    monkeypatch.setenv("FEISHU_APP_ID", "shared_app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "shared_secret")

    client = FeishuBitableClient()

    assert client.app_id == "data_ops_app"
    assert client.app_secret == "data_ops_secret"


@pytest.mark.django_db
def test_client_does_not_mix_partial_environment_credential_pairs(
    monkeypatch,
):
    monkeypatch.setenv("FEISHU_APP_ID", "incomplete_app")
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
    monkeypatch.setenv("DATA_OPS_FEISHU_APP_ID", "fallback_app")
    monkeypatch.setenv("DATA_OPS_FEISHU_APP_SECRET", "fallback_secret")

    client = FeishuBitableClient()

    assert client.app_id == "fallback_app"
    assert client.app_secret == "fallback_secret"


def test_list_records_marks_incomplete_when_total_is_not_reached(monkeypatch):
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            json=lambda: {
                "code": 0,
                "data": {
                    "has_more": False,
                    "total": 2,
                    "items": [{"record_id": "rec1", "fields": {}}],
                },
            },
            status_code=200,
            request=SimpleNamespace(),
        )

    monkeypatch.setattr("data_ops.services.feishu.client.httpx.get", fake_get)
    client = FeishuBitableClient(app_id="app", app_secret="secret")
    client._tenant_token = "tenant"

    records, incomplete, total = client.list_records("app_token", "table_id")

    assert len(records) == 1
    assert incomplete is True
    assert total == 2
    assert calls[0]["params"]["automatic_fields"] is True


def test_list_records_falls_back_when_automatic_fields_are_forbidden(
    monkeypatch,
):
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(kwargs["params"])
        if len(calls) == 1:
            return SimpleNamespace(
                json=lambda: {"code": 91403, "msg": "Forbidden"},
                status_code=403,
                request=SimpleNamespace(),
            )
        return SimpleNamespace(
            json=lambda: {
                "code": 0,
                "data": {
                    "has_more": False,
                    "total": 1,
                    "items": [{"record_id": "rec1", "fields": {}}],
                },
            },
            status_code=200,
            request=SimpleNamespace(),
        )

    monkeypatch.setattr("data_ops.services.feishu.client.httpx.get", fake_get)
    client = FeishuBitableClient(app_id="app", app_secret="secret")
    client._tenant_token = "tenant"

    records, incomplete, total = client.list_records("app_token", "table_id")

    assert len(records) == 1
    assert incomplete is False
    assert total == 1
    assert calls[0]["automatic_fields"] is True
    assert "automatic_fields" not in calls[1]


def test_access_check_warns_when_record_count_drops(monkeypatch, db):
    monkeypatch.setenv("DATA_OPS_FEISHU_APP_ID", "app_id")
    monkeypatch.setenv("DATA_OPS_FEISHU_APP_SECRET", "app_secret")
    SyncTableStatus.objects.create(
        source_key="domestic",
        table_key="contracts",
        app_token="app_token",
        table_id="table_id",
        table_name="Contracts",
        status=SyncStatus.OK,
        record_count=10,
        expected_record_floor=10,
    )

    monkeypatch.setattr(
        (
            "data_ops.services.feishu.client.FeishuBitableClient."
            "get_tenant_access_token"
        ),
        lambda self: "tenant",
    )
    monkeypatch.setattr(
        (
            "data_ops.services.feishu.client.FeishuBitableClient."
            "check_table_access"
        ),
        lambda self, **kwargs: SimpleNamespace(
            status=SyncStatus.OK,
            issue_code="",
            message="",
            resolution_hint="",
            record_count=2,
            expected_fields=[],
            missing_fields=[],
            expected_min_records=None,
        ),
    )

    statuses = run_bitable_access_check(
        source_key="domestic",
        table_key="contracts",
    )

    assert statuses[0].status == SyncStatus.WARNING
    assert statuses[0].expected_record_floor == 10
    assert "低于历史" in statuses[0].message
