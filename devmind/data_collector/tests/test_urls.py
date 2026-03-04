"""
Unit tests for data_collector URL resolution.
"""
import pytest
from django.urls import resolve, reverse


@pytest.mark.unit
@pytest.mark.django_db
class TestApiUrls:
    def test_config_list_resolves(self):
        match = resolve("/api/v1/data-collector/configs/")
        assert match.url_name == "config-list"

    def test_config_detail_resolves(self):
        # UUID is path arg
        match = resolve("/api/v1/data-collector/configs/00000000-0000-0000-0000-000000000001/")
        assert match.url_name == "config-detail"
        assert "uuid" in match.kwargs

    def test_records_list_resolves(self):
        match = resolve("/api/v1/data-collector/records/")
        assert match.url_name == "record-list"

    def test_stats_resolves(self):
        match = resolve("/api/v1/data-collector/stats/")
        assert match.func is not None

    def test_attachments_list_resolves(self):
        match = resolve("/api/v1/data-collector/attachments/")
        assert match.url_name == "attachment-list"
