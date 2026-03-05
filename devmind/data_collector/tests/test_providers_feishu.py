"""
Unit tests for Feishu provider: time helpers, authenticate, list_projects, fetch_attachments.
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from data_collector.services.providers.feishu import FeishuProvider
from data_collector.utils import from_unix_ms, to_unix_ms


@pytest.mark.unit
class TestFeishuTimeHelpers:
    def test_to_unix_ms_from_datetime_utc(self):
        dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        ms = to_unix_ms(dt)
        assert isinstance(ms, int)
        assert ms == 1736942400000

    def test_to_unix_ms_from_iso_string(self):
        ms = to_unix_ms("2025-01-15T12:00:00+00:00")
        assert isinstance(ms, int)
        assert ms == 1736942400000

    def test_to_unix_ms_from_timestamp_seconds(self):
        ms = to_unix_ms(1736942400)
        assert ms == 1736942400000

    def test_from_unix_ms_returns_datetime(self):
        dt = from_unix_ms(1736942400000)
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 1
        assert dt.day == 15

    def test_from_unix_ms_none_for_invalid(self):
        assert from_unix_ms(None) is None
        assert from_unix_ms("") is None


@pytest.mark.unit
class TestFeishuProviderAuthenticate:
    def test_authenticate_returns_false_when_empty_config(self):
        provider = FeishuProvider()
        assert provider.authenticate({}) is False

    @patch("data_collector.services.providers.feishu.requests.post")
    def test_authenticate_success(self, mock_post):
        mock_post.return_value.json.return_value = {
            "code": 0,
            "tenant_access_token": "t",
            "expire": 7200,
        }
        mock_post.return_value.raise_for_status = lambda: None
        provider = FeishuProvider()
        assert provider.authenticate({"app_id": "id", "app_secret": "secret"}) is True

    @patch("data_collector.services.providers.feishu.requests.post")
    def test_authenticate_failure_returns_false(self, mock_post):
        mock_post.side_effect = ValueError("invalid credentials")
        provider = FeishuProvider()
        assert provider.authenticate({"app_id": "id", "app_secret": "wrong"}) is False


@pytest.mark.unit
class TestFeishuProviderListProjects:
    @patch("data_collector.services.providers.feishu.requests.post")
    @patch("data_collector.services.providers.feishu.requests.get")
    def test_list_projects_returns_approval_definitions(self, mock_get, mock_post):
        mock_post.return_value.json.return_value = {
            "code": 0,
            "tenant_access_token": "t",
            "expire": 7200,
        }
        mock_post.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.return_value = {
            "data": {
                "approvals": [
                    {"approval_code": "leave", "name": "请假"},
                    {"approval_code": "expense", "name": "报销"},
                ]
            }
        }
        mock_get.return_value.raise_for_status = lambda: None
        provider = FeishuProvider()
        projects = provider.list_projects({"app_id": "id", "app_secret": "secret"})
        assert len(projects) == 2
        assert projects[0]["key"] == "leave"
        assert projects[0]["name"] == "请假"


@pytest.mark.unit
class TestFeishuProviderFetchAttachments:
    def test_fetch_attachments_returns_list_from_form(self):
        provider = FeishuProvider()
        record = type("Rec", (), {"raw_data": {}})()
        out = provider.fetch_attachments({}, record)
        assert isinstance(out, list)
