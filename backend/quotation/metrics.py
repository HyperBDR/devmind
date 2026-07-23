from __future__ import annotations

from collections import defaultdict
from threading import Lock


_lock = Lock()
_request_totals: dict[tuple[str, str, str], int] = defaultdict(int)
_duration_totals: dict[tuple[str, str], float] = defaultdict(float)
_duration_counts: dict[tuple[str, str], int] = defaultdict(int)


def record_storage_operation(
    *,
    provider: str,
    operation: str,
    result: str,
    duration_seconds: float,
) -> None:
    """Record low-cardinality RED values without resource identifiers."""
    request_key = (provider, operation, result)
    duration_key = (provider, operation)
    with _lock:
        _request_totals[request_key] += 1
        _duration_totals[duration_key] += duration_seconds
        _duration_counts[duration_key] += 1


def storage_metrics_snapshot() -> dict:
    """Return a serializable process-local RED metrics snapshot."""
    with _lock:
        requests = [
            {
                "provider": provider,
                "operation": operation,
                "result": result,
                "count": count,
            }
            for (provider, operation, result), count in sorted(
                _request_totals.items()
            )
        ]
        durations = [
            {
                "provider": provider,
                "operation": operation,
                "count": _duration_counts[(provider, operation)],
                "total_seconds": round(total, 6),
            }
            for (provider, operation), total in sorted(
                _duration_totals.items()
            )
        ]
    return {"requests": requests, "durations": durations}
