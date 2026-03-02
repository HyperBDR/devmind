"""
Unit tests for data_collector services: storage, beat_sync, providers.
"""
from unittest.mock import patch

import pytest
from django_celery_beat.models import PeriodicTask

from data_collector.models import RawDataRecord
from data_collector.services.beat_sync import (
    CLEANUP_TASK_NAME_PREFIX,
    COLLECT_TASK_NAME_PREFIX,
    sync_config_to_beat,
    unsync_config_from_beat,
)
from data_collector.services.providers import get_provider
from data_collector.services.providers.jira import JiraProvider
from data_collector.services.providers.feishu import FeishuProvider
from data_collector.services.storage import (
    attachment_file_path,
    attachment_file_url,
    ensure_attachment_dir,
    get_raw_data_attachment_dir,
)


@pytest.mark.unit
@pytest.mark.django_db
class TestStorage:
    def test_get_raw_data_attachment_dir_returns_path_with_record_uuid(
        self, collector_config
    ):
        record = RawDataRecord.objects.create(
            user_id=collector_config.user_id,
            platform=collector_config.platform,
            source_unique_id="R1",
            raw_data={},
            filter_metadata={},
            data_hash="h",
        )
        with patch("data_collector.services.storage.get_data_collector_root") as m:
            m.return_value = "/opt/storage/data_collector"
            path = get_raw_data_attachment_dir(record)
            root = "/opt/storage/data_collector"
            assert path == f"{root}/raw_data/{record.uuid}"
            m.assert_called_once()

    def test_attachment_file_path_joins_dir_and_attachment_uuid(
        self, collector_config
    ):
        record = RawDataRecord.objects.create(
            user_id=collector_config.user_id,
            platform=collector_config.platform,
            source_unique_id="R1",
            raw_data={},
            filter_metadata={},
            data_hash="h",
        )
        with patch("data_collector.services.storage.get_data_collector_root") as m:
            m.return_value = "/opt/storage/data_collector"
            path = attachment_file_path(record, "att-123")
            root = "/opt/storage/data_collector"
            assert path == f"{root}/raw_data/{record.uuid}/att-123"

    def test_attachment_file_url_returns_media_path(self, collector_config):
        record = RawDataRecord.objects.create(
            user_id=collector_config.user_id,
            platform=collector_config.platform,
            source_unique_id="R1",
            raw_data={},
            filter_metadata={},
            data_hash="h",
        )
        url = attachment_file_url(record, "att-456")
        base = "/media/storage/data_collector/raw_data"
        assert url == f"{base}/{record.uuid}/att-456"

    def test_ensure_attachment_dir_creates_dir_and_returns_path(
        self, collector_config, tmp_path
    ):
        record = RawDataRecord.objects.create(
            user_id=collector_config.user_id,
            platform=collector_config.platform,
            source_unique_id="R1",
            raw_data={},
            filter_metadata={},
            data_hash="h",
        )
        with patch("data_collector.services.storage.get_data_collector_root") as m:
            m.return_value = str(tmp_path)
            out = ensure_attachment_dir(record)
            expected_dir = tmp_path / "raw_data" / str(record.uuid)
            assert out == str(expected_dir)
            assert expected_dir.exists()
            assert expected_dir.is_dir()


@pytest.mark.unit
@pytest.mark.django_db
class TestBeatSync:
    def test_sync_config_to_beat_creates_tasks(self, collector_config):
        sync_config_to_beat(collector_config)
        uuid_str = str(collector_config.uuid)
        collect_name = f"{COLLECT_TASK_NAME_PREFIX}{uuid_str}"
        cleanup_name = f"{CLEANUP_TASK_NAME_PREFIX}{uuid_str}"
        assert PeriodicTask.objects.filter(name=collect_name).exists()
        assert PeriodicTask.objects.filter(name=cleanup_name).exists()

    def test_unsync_config_from_beat_removes_tasks(self, collector_config):
        sync_config_to_beat(collector_config)
        uuid_str = str(collector_config.uuid)
        collect_name = f"{COLLECT_TASK_NAME_PREFIX}{uuid_str}"
        cleanup_name = f"{CLEANUP_TASK_NAME_PREFIX}{uuid_str}"
        unsync_config_from_beat(collector_config)
        assert not PeriodicTask.objects.filter(name=collect_name).exists()
        assert not PeriodicTask.objects.filter(name=cleanup_name).exists()

    def test_sync_config_to_beat_uses_custom_cron_from_value(
        self, collector_config
    ):
        collector_config.value = {
            "schedule_cron": "5 */3 * * *",
            "cleanup_cron": "10 4 * * *",
            "runtime_state": {},
        }
        collector_config.save()
        sync_config_to_beat(collector_config)
        uuid_str = str(collector_config.uuid)
        collect_task = PeriodicTask.objects.get(
            name=f"{COLLECT_TASK_NAME_PREFIX}{uuid_str}"
        )
        cleanup_task = PeriodicTask.objects.get(
            name=f"{CLEANUP_TASK_NAME_PREFIX}{uuid_str}"
        )
        assert collect_task.crontab.minute == "5"
        assert collect_task.crontab.hour == "*/3"
        assert cleanup_task.crontab.minute == "10"
        assert cleanup_task.crontab.hour == "4"

    def test_sync_config_to_beat_invalid_cron_uses_defaults(
        self, collector_config
    ):
        collector_config.value = {
            "schedule_cron": "invalid",
            "cleanup_cron": "also-invalid",
            "runtime_state": {},
        }
        collector_config.save()
        sync_config_to_beat(collector_config)
        uuid_str = str(collector_config.uuid)
        collect_task = PeriodicTask.objects.get(
            name=f"{COLLECT_TASK_NAME_PREFIX}{uuid_str}"
        )
        assert collect_task.crontab is not None
        assert collect_task.crontab.minute == "0"
        hour = collect_task.crontab.hour
        assert "*/2" in hour or hour == "*/2"

    def test_sync_config_to_beat_respects_is_enabled(self, collector_config):
        collector_config.is_enabled = False
        collector_config.save()
        sync_config_to_beat(collector_config)
        uuid_str = str(collector_config.uuid)
        collect_task = PeriodicTask.objects.get(
            name=f"{COLLECT_TASK_NAME_PREFIX}{uuid_str}"
        )
        assert collect_task.enabled is False


@pytest.mark.unit
class TestGetProvider:
    def test_get_provider_jira_returns_jira_provider_class(self):
        assert get_provider("jira") is JiraProvider

    def test_get_provider_feishu_returns_feishu_provider_class(self):
        assert get_provider("feishu") is FeishuProvider

    def test_get_provider_unknown_returns_none(self):
        assert get_provider("unknown_platform") is None
        assert get_provider("") is None
