from types import SimpleNamespace

import pytest

from data_ops.models import DataOpsGlobalConfig
from data_ops.models import SyncStatus, SyncTableStatus
from data_ops.services.feishu.client import FeishuBitableClient
from data_ops.services.feishu.client import run_bitable_access_check


def test_list_record_history_reads_all_pages(monkeypatch):
    pages = [
        {
            "code": 0,
            "data": {
                "has_more": True,
                "page_token": "next",
                "items": [
                    {
                        "fields_history": [
                            {"field_name": "合同金额", "update_time": "1"}
                        ]
                    }
                ],
            },
        },
        {
            "code": 0,
            "data": {
                "has_more": False,
                "items": [
                    {
                        "fields_history": [
                            {"field_name": "到期时间", "update_time": "2"}
                        ]
                    }
                ],
            },
        },
    ]
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(kwargs.get("params", {}))
        payload = pages[len(calls) - 1]
        return SimpleNamespace(
            json=lambda: payload,
            status_code=200,
            request=SimpleNamespace(),
        )

    monkeypatch.setattr("data_ops.services.feishu.client.httpx.get", fake_get)
    client = FeishuBitableClient(app_id="app", app_secret="secret")
    client._tenant_token = "tenant"

    result = client.list_record_history("app_token", "table_id", "record_id")

    assert [item["field_name"] for item in result] == [
        "合同金额",
        "到期时间",
    ]
    assert calls[0] == {"page_size": 100}
    assert calls[1] == {"page_size": 100, "page_token": "next"}


@pytest.mark.django_db
def test_client_uses_global_feishu_credentials_before_env(monkeypatch):
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


def test_list_records_marks_incomplete_when_total_is_not_reached(monkeypatch):
    def fake_get(*args, **kwargs):
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


def test_list_record_history_raises_on_incomplete_pagination(monkeypatch):
    def fake_get(*args, **kwargs):
        return SimpleNamespace(
            json=lambda: {
                "code": 0,
                "data": {"has_more": True, "items": []},
            },
            status_code=200,
            request=SimpleNamespace(),
        )

    monkeypatch.setattr("data_ops.services.feishu.client.httpx.get", fake_get)
    client = FeishuBitableClient(app_id="app", app_secret="secret")
    client._tenant_token = "tenant"

    try:
        client.list_record_history("app_token", "table_id", "record_id")
    except Exception as exc:
        assert "pagination incomplete" in str(exc)
    else:
        raise AssertionError("Expected incomplete pagination error")


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
