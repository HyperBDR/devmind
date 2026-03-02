"""
Unit tests for Jira provider: pure helpers _jql_date_range, _issue_raw_to_item,
_client validation (ValueError when auth missing).
"""
from datetime import date, datetime, timezone

import pytest

from data_collector.services.providers.jira import (
    JiraProvider,
    _client,
    _issue_raw_to_item,
    _jql_date_range,
    _to_utc_date,
)


@pytest.mark.unit
class TestJiraDateHelpers:
    def test_to_utc_date_returns_date_for_datetime(self):
        dt = datetime(2025, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert _to_utc_date(dt) == date(2025, 2, 1)

    def test_to_utc_date_returns_as_is_for_date(self):
        d = date(2025, 2, 1)
        assert _to_utc_date(d) == d

    def test_jql_date_range_returns_start_and_end_plus_one(self):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 5, tzinfo=timezone.utc)
        start_str, end_plus_one_str = _jql_date_range(start, end)
        assert start_str == "2025-01-01"
        assert end_plus_one_str == "2025-01-06"


@pytest.mark.unit
class TestIssueRawToItem:
    def test_returns_none_when_key_missing(self):
        assert _issue_raw_to_item({}, []) is None
        assert _issue_raw_to_item({"fields": {}}, []) is None

    def test_returns_item_with_source_unique_id_and_hash(self):
        issue_raw = {
            "key": "PROJ-1",
            "fields": {
                "created": "2025-01-01T00:00:00Z",
                "updated": "2025-01-02T00:00:00Z",
                "project": {"key": "PROJ"},
                "attachment": [{"id": "a1"}],
            },
        }
        comments = [{"id": "c1"}]
        item = _issue_raw_to_item(issue_raw, comments)
        assert item is not None
        assert item["source_unique_id"] == "PROJ-1"
        assert item["filter_metadata"] == {"project": "PROJ"}
        assert item["raw_data"]["issue"] == issue_raw
        assert item["raw_data"]["comments"] == comments
        assert item["raw_data"]["attachments"] == [{"id": "a1"}]
        assert len(item["data_hash"]) == 64
        assert item["source_created_at"] == "2025-01-01T00:00:00Z"
        assert item["source_updated_at"] == "2025-01-02T00:00:00Z"

    def test_same_payload_produces_same_hash(self):
        issue_raw = {"key": "X-1", "fields": {}}
        a = _issue_raw_to_item(issue_raw, [])
        b = _issue_raw_to_item(issue_raw, [])
        assert a["data_hash"] == b["data_hash"]


@pytest.mark.unit
class TestJiraClientValidation:
    def test_client_raises_when_base_url_empty(self):
        with pytest.raises(ValueError, match="base_url"):
            _client({})
        with pytest.raises(ValueError, match="base_url"):
            _client({"base_url": ""})

    def test_client_raises_for_cloud_without_email_or_token(self):
        with pytest.raises(ValueError, match="email and api_token"):
            _client({
                "base_url": "https://example.atlassian.net",
                "auth_version": "cloud",
            })
        with pytest.raises(ValueError, match="email and api_token"):
            _client({
                "base_url": "https://example.atlassian.net",
                "auth_version": "cloud",
                "email": "a@b.com",
            })

    def test_client_raises_for_legacy_without_username_or_password(self):
        with pytest.raises(ValueError, match="username and password"):
            _client({
                "base_url": "https://jira.example.com",
                "auth_version": "legacy",
            })
        with pytest.raises(ValueError, match="username and password"):
            _client({
                "base_url": "https://jira.example.com",
                "username": "u",
            })


@pytest.mark.unit
class TestJiraProviderFetchAttachments:
    def test_fetch_attachments_returns_from_raw_data_attachments(self):
        provider = JiraProvider()
        record = type("Rec", (), {"raw_data": {"attachments": [
            {
                "id": "f1",
                "filename": "a.txt",
                "content": "http://x/f1",
                "mimeType": "text/plain",
                "size": 10,
                "created": None,
                "updated": None,
            },
        ]}})()
        out = provider.fetch_attachments({}, record)
        assert len(out) == 1
        assert out[0]["source_file_id"] == "f1"
        assert out[0]["file_name"] == "a.txt"
        assert out[0]["file_url"] == "http://x/f1"

    def test_fetch_attachments_returns_empty_when_no_attachments(self):
        provider = JiraProvider()
        record = type("Rec", (), {"raw_data": {}})()
        assert provider.fetch_attachments({}, record) == []
