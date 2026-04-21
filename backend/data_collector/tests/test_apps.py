"""
Unit tests for data_collector app config.
"""
import pytest

from data_collector.apps import DataCollectorConfig


@pytest.mark.unit
class TestDataCollectorConfig:
    def test_app_name(self):
        assert DataCollectorConfig.name == "data_collector"

    def test_verbose_name(self):
        assert DataCollectorConfig.verbose_name == "Data Collector"

    def test_default_auto_field(self):
        assert DataCollectorConfig.default_auto_field == "django.db.models.BigAutoField"
