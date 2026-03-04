"""
Unit tests for data_collector serializers and Conflict exception.
"""
import pytest
from rest_framework.exceptions import ValidationError

from data_collector.models import CollectorConfig, RawDataAttachment, RawDataRecord
from data_collector.serializers import (
    Conflict,
    CollectorConfigListSerializer,
    CollectorConfigSerializer,
    RawDataAttachmentSerializer,
    RawDataRecordDetailSerializer,
    RawDataRecordListSerializer,
)


@pytest.mark.unit
class TestConflict:
    def test_conflict_status_code(self):
        assert Conflict.status_code == 409


@pytest.mark.unit
@pytest.mark.django_db
class TestCollectorConfigSerializer:
    def test_validate_value_accepts_dict(self, user):
        ser = CollectorConfigSerializer()
        data = ser.validate_value({"schedule_cron": "0 * * * *"})
        assert data["schedule_cron"] == "0 * * * *"
        assert "runtime_state" in data
        assert data["runtime_state"]["first_collect_at"] is None

    def test_validate_value_none_becomes_empty_dict(self, user):
        from data_collector.serializers import _default_runtime_state
        ser = CollectorConfigSerializer()
        data = ser.validate_value(None)
        assert "runtime_state" in data
        assert set(data["runtime_state"].keys()) == set(_default_runtime_state().keys())

    def test_validate_value_rejects_non_dict(self, user):
        ser = CollectorConfigSerializer()
        with pytest.raises(ValidationError) as exc_info:
            ser.validate_value("not a dict")
        assert "value must be a JSON object" in str(exc_info.value.detail)

    def test_validate_value_runtime_state_must_be_dict(self, user):
        ser = CollectorConfigSerializer()
        with pytest.raises(ValidationError) as exc_info:
            ser.validate_value({"runtime_state": "invalid"})
        assert "runtime_state" in str(exc_info.value.detail)

    def test_update_raises_conflict_on_version_mismatch(self, user, collector_config):
        ser = CollectorConfigSerializer(instance=collector_config, data={
            "platform": collector_config.platform,
            "key": collector_config.key,
            "value": collector_config.value,
            "is_enabled": True,
            "version": 999,
        }, partial=True)
        ser.is_valid(raise_exception=True)
        with pytest.raises(Conflict):
            ser.save()

    def test_update_merges_value_and_preserves_auth_password(self, user, collector_config):
        collector_config.value = {
            "auth": {"username": "u", "password": "secret", "base_url": "https://jira.example.com"},
            "runtime_state": {},
        }
        collector_config.save()
        ser = CollectorConfigSerializer(instance=collector_config, data={
            "platform": collector_config.platform,
            "key": collector_config.key,
            "value": {"schedule_cron": "0 9 * * *"},
            "is_enabled": True,
            "version": collector_config.version,
        }, partial=True)
        ser.is_valid(raise_exception=True)
        updated = ser.save()
        assert updated.value.get("auth", {}).get("password") == "secret"
        assert updated.value.get("schedule_cron") == "0 9 * * *"


@pytest.mark.unit
@pytest.mark.django_db
class TestCollectorConfigListSerializer:
    def test_get_schedule_cron_from_value(self, collector_config):
        collector_config.value = {"schedule_cron": "5 * * * *", "runtime_state": {}}
        collector_config.save()
        data = CollectorConfigListSerializer(instance=collector_config).data
        assert data["schedule_cron"] == "5 * * * *"

    def test_get_schedule_cron_default(self, collector_config):
        collector_config.value = {}
        collector_config.save()
        data = CollectorConfigListSerializer(instance=collector_config).data
        assert data["schedule_cron"] == "0 */2 * * *"


@pytest.mark.unit
@pytest.mark.django_db
class TestRawDataRecordListSerializer:
    def test_display_title_jira_summary(self, user):
        record = RawDataRecord.objects.create(
            user=user,
            platform="jira",
            source_unique_id="PROJ-1",
            raw_data={
                "issue": {"fields": {"summary": "Fix login bug"}},
            },
            filter_metadata={},
            data_hash="h",
        )
        data = RawDataRecordListSerializer(instance=record).data
        assert data["display_title"] == "Fix login bug"

    def test_display_title_jira_fallback_to_source_id(self, user):
        record = RawDataRecord.objects.create(
            user=user,
            platform="jira",
            source_unique_id="PROJ-2",
            raw_data={"issue": {"fields": {}}},
            filter_metadata={},
            data_hash="h",
        )
        data = RawDataRecordListSerializer(instance=record).data
        assert data["display_title"] == "PROJ-2"

    def test_display_title_feishu_approval_name(self, user):
        record = RawDataRecord.objects.create(
            user=user,
            platform="feishu",
            source_unique_id="inst-1",
            raw_data={"approval": {"name": "请假申请"}},
            filter_metadata={},
            data_hash="h",
        )
        data = RawDataRecordListSerializer(instance=record).data
        assert data["display_title"] == "请假申请"

    def test_display_title_license_order_code(self, user):
        record = RawDataRecord.objects.create(
            user=user,
            platform="license",
            source_unique_id="ORD-001",
            raw_data={"order": {"code": "ORD-001", "category": {"name": "License"}}},
            filter_metadata={},
            data_hash="h",
        )
        data = RawDataRecordListSerializer(instance=record).data
        assert data["display_title"] == "ORD-001"

    def test_attachment_count_from_raw_data(self, user):
        record = RawDataRecord.objects.create(
            user=user,
            platform="jira",
            source_unique_id="X-1",
            raw_data={"attachments": [{"id": "a1"}, {"id": "a2"}]},
            filter_metadata={},
            data_hash="h",
        )
        data = RawDataRecordListSerializer(instance=record).data
        assert data["attachment_count"] == 2

    def test_attachment_count_non_list_returns_zero(self, user):
        record = RawDataRecord.objects.create(
            user=user,
            platform="jira",
            source_unique_id="X-2",
            raw_data={"attachments": "not-a-list"},
            filter_metadata={},
            data_hash="h",
        )
        data = RawDataRecordListSerializer(instance=record).data
        assert data["attachment_count"] == 0


@pytest.mark.unit
@pytest.mark.django_db
class TestRawDataRecordDetailSerializer:
    def test_get_attachments_returns_list_with_uuid_and_file_name(self, user):
        record = RawDataRecord.objects.create(
            user=user,
            platform="jira",
            source_unique_id="R-1",
            raw_data={},
            filter_metadata={},
            data_hash="h",
        )
        RawDataAttachment.objects.create(
            raw_record=record,
            file_name="doc.pdf",
            file_path="/opt/x/doc.pdf",
            file_url="/media/x/doc.pdf",
            file_type="application/pdf",
            file_size=100,
        )
        data = RawDataRecordDetailSerializer(instance=record).data
        assert len(data["attachments"]) == 1
        assert data["attachments"][0]["file_name"] == "doc.pdf"
        assert "uuid" in data["attachments"][0]


@pytest.mark.unit
@pytest.mark.django_db
class TestRawDataAttachmentSerializer:
    def test_serialize_attachment(self, user):
        record = RawDataRecord.objects.create(
            user=user,
            platform="jira",
            source_unique_id="R-1",
            raw_data={},
            data_hash="h",
        )
        att = RawDataAttachment.objects.create(
            raw_record=record,
            file_name="f.txt",
            file_path="/p/f.txt",
            file_url="/media/p/f.txt",
            file_type="text/plain",
            file_size=42,
        )
        data = RawDataAttachmentSerializer(instance=att).data
        assert data["file_name"] == "f.txt"
        assert data["file_size"] == 42
