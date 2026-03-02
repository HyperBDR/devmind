"""
Unit tests for data_collector Celery tasks.
Cover run_collect (time range, persist create/update/skip, config not found),
run_cleanup (retention, config not found), run_validate (mark deleted).
"""
from datetime import timedelta
from unittest.mock import patch, MagicMock

import pytest
from django.utils import timezone

from data_collector.models import CollectorConfig, RawDataRecord
from data_collector.tasks import run_collect, run_cleanup, run_validate


@pytest.mark.unit
@pytest.mark.django_db
class TestRunCollect:
    @patch("data_collector.tasks.get_provider")
    def test_run_collect_config_not_found_returns_error(self, mock_get_provider):
        result = run_collect("00000000-0000-0000-0000-000000000000")
        assert result["success"] is False
        assert "not found" in result.get("error", "").lower() or "Config" in result.get("error", "")
        mock_get_provider.assert_not_called()

    @patch("data_collector.tasks.get_provider")
    def test_run_collect_invalid_time_format_returns_error(
        self, mock_get_provider, collector_config
    ):
        result = run_collect(
            str(collector_config.uuid),
            start_time="not-a-date",
            end_time="2025-01-02T00:00:00Z",
        )
        assert result["success"] is False
        assert "Invalid" in result.get("error", "") or "format" in result.get("error", "").lower()

    @patch("data_collector.tasks.get_provider")
    def test_run_collect_start_after_end_returns_error(
        self, mock_get_provider, collector_config
    ):
        result = run_collect(
            str(collector_config.uuid),
            start_time="2025-01-02T00:00:00Z",
            end_time="2025-01-01T00:00:00Z",
        )
        assert result["success"] is False
        assert "before" in result.get("error", "").lower() or "start" in result.get("error", "").lower()

    @patch("data_collector.tasks.get_provider")
    def test_run_collect_calls_provider_and_updates_runtime(
        self, mock_get_provider, collector_config
    ):
        mock_provider = MagicMock()
        mock_provider.collect.return_value = []
        mock_get_provider.return_value = MagicMock(return_value=mock_provider)

        result = run_collect(str(collector_config.uuid))

        assert result["success"] is True
        assert result.get("records_created") == 0
        assert result.get("records_updated") == 0
        mock_provider.collect.assert_called_once()
        collector_config.refresh_from_db()
        runtime = (collector_config.value or {}).get("runtime_state") or {}
        assert "last_success_collect_at" in runtime
        assert "first_collect_at" in runtime

    @patch("data_collector.tasks.get_provider")
    def test_run_collect_first_run_uses_initial_range(
        self, mock_get_provider, collector_config
    ):
        collector_config.value = {
            "schedule_cron": "0 */2 * * *",
            "cleanup_cron": "0 3 * * *",
            "runtime_state": {},
            "initial_range": "3m",
        }
        collector_config.save()
        mock_provider = MagicMock()
        mock_provider.collect.return_value = []
        mock_get_provider.return_value = MagicMock(return_value=mock_provider)

        run_collect(str(collector_config.uuid))

        call_kw = mock_provider.collect.call_args
        start_time = call_kw[0][1]
        end_time = call_kw[0][2]
        delta = (end_time - start_time).days
        assert delta >= 85

    @patch("data_collector.tasks.get_provider")
    def test_run_collect_persists_new_record(
        self, mock_get_provider, collector_config
    ):
        mock_provider = MagicMock()
        mock_provider.collect.return_value = [
            {
                "source_unique_id": "PROJ-1",
                "raw_data": {"issue": {}},
                "filter_metadata": {},
                "data_hash": "abc",
                "source_created_at": None,
                "source_updated_at": None,
            },
        ]
        mock_get_provider.return_value = MagicMock(return_value=mock_provider)

        result = run_collect(str(collector_config.uuid))

        assert result["success"] is True
        assert result["records_created"] == 1
        assert result["records_updated"] == 0
        assert RawDataRecord.objects.filter(
            user_id=collector_config.user_id,
            platform=collector_config.platform,
            source_unique_id="PROJ-1",
        ).exists()

    @patch("data_collector.tasks.get_provider")
    def test_run_collect_updates_existing_record_when_hash_differs(
        self, mock_get_provider, collector_config
    ):
        now = timezone.now()
        RawDataRecord.objects.create(
            user_id=collector_config.user_id,
            platform=collector_config.platform,
            source_unique_id="PROJ-2",
            raw_data={"old": True},
            filter_metadata={},
            data_hash="old_hash",
            first_collected_at=now,
            last_collected_at=now,
        )
        mock_provider = MagicMock()
        mock_provider.collect.return_value = [
            {
                "source_unique_id": "PROJ-2",
                "raw_data": {"new": True},
                "filter_metadata": {"project": "PROJ"},
                "data_hash": "new_hash",
                "source_created_at": None,
                "source_updated_at": None,
            },
        ]
        mock_get_provider.return_value = MagicMock(return_value=mock_provider)

        result = run_collect(str(collector_config.uuid))

        assert result["success"] is True
        assert result["records_created"] == 0
        assert result["records_updated"] == 1
        rec = RawDataRecord.objects.get(
            user_id=collector_config.user_id,
            platform=collector_config.platform,
            source_unique_id="PROJ-2",
        )
        assert rec.data_hash == "new_hash"
        assert rec.raw_data == {"new": True}

    @patch("data_collector.tasks.get_provider")
    def test_run_collect_skips_item_without_source_unique_id(
        self, mock_get_provider, collector_config
    ):
        mock_provider = MagicMock()
        mock_provider.collect.return_value = [
            {
                "source_unique_id": "",
                "raw_data": {},
                "filter_metadata": {},
                "data_hash": "x",
                "source_created_at": None,
                "source_updated_at": None,
            },
        ]
        mock_get_provider.return_value = MagicMock(return_value=mock_provider)

        result = run_collect(str(collector_config.uuid))

        assert result["success"] is True
        assert result["records_created"] == 0
        assert result["records_updated"] == 0
        assert RawDataRecord.objects.filter(
            user_id=collector_config.user_id,
            platform=collector_config.platform,
        ).count() == 0

    @patch("data_collector.tasks.get_provider")
    def test_run_collect_skips_unchanged_when_hash_same(
        self, mock_get_provider, collector_config
    ):
        now = timezone.now()
        RawDataRecord.objects.create(
            user_id=collector_config.user_id,
            platform=collector_config.platform,
            source_unique_id="PROJ-3",
            raw_data={"same": True},
            filter_metadata={},
            data_hash="same_hash",
            first_collected_at=now,
            last_collected_at=now,
        )
        mock_provider = MagicMock()
        mock_provider.collect.return_value = [
            {
                "source_unique_id": "PROJ-3",
                "raw_data": {"same": True},
                "filter_metadata": {},
                "data_hash": "same_hash",
                "source_created_at": None,
                "source_updated_at": None,
            },
        ]
        mock_get_provider.return_value = MagicMock(return_value=mock_provider)

        result = run_collect(str(collector_config.uuid))

        assert result["success"] is True
        assert result["records_created"] == 0
        assert result["records_updated"] == 0

    @patch("data_collector.tasks.get_provider")
    def test_run_collect_unknown_platform_returns_success_zero_counts(
        self, mock_get_provider, collector_config
    ):
        collector_config.platform = "unknown_platform"
        collector_config.save()
        mock_get_provider.return_value = None

        result = run_collect(str(collector_config.uuid))

        assert result["success"] is True
        assert result["records_created"] == 0
        assert result["records_updated"] == 0


@pytest.mark.unit
@pytest.mark.django_db
class TestRunCleanup:
    def test_run_cleanup_config_not_found_returns_error(self):
        result = run_cleanup("00000000-0000-0000-0000-000000000000")
        assert result["success"] is False
        assert "not found" in result.get("error", "").lower() or "Config" in result.get("error", "")

    def test_run_cleanup_deletes_old_records_and_updates_state(
        self, collector_config
    ):
        old_date = timezone.now() - timedelta(days=200)
        RawDataRecord.objects.create(
            user_id=collector_config.user_id,
            platform=collector_config.platform,
            source_unique_id="OLD-1",
            raw_data={},
            filter_metadata={},
            data_hash="h",
            last_collected_at=old_date,
        )
        collector_config.value = {
            "retention_days": 180,
            "runtime_state": {},
        }
        collector_config.save()

        result = run_cleanup(str(collector_config.uuid))

        assert result["success"] is True
        assert result["records_deleted"] == 1
        assert not RawDataRecord.objects.filter(
            user_id=collector_config.user_id,
            platform=collector_config.platform,
            source_unique_id="OLD-1",
        ).exists()
        collector_config.refresh_from_db()
        runtime = (collector_config.value or {}).get("runtime_state") or {}
        assert "last_cleanup_at" in runtime

    def test_run_cleanup_keeps_recent_records(self, collector_config):
        recent = timezone.now() - timedelta(days=10)
        RawDataRecord.objects.create(
            user_id=collector_config.user_id,
            platform=collector_config.platform,
            source_unique_id="RECENT-1",
            raw_data={},
            filter_metadata={},
            data_hash="h",
            last_collected_at=recent,
        )
        collector_config.value = {"retention_days": 180, "runtime_state": {}}
        collector_config.save()

        result = run_cleanup(str(collector_config.uuid))

        assert result["success"] is True
        assert result["records_deleted"] == 0
        assert RawDataRecord.objects.filter(
            user_id=collector_config.user_id,
            platform=collector_config.platform,
            source_unique_id="RECENT-1",
        ).exists()


@pytest.mark.unit
@pytest.mark.django_db
class TestRunValidate:
    def test_run_validate_config_not_found_returns_error(self):
        result = run_validate(
            "00000000-0000-0000-0000-000000000000",
            "2025-01-01T00:00:00Z",
            "2025-01-02T00:00:00Z",
        )
        assert result["success"] is False
        assert "not found" in result.get("error", "").lower() or "Config" in result.get("error", "")

    @patch("data_collector.tasks.get_provider")
    def test_run_validate_marks_missing_as_deleted(
        self, mock_get_provider, collector_config
    ):
        now = timezone.now()
        RawDataRecord.objects.create(
            user_id=collector_config.user_id,
            platform=collector_config.platform,
            source_unique_id="MISS-1",
            raw_data={},
            filter_metadata={},
            data_hash="h",
            last_collected_at=now,
            is_deleted=False,
        )
        RawDataRecord.objects.create(
            user_id=collector_config.user_id,
            platform=collector_config.platform,
            source_unique_id="MISS-2",
            raw_data={},
            filter_metadata={},
            data_hash="h",
            last_collected_at=now,
            is_deleted=False,
        )
        mock_provider = MagicMock()
        mock_provider.validate.return_value = ["MISS-1"]
        mock_get_provider.return_value = MagicMock(return_value=mock_provider)

        result = run_validate(
            str(collector_config.uuid),
            (now - timedelta(days=1)).isoformat(),
            (now + timedelta(days=1)).isoformat(),
        )

        assert result["success"] is True
        assert result["records_marked_deleted"] == 1
        r1 = RawDataRecord.objects.get(
            user_id=collector_config.user_id,
            platform=collector_config.platform,
            source_unique_id="MISS-1",
        )
        assert r1.is_deleted is True
        r2 = RawDataRecord.objects.get(
            user_id=collector_config.user_id,
            platform=collector_config.platform,
            source_unique_id="MISS-2",
        )
        assert r2.is_deleted is False
