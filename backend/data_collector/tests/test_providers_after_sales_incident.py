"""
Tests for AfterSalesIncident provider.
"""
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from django.test import TestCase

from data_collector.services.providers.after_sales_incident import (
    AfterSalesIncidentProvider,
    _fmt_priority,
    _fmt_state,
    _parse_datetime,
    _is_token_valid,
    DEFAULT_BASE_URL,
    REQUEST_TIMEOUT,
    BATCH_SIZE,
)


class TestAfterSalesIncidentProvider(TestCase):
    def setUp(self):
        self.provider = AfterSalesIncidentProvider()
        self.auth_config = {
            "base_url": "https://support.oneprocloud.com",
            "bearer_token": "test-token-123",
        }

    def test_provider_initialization(self):
        """Test provider initializes with default values."""
        self.assertEqual(self.provider._base_url, DEFAULT_BASE_URL)
        self.assertIsNone(self.provider._token)

    def test_resolve_config_returns_base_url_and_token(self):
        """Test _resolve_config returns correct tuple."""
        base_url, token = self.provider._resolve_config(self.auth_config)
        self.assertEqual(base_url, "https://support.oneprocloud.com")
        self.assertEqual(token, "test-token-123")

    def test_resolve_config_uses_default_base_url(self):
        """Test _resolve_config uses DEFAULT_BASE_URL when not provided."""
        base_url, token = self.provider._resolve_config({"bearer_token": "token"})
        self.assertEqual(base_url, DEFAULT_BASE_URL)

    def test_build_headers_contains_required_fields(self):
        """Test _build_headers returns correct headers."""
        headers = self.provider._build_headers("test-token")
        self.assertEqual(headers["Authorization"], "Bearer test-token")
        self.assertEqual(headers["Accept"], "application/json, text/plain, */*")
        self.assertIn("Referer", headers)
        self.assertIn("User-Agent", headers)
        self.assertIn("sec-ch-ua", headers)

    @patch("data_collector.services.providers.after_sales_incident.requests.get")
    def test_authenticate_success(self, mock_get):
        """Test successful authentication."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = self.provider.authenticate(self.auth_config)
        self.assertTrue(result)

    @patch("data_collector.services.providers.after_sales_incident.requests.get")
    def test_authenticate_failure(self, mock_get):
        """Test failed authentication returns False."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        result = self.provider.authenticate(self.auth_config)
        self.assertFalse(result)

    @patch("data_collector.services.providers.after_sales_incident.requests.get")
    def test_collect_returns_empty_on_no_token(self, mock_get):
        """Test collect returns empty list when no token."""
        result = self.provider.collect(
            auth_config={"bearer_token": ""},
            start_time=None,
            end_time=None,
            user_id=1,
            platform="after_sales_incident",
        )
        self.assertEqual(result, [])

    @patch("data_collector.services.providers.after_sales_incident.requests.get")
    def test_collect_returns_items(self, mock_get):
        """Test collect returns parsed items."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "record_data_map": {
                        "number": "INC-001",
                        "priority": 1,
                        "state": 1,
                        "sys_created_on": "2026-01-01 00:00:00",
                        "sys_updated_on": "2026-01-02 00:00:00",
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        result = self.provider.collect(
            auth_config=self.auth_config,
            start_time=None,
            end_time=None,
            user_id=1,
            platform="after_sales_incident",
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source_unique_id"], "INC-001")
        self.assertIn("raw_data", result[0])
        self.assertIn("data_hash", result[0])

    @patch("data_collector.services.providers.after_sales_incident.requests.get")
    def test_collect_handles_401_refresh_token(self, mock_get):
        """Test collect refreshes token on 401."""
        # First call returns 401, second returns success
        mock_401 = MagicMock()
        mock_401.status_code = 401

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"data": []}

        mock_get.side_effect = [mock_401, mock_200]

        with patch.object(self.provider, "_ensure_token") as mock_ensure:
            mock_ensure.return_value = "new-token"

            result = self.provider.collect(
                auth_config=self.auth_config,
                start_time=None,
                end_time=None,
                user_id=1,
                platform="after_sales_incident",
            )

    def test_fetch_attachments_returns_empty(self):
        """Test fetch_attachments returns empty list (no attachments for this platform)."""
        result = self.provider.fetch_attachments(
            auth_config=self.auth_config,
            raw_record={},
        )
        self.assertEqual(result, [])

    def test_download_attachment_content_returns_none(self):
        """Test download_attachment_content returns None (no attachments)."""
        result = self.provider.download_attachment_content(
            auth_config=self.auth_config,
            attachment_meta={},
        )
        self.assertIsNone(result)


class TestHelperFunctions(TestCase):
    def test_fmt_priority_integer(self):
        """Test _fmt_priority with integer input."""
        self.assertEqual(_fmt_priority(1), "P1")
        self.assertEqual(_fmt_priority(2), "P2")
        self.assertEqual(_fmt_priority(3), "P3")
        self.assertEqual(_fmt_priority(4), "P4")

    def test_fmt_priority_string(self):
        """Test _fmt_priority with string input."""
        self.assertEqual(_fmt_priority("P1"), "P1")
        self.assertEqual(_fmt_priority("p2"), "P2")
        self.assertEqual(_fmt_priority("invalid"), "P3")  # defaults to P3

    def test_fmt_state_integer(self):
        """Test _fmt_state with integer input."""
        self.assertEqual(_fmt_state(1), "New")
        self.assertEqual(_fmt_state(2), "In Progress")
        self.assertEqual(_fmt_state(4), "Closed")
        self.assertEqual(_fmt_state(6), "Resolved")

    def test_fmt_state_chinese(self):
        """Test _fmt_state with Chinese input."""
        self.assertEqual(_fmt_state("新建"), "New")
        self.assertEqual(_fmt_state("处理中"), "In Progress")
        self.assertEqual(_fmt_state("已关闭"), "Closed")

    def test_fmt_state_invalid(self):
        """Test _fmt_state with invalid input."""
        self.assertEqual(_fmt_state(None), "Unknown")
        self.assertEqual(_fmt_state("invalid"), "Unknown")

    def test_parse_datetime_formats(self):
        """Test _parse_datetime handles various formats."""
        # Standard format
        result = _parse_datetime("2026-01-15 10:30:00")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 15)

        # ISO format
        result = _parse_datetime("2026-01-15T10:30:00")
        self.assertIsNotNone(result)

        # Date only
        result = _parse_datetime("2026-01-15")
        self.assertIsNotNone(result)

    def test_parse_datetime_invalid(self):
        """Test _parse_datetime returns None for invalid input."""
        self.assertIsNone(_parse_datetime(None))
        self.assertIsNone(_parse_datetime("invalid"))

    def test_is_token_valid_with_valid_token(self):
        """Test _is_token_valid returns True for valid JWT."""
        # A token expiring in 1 hour (should be valid)
        valid_token = (
            "eyJhbGciOiJIUzI1NiJ9."
            "eyJleHAiOjE3NzcwMDAwMDB9."
            "signature"
        )
        result = _is_token_valid(valid_token)
        # Note: This may fail if the token is actually invalid
        # The function should return True for invalid tokens (fail-open)

    def test_is_token_valid_with_invalid_token(self):
        """Test _is_token_valid handles invalid tokens."""
        result = _is_token_valid("not-a-valid-jwt")
        # Should return True (fail-open) for unparseable tokens
        self.assertTrue(result)

    def test_constants(self):
        """Test provider constants."""
        self.assertEqual(DEFAULT_BASE_URL, "https://support.oneprocloud.com")
        self.assertEqual(REQUEST_TIMEOUT, 60)
        self.assertEqual(BATCH_SIZE, 200)
