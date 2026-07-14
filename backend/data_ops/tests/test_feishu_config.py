from datetime import timedelta

import httpx
import pytest
from django.utils import timezone

from data_ops.models import (
    CollectionFrequency,
    FeishuBitableCollectionConfig,
    SyncJob,
    SyncStatus,
)
from data_ops.services.feishu.config import (
    discover_bitable_table_ids,
    due_bitable_collection_configs,
    ensure_bitable_collection_configs,
    is_config_due,
)
from data_ops.services.feishu.mappings import (
    BITABLE_SOURCES,
    iter_default_collection_configs,
)
from data_ops.tasks import run_scheduled_sync_task


def test_default_mappings_do_not_contain_feishu_table_ids():
    configs = list(iter_default_collection_configs())

    assert len(configs) == 6
    assert {config["source_key"] for config in configs} == {"domestic"}
    assert all(config["table_id"] == "" for config in configs)
    assert all(
        "table_id" not in table
        for source in BITABLE_SOURCES.values()
        for table in source["tables"].values()
    )


@pytest.mark.django_db
def test_ensure_bitable_configs_removes_unsupported_legacy_sources():
    FeishuBitableCollectionConfig.objects.create(
        source_key="oversea",
        table_key="oversea_projects",
        app_token="legacy_base",
        table_id="legacy_table",
    )

    ensure_bitable_collection_configs()

    assert not FeishuBitableCollectionConfig.objects.filter(
        source_key="oversea",
    ).exists()


@pytest.mark.django_db
def test_ensure_bitable_configs_uses_environment_base_without_table_id(
    monkeypatch,
):
    monkeypatch.setenv(
        "DATA_OPS_FEISHU_DOMESTIC_APP_TOKEN",
        "current_base",
    )
    ensure_bitable_collection_configs()
    config = FeishuBitableCollectionConfig.objects.get(
        source_key="domestic",
        table_key="contracts",
    )

    assert config.app_token == "current_base"
    assert config.table_id == ""


@pytest.mark.django_db
def test_environment_base_replaces_stale_base_and_table_id(monkeypatch):
    FeishuBitableCollectionConfig.objects.create(
        source_key="domestic",
        table_key="contracts",
        app_token="stale_base",
        table_id="stale_table",
    )
    monkeypatch.setenv(
        "DATA_OPS_FEISHU_DOMESTIC_APP_TOKEN",
        "current_base",
    )

    ensure_bitable_collection_configs()

    config = FeishuBitableCollectionConfig.objects.get(
        source_key="domestic",
        table_key="contracts",
    )
    assert config.app_token == "current_base"
    assert config.table_id == ""


@pytest.mark.django_db
def test_discovery_resolves_table_id_from_live_table_name(monkeypatch):
    monkeypatch.setenv(
        "DATA_OPS_FEISHU_DOMESTIC_APP_TOKEN",
        "current_base",
    )

    class Client:
        def list_tables(self, app_token):
            assert app_token == "current_base"
            return [
                {
                    "name": "合同清单2025.3之后",
                    "table_id": "tbl_live",
                }
            ]

    result = discover_bitable_table_ids(
        client=Client(),
        source_key="domestic",
        table_key="contracts",
    )

    config = FeishuBitableCollectionConfig.objects.get(
        source_key="domestic",
        table_key="contracts",
    )
    assert config.table_id == "tbl_live"
    assert result["matched"] == 1
    assert result["updated"] == 1
    assert result["tables_seen"] == 1


@pytest.mark.django_db
def test_discovery_does_not_guess_when_table_name_is_ambiguous(
    monkeypatch,
):
    monkeypatch.setenv(
        "DATA_OPS_FEISHU_DOMESTIC_APP_TOKEN",
        "current_base",
    )

    class Client:
        def list_tables(self, app_token):
            return [
                {"name": "合同清单2025.3之后", "table_id": "tbl_a"},
                {"name": "合同清单2025.3之后", "table_id": "tbl_b"},
            ]

    result = discover_bitable_table_ids(
        client=Client(),
        source_key="domestic",
        table_key="contracts",
    )

    config = FeishuBitableCollectionConfig.objects.get(
        source_key="domestic",
        table_key="contracts",
    )
    assert config.table_id == ""
    assert result["matched"] == 0
    assert result["ambiguous"] == ["domestic/contracts"]


@pytest.mark.django_db
def test_discovery_returns_safe_feishu_error_details(monkeypatch):
    monkeypatch.setenv(
        "DATA_OPS_FEISHU_DOMESTIC_APP_TOKEN",
        "current_base",
    )

    class Client:
        def list_tables(self, app_token):
            request = httpx.Request("GET", "https://open.feishu.cn/private")
            response = httpx.Response(
                403,
                json={"code": 91403, "msg": "Forbidden"},
                headers={
                    "x-request-id": "request-123",
                    "x-tt-logid": "log-456",
                },
                request=request,
            )
            raise httpx.HTTPStatusError(
                "forbidden",
                request=request,
                response=response,
            )

    result = discover_bitable_table_ids(
        client=Client(),
        source_key="domestic",
        table_key="contracts",
    )

    error = result["errors"][0]
    assert error["http_status"] == 403
    assert error["feishu_code"] == 91403
    assert error["request_id"] == "request-123"
    assert error["log_id"] == "log-456"
    assert "private" not in str(error)


@pytest.mark.django_db
def test_ensure_bitable_configs_preserves_current_feishu_base_tokens():
    FeishuBitableCollectionConfig.objects.create(
        source_key="domestic",
        table_key="contracts",
        app_token="test_current_base_token",
        table_id="test_current_table_id",
    )

    ensure_bitable_collection_configs()

    config = FeishuBitableCollectionConfig.objects.get(
        source_key="domestic",
        table_key="contracts",
    )
    assert config.app_token == "test_current_base_token"
    assert config.table_id == "test_current_table_id"


@pytest.mark.django_db
def test_ensure_bitable_configs_preserves_custom_tokens(monkeypatch):
    monkeypatch.delenv(
        "DATA_OPS_FEISHU_DOMESTIC_APP_TOKEN",
        raising=False,
    )
    monkeypatch.delenv(
        "DATA_OPS_FEISHU_BITABLE_APP_TOKEN",
        raising=False,
    )
    FeishuBitableCollectionConfig.objects.create(
        source_key="domestic",
        table_key="contracts",
        source_name="Custom source",
        table_name="Custom table",
        app_token="custom_app",
        table_id="custom_table",
    )

    ensure_bitable_collection_configs()

    config = FeishuBitableCollectionConfig.objects.get(
        source_key="domestic",
        table_key="contracts",
    )
    assert config.app_token == "custom_app"
    assert config.table_id == "custom_table"


@pytest.mark.django_db
def test_is_config_due_uses_last_successful_schedule_time():
    now = timezone.now()
    config = FeishuBitableCollectionConfig.objects.create(
        source_key="domestic",
        table_key="contracts",
        app_token="app",
        table_id="table",
        sync_frequency=CollectionFrequency.DAILY,
        last_scheduled_at=now - timedelta(hours=23),
    )

    assert is_config_due(config, now) is False

    config.last_scheduled_at = now - timedelta(days=1, minutes=1)
    assert is_config_due(config, now) is True


@pytest.mark.django_db
def test_due_configs_excludes_configs_with_active_jobs(monkeypatch):
    monkeypatch.setattr(
        "data_ops.services.feishu.config.ensure_bitable_collection_configs",
        lambda: [],
    )
    config = FeishuBitableCollectionConfig.objects.create(
        source_key="domestic",
        table_key="contracts",
        app_token="app",
        table_id="table",
        sync_frequency=CollectionFrequency.HOURLY,
    )
    SyncJob.objects.create(
        source_key=config.source_key,
        table_key=config.table_key,
        status=SyncStatus.RUNNING,
    )

    assert due_bitable_collection_configs() == []


@pytest.mark.django_db
def test_due_configs_excludes_configs_when_full_sync_is_active(monkeypatch):
    monkeypatch.setattr(
        "data_ops.services.feishu.config.ensure_bitable_collection_configs",
        lambda: [],
    )
    FeishuBitableCollectionConfig.objects.create(
        source_key="domestic",
        table_key="contracts",
        app_token="app",
        table_id="table",
        sync_frequency=CollectionFrequency.HOURLY,
    )
    SyncJob.objects.create(
        source_key="",
        table_key="",
        status=SyncStatus.RUNNING,
    )

    assert due_bitable_collection_configs() == []


@pytest.mark.django_db
def test_due_configs_ignores_stale_active_jobs(monkeypatch):
    monkeypatch.setattr(
        "data_ops.services.feishu.config.ensure_bitable_collection_configs",
        lambda: [],
    )
    config = FeishuBitableCollectionConfig.objects.create(
        source_key="domestic",
        table_key="contracts",
        app_token="app",
        table_id="table",
        sync_frequency=CollectionFrequency.HOURLY,
    )
    now = timezone.now()
    SyncJob.objects.create(
        source_key=config.source_key,
        table_key=config.table_key,
        status=SyncStatus.RUNNING,
        started_at=now - timedelta(hours=4),
    )

    assert due_bitable_collection_configs(now) == [config]


@pytest.mark.django_db
def test_scheduled_sync_marks_job_failed_when_dispatch_fails(monkeypatch):
    monkeypatch.setattr(
        "data_ops.services.feishu.config.ensure_bitable_collection_configs",
        lambda: [],
    )
    monkeypatch.setattr(
        "data_ops.tasks.run_scheduled_sync_batch_task.delay",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("broker down")),
    )
    config = FeishuBitableCollectionConfig.objects.create(
        source_key="domestic",
        table_key="contracts",
        app_token="app",
        table_id="table",
        sync_frequency=CollectionFrequency.HOURLY,
    )

    result = run_scheduled_sync_task()

    job = SyncJob.objects.get(
        source_key=config.source_key,
        table_key=config.table_key,
    )
    assert result["queued"] == []
    assert result["failed"][0]["job_id"] == str(job.id)
    assert job.status == SyncStatus.FAILED
    assert "投递失败" in job.error_message


@pytest.mark.django_db
def test_scheduled_sync_dispatches_due_tables_as_one_serial_batch(monkeypatch):
    configs = [
        FeishuBitableCollectionConfig.objects.create(
            source_key="domestic",
            table_key=table_key,
            app_token="app",
            table_id=table_key,
            sync_frequency=CollectionFrequency.HOURLY,
        )
        for table_key in ("contracts", "sales_records")
    ]
    monkeypatch.setattr(
        "data_ops.services.feishu.config.due_bitable_collection_configs",
        lambda: configs,
    )
    dispatched = []
    monkeypatch.setattr(
        "data_ops.tasks.run_scheduled_sync_batch_task.delay",
        lambda **kwargs: dispatched.append(kwargs)
        or type("Result", (), {"id": "batch-task"})(),
    )

    result = run_scheduled_sync_task()

    assert len(dispatched) == 1
    assert [item["table_key"] for item in dispatched[0]["items"]] == [
        "contracts",
        "sales_records",
    ]
    assert len(result["queued"]) == 2
