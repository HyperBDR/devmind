"""Tests for owner extraction from cloud provider instance tags."""

from unittest.mock import Mock

import pytest

from cloud_billing.clouds.aws_provider import AWSConfig, AWSCloud
from cloud_billing.clouds.tencent_provider import (
    TencentConfig,
    TencentCloud,
)


class TestAWSOwnerExtraction:
    """Tests for AWS _extract_owner_from_tags."""

    def _make_provider(self):
        config = AWSConfig(
            api_key="test-ak",
            api_secret="test-sk",
            region="us-east-1",
        )
        provider = AWSCloud(config)
        provider._ec2_client = Mock()
        return provider

    def test_extract_owner_created_by(self):
        """Should extract owner from 'created_by' tag."""
        provider = self._make_provider()
        tags = [
            {"Key": "created_by", "Value": "zhangsan"},
            {"Key": "Env", "Value": "prod"},
        ]
        assert provider._extract_owner_from_tags(tags) == "zhangsan"

    def test_extract_owner_owner_tag(self):
        """Should extract owner from 'Owner' tag."""
        provider = self._make_provider()
        tags = [
            {"Key": "Name", "Value": "web-server-01"},
            {"Key": "Owner", "Value": "lisi"},
        ]
        assert provider._extract_owner_from_tags(tags) == "lisi"

    def test_extract_owner_case_insensitive(self):
        """Should match tag keys case-insensitively."""
        provider = self._make_provider()
        tags = [{"Key": "CREATED_BY", "Value": "wangwu"}]
        assert provider._extract_owner_from_tags(tags) == "wangwu"

    def test_extract_owner_no_match(self):
        """Should return empty string when no owner tag found."""
        provider = self._make_provider()
        tags = [
            {"Key": "Name", "Value": "web-server"},
            {"Key": "Env", "Value": "prod"},
        ]
        assert provider._extract_owner_from_tags(tags) == ""

    def test_extract_owner_empty_tags(self):
        """Should return empty string for empty tags list."""
        provider = self._make_provider()
        assert provider._extract_owner_from_tags([]) == ""

    def test_extract_owner_none_tags(self):
        """Should return empty string for None tags."""
        provider = self._make_provider()
        assert provider._extract_owner_from_tags(None) == ""


class TestTencentOwnerExtraction:
    """Tests for Tencent _extract_owner_from_tags."""

    def _make_provider(self):
        config = TencentConfig(
            access_key_id="test-ak",
            access_key_secret="test-sk",
            app_id="12345",
            region="ap-guangzhou",
        )
        provider = TencentCloud(config)
        return provider

    def test_extract_owner_created_by(self):
        """Should extract owner from 'created_by' tag."""
        provider = self._make_provider()
        tags = [
            {"Key": "created_by", "Value": "zhangsan"},
            {"Key": "Env", "Value": "prod"},
        ]
        assert provider._extract_owner_from_tags(tags) == "zhangsan"

    def test_extract_owner_owner_tag(self):
        """Should extract owner from 'Owner' tag."""
        provider = self._make_provider()
        tags = [
            {"Key": "Name", "Value": "web-server"},
            {"Key": "Owner", "Value": "lisi"},
        ]
        assert provider._extract_owner_from_tags(tags) == "lisi"

    def test_extract_owner_creator_tag(self):
        """Should extract owner from 'creator' tag."""
        provider = self._make_provider()
        tags = [{"Key": "creator", "Value": "wangwu"}]
        assert provider._extract_owner_from_tags(tags) == "wangwu"

    def test_extract_owner_no_match(self):
        """Should return empty string when no owner tag found."""
        provider = self._make_provider()
        tags = [{"Key": "Env", "Value": "prod"}]
        assert provider._extract_owner_from_tags(tags) == ""

    def test_extract_owner_empty_tags(self):
        """Should return empty string for empty tags list."""
        provider = self._make_provider()
        assert provider._extract_owner_from_tags([]) == ""

    def test_extract_owner_none_tags(self):
        """Should return empty string for None tags."""
        provider = self._make_provider()
        assert provider._extract_owner_from_tags(None) == ""
