from datetime import timedelta

import pytest
from django.utils import timezone

from data_ops.models import (
    CollectionFrequency,
    FeishuBitableCollectionConfig,
    SyncJob,
    SyncStatus,
)
from data_ops.services.feishu.config import (
    due_bitable_collection_configs,
    is_config_due,
)
from data_ops.tasks import run_scheduled_sync_task


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
        "data_ops.tasks.run_table_sync_task.delay",
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
