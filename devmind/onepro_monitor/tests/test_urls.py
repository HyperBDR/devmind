import pytest
from django.urls import resolve


@pytest.mark.django_db
class TestApiUrls:
    def test_data_source_list_resolves(self):
        match = resolve("/api/v1/onepro-monitor/data-sources/")
        assert match.url_name == "data-source-list"

    def test_task_detail_resolves(self):
        match = resolve("/api/v1/onepro-monitor/tasks/42/")
        assert match.url_name == "task-detail"
        assert match.kwargs["task_id"] == 42

    def test_dashboard_resolves(self):
        match = resolve("/api/v1/onepro-monitor/analyzer/dashboard/")
        assert match.url_name == "dashboard"
