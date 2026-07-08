import os
import time
from decimal import Decimal

from data_ops.services.feishu.sync import _parse_bool, _parse_date


def test_parse_bool_handles_negative_text_values():
    for value in ["否", "无", "false", "0", "", None]:
        assert _parse_bool(value) is False


def test_parse_bool_handles_positive_values():
    for value in ["是", "有", "true", "1", 1, Decimal("1")]:
        assert _parse_bool(value) is True


def test_parse_date_uses_feishu_source_timezone_for_timestamps(monkeypatch):
    old_tz = os.environ.get("TZ")
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()

    try:
        assert _parse_date(1704038400000).isoformat() == "2024-01-01"
    finally:
        if old_tz is None:
            monkeypatch.delenv("TZ", raising=False)
        else:
            monkeypatch.setenv("TZ", old_tz)
        time.tzset()
