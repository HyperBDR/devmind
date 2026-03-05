"""
Shared utilities for data_collector (time conversion, etc.).
"""
from datetime import datetime, timezone
from typing import Any


def to_unix_ms(dt: Any) -> int:
    """
    Convert datetime / ISO8601 string / timestamp to unix ms timestamp.
    Used by Feishu provider for instance_start_time_from/to.
    """
    if isinstance(dt, (int, float)):
        return int(dt * 1000)
    if isinstance(dt, str):
        try:
            parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            dt = parsed
        except Exception:
            return 0
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    return 0


def from_unix_ms(value: Any) -> datetime | None:
    """
    Convert millisecond timestamp (str/int) to timezone-aware datetime (UTC).
    Returns None if value is falsy or cannot be parsed.
    """
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
        ms = int(value)
    except (TypeError, ValueError):
        return None
    try:
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def to_utc_datetime_str(dt: Any) -> str:
    """
    Convert datetime to UTC string for filter_start_time/filter_end_time.
    Format: "YYYY-MM-DD HH:MM:SS" (UTC).
    """
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        utc_dt = dt.astimezone(timezone.utc)
        return utc_dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt)
