from __future__ import annotations

import logging
from collections import defaultdict
from threading import Lock

from django.core.cache import cache

logger = logging.getLogger(__name__)
_lock = Lock()
_request_totals: dict[tuple[str, str, str], int] = defaultdict(int)
_duration_totals: dict[tuple[str, str], float] = defaultdict(float)
_duration_counts: dict[tuple[str, str], int] = defaultdict(int)
EXPORT_STAGES = ("archive", "render")
EXPORT_RESULTS = ("failure", "retry", "success")


def _export_metric_key(*parts: str) -> str:
    return "quotation:export:metrics:" + ":".join(parts)


def _increment_metric(key: str, value: int = 1) -> None:
    cache.add(key, 0, timeout=None)
    cache.incr(key, value)


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
            for (provider, operation, result), count in sorted(_request_totals.items())
        ]
        durations = [
            {
                "provider": provider,
                "operation": operation,
                "count": _duration_counts[(provider, operation)],
                "total_seconds": round(total, 6),
            }
            for (provider, operation), total in sorted(_duration_totals.items())
        ]
    return {"requests": requests, "durations": durations}


def record_export_operation(
    *,
    stage: str,
    result: str,
    duration_seconds: float,
) -> None:
    """Record cross-process export metrics in the shared cache."""
    if stage not in EXPORT_STAGES or result not in EXPORT_RESULTS:
        raise ValueError("unsupported quotation export metric label")
    duration_ms = max(round(duration_seconds * 1000), 0)
    try:
        _increment_metric(_export_metric_key("result", stage, result))
        _increment_metric(_export_metric_key("duration_count", stage))
        _increment_metric(
            _export_metric_key("duration_ms", stage),
            duration_ms,
        )
    except Exception:
        logger.exception("quotation_export_metric_record_failed")


def export_metrics_snapshot() -> dict:
    """Return shared render and archive stage metrics."""
    results: dict[str, dict[str, int]] = {}
    durations = {}
    try:
        for stage in EXPORT_STAGES:
            for result in EXPORT_RESULTS:
                count = int(
                    cache.get(
                        _export_metric_key("result", stage, result),
                        0,
                    )
                    or 0
                )
                if count:
                    results.setdefault(stage, {})[result] = count
            count = int(
                cache.get(
                    _export_metric_key("duration_count", stage),
                    0,
                )
                or 0
            )
            total_ms = int(
                cache.get(
                    _export_metric_key("duration_ms", stage),
                    0,
                )
                or 0
            )
            if count:
                durations[stage] = {
                    "count": count,
                    "total_seconds": round(total_ms / 1000, 6),
                }
    except Exception:
        logger.exception("quotation_export_metric_snapshot_failed")
    return {"results": results, "durations": durations}
