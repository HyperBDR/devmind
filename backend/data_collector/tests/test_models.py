"""
Tests for data_collector models.
"""
import pytest
from django.contrib.auth.models import User

from data_collector.models import CollectorConfig, RawDataRecord, RawDataAttachment


@pytest.mark.django_db
class TestCollectorConfig:
    def test_create_config(self, user):
        config = CollectorConfig.objects.create(
            user=user,
            platform="jira",
            key="my_jira",
            value={"schedule_cron": "0 * * * *", "runtime_state": {}},
            is_enabled=True,
        )
        assert config.platform == "jira"
        assert config.key == "my_jira"
        assert config.version == 0
        assert config.uuid is not None

    def test_unique_user_platform(self, user):
        CollectorConfig.objects.create(
            user=user,
            platform="jira",
            key="k1",
            value={},
        )
        with pytest.raises(Exception):
            CollectorConfig.objects.create(
                user=user,
                platform="jira",
                key="k2",
                value={},
            )

    def test_str(self, collector_config):
        assert "jira" in str(collector_config) or str(collector_config.user_id) in str(collector_config)


@pytest.mark.django_db
class TestRawDataRecord:
    def test_create_record(self, user):
        record = RawDataRecord.objects.create(
            user=user,
            platform="jira",
            source_unique_id="PROJ-1",
            raw_data={"key": "PROJ-1"},
            data_hash="h1",
        )
        assert record.platform == "jira"
        assert record.source_unique_id == "PROJ-1"
        assert record.uuid is not None
        assert record.is_deleted is False


@pytest.mark.django_db
class TestRawDataAttachment:
    def test_create_attachment(self, user):
        record = RawDataRecord.objects.create(
            user=user,
            platform="jira",
            source_unique_id="PROJ-1",
            raw_data={},
            data_hash="abc",
        )
        att = RawDataAttachment.objects.create(
            raw_record=record,
            file_name="test.txt",
            file_path="/opt/storage/data_collector/test.txt",
            file_url="/media/storage/data_collector/test.txt",
            file_type="text/plain",
        )
        assert att.raw_record_id == record.uuid
        assert att.file_name == "test.txt"
