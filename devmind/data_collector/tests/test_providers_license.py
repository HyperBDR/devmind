"""
Unit tests for License provider: _to_utc_datetime_str, _get_base_url,
LicenseProvider.list_projects, _order_raw_to_item, authenticate, collect, validate, fetch_attachments.
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from data_collector.services.providers.license import (
    LicenseProvider,
    _get_base_url,
    _to_utc_datetime_str,
)


@pytest.mark.unit
class TestLicenseHelpers:
    def test_to_utc_datetime_str_from_datetime(self):
        dt = datetime(2025, 1, 15, 12, 30, 0, tzinfo=timezone.utc)
        s = _to_utc_datetime_str(dt)
        assert s == "2025-01-15 12:30:00"

    def test_to_utc_datetime_str_none_returns_empty(self):
        assert _to_utc_datetime_str(None) == ""

    def test_to_utc_datetime_str_string_passthrough(self):
        assert _to_utc_datetime_str("2025-01-01 00:00:00") == "2025-01-01 00:00:00"

    def test_get_base_url_raises_when_empty(self):
        with pytest.raises(ValueError, match="base_url"):
            _get_base_url({})
        with pytest.raises(ValueError, match="base_url"):
            _get_base_url({"base_url": ""})

    def test_get_base_url_strips_trailing_slash(self):
        assert _get_base_url({"base_url": "https://auth.example.com/"}) == "https://auth.example.com"


@pytest.mark.unit
class TestLicenseProviderListProjects:
    def test_list_projects_returns_order_option(self):
        provider = LicenseProvider()
        projects = provider.list_projects({})
        assert len(projects) == 1
        assert projects[0]["key"] == "order"
        assert projects[0]["name"] == "Order collection"


@pytest.mark.unit
class TestLicenseProviderOrderRawToItem:
    def test_order_raw_to_item_returns_none_when_no_code(self):
        provider = LicenseProvider()
        assert provider._order_raw_to_item({}) is None
        assert provider._order_raw_to_item({"code": ""}) is None

    def test_order_raw_to_item_returns_item_with_code_and_hash(self):
        provider = LicenseProvider()
        order = {
            "code": "ORD-001",
            "created_at": "2025-01-01T00:00:00Z",
            "approval_at": "2025-01-02T00:00:00Z",
            "category": {"id": 1},
            "third_id": "ext-1",
        }
        item = provider._order_raw_to_item(order)
        assert item is not None
        assert item["source_unique_id"] == "ORD-001"
        assert item["raw_data"]["order"] == order
        assert len(item["data_hash"]) == 64
        assert item["filter_metadata"].get("category") == 1
        assert item["filter_metadata"].get("third_id") == "ext-1"


@pytest.mark.unit
class TestLicenseProviderAuthenticate:
    def test_authenticate_returns_false_when_empty_config(self):
        provider = LicenseProvider()
        assert provider.authenticate({}) is False

    @patch("data_collector.services.providers.license.requests.post")
    def test_authenticate_success(self, mock_post):
        mock_post.return_value.json.return_value = {"api_key": "key123"}
        mock_post.return_value.raise_for_status = lambda: None
        provider = LicenseProvider()
        assert provider.authenticate({
            "base_url": "https://auth.example.com",
            "username": "u",
            "password": "p",
        }) is True


@pytest.mark.unit
class TestLicenseProviderCollect:
    @patch("data_collector.services.providers.license.requests.post")
    @patch("data_collector.services.providers.license.requests.get")
    def test_collect_returns_orders_from_api(self, mock_get, mock_post):
        mock_post.return_value.json.return_value = {"api_key": "k"}
        mock_post.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.return_value = {
            "items": [
                {"code": "ORD-1", "created_at": None, "approval_at": None},
            ]
        }
        mock_get.return_value.raise_for_status = lambda: None
        provider = LicenseProvider()
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 2, tzinfo=timezone.utc)
        items = provider.collect(
            {"base_url": "https://auth.example.com", "username": "u", "password": "p"},
            start,
            end,
            user_id=1,
            platform="license",
            project_keys=["order"],
        )
        assert len(items) == 1
        assert items[0]["source_unique_id"] == "ORD-1"

    def test_collect_skips_when_project_keys_exclude_order(self):
        provider = LicenseProvider()
        items = provider.collect(
            {"base_url": "https://x.com", "username": "u", "password": "p"},
            None,
            None,
            user_id=1,
            platform="license",
            project_keys=["other"],
        )
        assert items == []


@pytest.mark.unit
class TestLicenseProviderValidate:
    @patch("data_collector.services.providers.license.requests.post")
    @patch("data_collector.services.providers.license.requests.get")
    def test_validate_returns_missing_codes(self, mock_get, mock_post):
        mock_post.return_value.json.return_value = {"api_key": "k"}
        mock_post.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.return_value = {
            "items": [{"code": "ORD-1"}],
        }
        mock_get.return_value.raise_for_status = lambda: None
        provider = LicenseProvider()
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 2, tzinfo=timezone.utc)
        missing = provider.validate(
            {"base_url": "https://auth.example.com", "username": "u", "password": "p"},
            start,
            end,
            user_id=1,
            platform="license",
            source_unique_ids=["ORD-1", "ORD-2"],
        )
        assert missing == ["ORD-2"]


@pytest.mark.unit
class TestLicenseProviderFetchAttachments:
    def test_fetch_attachments_returns_empty(self):
        provider = LicenseProvider()
        record = type("Rec", (), {"raw_data": {}})()
        assert provider.fetch_attachments({}, record) == []
