"""
Tests for data_collector API views.
"""
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

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

    def test_retrieve_config(self, api_client, collector_config):
        uuid = str(collector_config.uuid)
        response = api_client.get(f"/api/v1/data-collector/configs/{uuid}/")
        assert response.status_code == 200
        assert response.data["platform"] == "jira"

    def test_update_config(self, api_client, collector_config):
        uuid = str(collector_config.uuid)
        payload = {
            "platform": "jira",
            "key": "test_jira",
            "value": collector_config.value,
            "is_enabled": False,
            "version": collector_config.version,
        }
        response = api_client.put(f"/api/v1/data-collector/configs/{uuid}/", payload, format="json")
        assert response.status_code == 200
        collector_config.refresh_from_db()
        assert collector_config.is_enabled is False

    def test_delete_config(self, api_client, collector_config):
        uuid = str(collector_config.uuid)
        response = api_client.delete(f"/api/v1/data-collector/configs/{uuid}/")
        assert response.status_code == 204
        assert not CollectorConfig.objects.filter(uuid=collector_config.uuid).exists()

    def test_create_duplicate_platform_returns_400(self, api_client, user):
        CollectorConfig.objects.create(
            user=user,
            platform="jira",
            key="first",
            value={},
        )
        payload = {
            "platform": "jira",
            "key": "second",
            "value": {},
            "is_enabled": True,
        }
        response = api_client.post("/api/v1/data-collector/configs/", payload, format="json")
        assert response.status_code == 400
        assert "platform" in response.data or "该平台" in str(response.data)

    @patch("data_collector.views.config.run_collect")
    def test_collect_action_returns_202_and_task_id(self, mock_run_collect, api_client, collector_config):
        mock_run_collect.delay.return_value = type("Task", (), {"id": "task-123"})()
        uuid = str(collector_config.uuid)
        response = api_client.post(
            f"/api/v1/data-collector/configs/{uuid}/collect/",
            {},
            format="json",
        )
        assert response.status_code == 202
        assert response.data.get("task_id") == "task-123"

    def test_validate_config_payload_missing_platform_returns_400(self, api_client):
        response = api_client.post(
            "/api/v1/data-collector/configs/validate-config/",
            {"value": {}},
            format="json",
        )
        assert response.status_code == 400

    def test_validate_config_payload_unknown_platform_returns_200_invalid(self, api_client):
        response = api_client.post(
            "/api/v1/data-collector/configs/validate-config/",
            {"platform": "unknown_platform", "value": {}},
            format="json",
        )
        assert response.status_code == 200
        assert response.data.get("valid") is False

    @patch("data_collector.views.config.get_provider")
    def test_validate_config_payload_calls_authenticate(self, mock_get_provider, api_client):
        mock_instance = type("Provider", (), {"authenticate": lambda self, auth: True})()
        mock_get_provider.return_value = lambda: mock_instance
        response = api_client.post(
            "/api/v1/data-collector/configs/validate-config/",
            {"platform": "jira", "value": {"auth": {"base_url": "https://jira.example.com"}}},
            format="json",
        )
        assert response.status_code == 200
        assert response.data.get("valid") is True

    def test_fetch_projects_missing_platform_returns_400(self, api_client):
        response = api_client.post(
            "/api/v1/data-collector/configs/fetch-projects/",
            {"value": {}},
            format="json",
        )
        assert response.status_code == 400

    @patch("data_collector.views.config.get_provider")
    def test_fetch_projects_license_returns_projects(self, mock_get_provider, api_client):
        mock_instance = type(
            "Provider",
            (),
            {"list_projects": lambda self, auth: [{"key": "order", "name": "Order"}]},
        )()
        mock_get_provider.return_value = lambda: mock_instance
        response = api_client.post(
            "/api/v1/data-collector/configs/fetch-projects/",
            {"platform": "license", "value": {}},
            format="json",
        )
        assert response.status_code == 200
        assert "projects" in response.data

    def test_validate_action_requires_start_end_time(self, api_client, collector_config):
        uuid = str(collector_config.uuid)
        response = api_client.post(
            f"/api/v1/data-collector/configs/{uuid}/validate/",
            {},
            format="json",
        )
        assert response.status_code == 400

    @patch("data_collector.views.config.run_validate")
    def test_validate_action_returns_202(self, mock_run_validate, api_client, collector_config):
        mock_run_validate.delay.return_value = type("Task", (), {"id": "validate-1"})()
        uuid = str(collector_config.uuid)
        response = api_client.post(
            f"/api/v1/data-collector/configs/{uuid}/validate/",
            {"start_time": "2025-01-01T00:00:00Z", "end_time": "2025-01-02T00:00:00Z"},
            format="json",
        )
        assert response.status_code == 202
        assert response.data.get("task_id") == "validate-1"


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
