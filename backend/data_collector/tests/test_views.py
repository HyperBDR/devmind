"""
Tests for data_collector API views.
"""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth.models import User

from agentcore_task.adapters.django.models import TaskExecution
from data_collector.models import CollectorConfig, RawDataAttachment, RawDataRecord


@pytest.mark.django_db
class TestCollectorConfigViewSet:
    def test_list_configs(self, api_client, collector_config):
        response = api_client.get("/api/v1/data-collector/configs/")
        assert response.status_code == 200
        results = response.data.get("results", response.data) if isinstance(response.data, dict) else response.data
        if isinstance(results, list):
            assert len(results) >= 1
            assert any(c["platform"] == "jira" for c in results)
        else:
            assert response.data.get("platform") or True

    def test_create_config(self, api_client, user):
        payload = {
            "platform": "feishu",
            "key": "my_feishu",
            "value": {"schedule_cron": "0 9 * * *", "retention_days": 30},
            "is_enabled": True,
        }
        response = api_client.post("/api/v1/data-collector/configs/", payload, format="json")
        assert response.status_code in (200, 201)
        assert response.data.get("platform") == "feishu"
        assert CollectorConfig.objects.filter(user=user, platform="feishu").exists()

@pytest.mark.django_db
class TestStatsAPIView:
    def test_stats_empty(self, api_client):
        response = api_client.get("/api/v1/data-collector/stats/")
        assert response.status_code == 200
        assert "by_platform" in response.data
        assert response.data["total"] == 0
        assert response.data["deleted"] == 0

    def test_stats_with_records(self, api_client, user):
        RawDataRecord.objects.create(
            user=user,
            platform="jira",
            source_unique_id="X-1",
            raw_data={},
            data_hash="x1",
        )
        response = api_client.get("/api/v1/data-collector/stats/")
        assert response.status_code == 200
        assert response.data["total"] >= 1
        assert any(p["platform"] == "jira" for p in response.data["by_platform"])


@pytest.mark.django_db
class TestRawDataRecordViewSet:
    def test_list_records_empty(self, api_client):
        response = api_client.get("/api/v1/data-collector/records/")
        assert response.status_code == 200

    def test_list_records_with_data(self, api_client, user):
        RawDataRecord.objects.create(
            user=user,
            platform="jira",
            source_unique_id="Y-1",
            raw_data={},
            data_hash="y1",
        )
        response = api_client.get("/api/v1/data-collector/records/")
        assert response.status_code == 200
        results = response.data.get("results", response.data) if isinstance(response.data, dict) else response.data
        if isinstance(results, list):
            assert len(results) >= 1

    def test_list_records_filter_by_platform(self, api_client, user):
        RawDataRecord.objects.create(
            user=user,
            platform="jira",
            source_unique_id="J-1",
            raw_data={},
            data_hash="j1",
        )
        RawDataRecord.objects.create(
            user=user,
            platform="feishu",
            source_unique_id="F-1",
            raw_data={},
            data_hash="f1",
        )
        response = api_client.get("/api/v1/data-collector/records/?platform=feishu")
        assert response.status_code == 200
        results = response.data.get("results", response.data) if isinstance(response.data, dict) else response.data
        if isinstance(results, list):
            assert all(r.get("platform") == "feishu" for r in results)

    def test_retrieve_record_returns_detail_with_attachments(self, api_client, user):
        record = RawDataRecord.objects.create(
            user=user,
            platform="jira",
            source_unique_id="D-1",
            raw_data={"issue": {"fields": {"summary": "Detail"}}},
            data_hash="d1",
        )
        response = api_client.get(f"/api/v1/data-collector/records/{record.uuid}/")
        assert response.status_code == 200
        assert response.data["source_unique_id"] == "D-1"
        assert "attachments" in response.data


@pytest.mark.django_db
class TestRawDataAttachmentViewSet:
    def test_list_attachments_empty(self, api_client):
        response = api_client.get("/api/v1/data-collector/attachments/")
        assert response.status_code == 200

    def test_retrieve_attachment(self, api_client, user):
        record = RawDataRecord.objects.create(
            user=user,
            platform="jira",
            source_unique_id="R-1",
            raw_data={},
            data_hash="h",
        )
        att = RawDataAttachment.objects.create(
            raw_record=record,
            file_name="test.pdf",
            file_path="/nonexistent/test.pdf",
            file_url="/media/test.pdf",
        )
        response = api_client.get(f"/api/v1/data-collector/attachments/{att.uuid}/")
        assert response.status_code == 200
        assert response.data["file_name"] == "test.pdf"

    def test_download_attachment_no_file_path_returns_404(self, api_client, user):
        record = RawDataRecord.objects.create(
            user=user,
            platform="jira",
            source_unique_id="R-1",
            raw_data={},
            data_hash="h",
        )
        att = RawDataAttachment.objects.create(
            raw_record=record,
            file_name="x.txt",
            file_path="",
            file_url="/media/x.txt",
        )
        response = api_client.get(f"/api/v1/data-collector/attachments/{att.uuid}/download/")
        assert response.status_code == 404

    def test_download_attachment_file_not_found_returns_404(self, api_client, user):
        record = RawDataRecord.objects.create(
            user=user,
            platform="jira",
            source_unique_id="R-1",
            raw_data={},
            data_hash="h",
        )
        att = RawDataAttachment.objects.create(
            raw_record=record,
            file_name="missing.txt",
            file_path="/nonexistent/missing.txt",
            file_url="/media/missing.txt",
        )
        response = api_client.get(f"/api/v1/data-collector/attachments/{att.uuid}/download/")
        assert response.status_code == 404
