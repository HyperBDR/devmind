"""
Unit tests for data_collector conf (get_data_collector_root).
"""
import pytest

from data_collector.conf import DATA_COLLECTOR_ROOT, get_data_collector_root


@pytest.mark.unit
class TestConf:
    def test_get_data_collector_root_returns_root(self):
        root = get_data_collector_root()
        assert root == DATA_COLLECTOR_ROOT
        assert isinstance(root, str)
        assert len(root) > 0

    def test_data_collector_root_defined(self):
        assert DATA_COLLECTOR_ROOT is not None
        assert isinstance(DATA_COLLECTOR_ROOT, str)
