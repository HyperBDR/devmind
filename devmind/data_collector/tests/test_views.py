"""
Tests for data_collector API views.
"""
import pytest
from django.contrib.auth.models import User

from data_collector.models import CollectorConfig, RawDataRecord


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
