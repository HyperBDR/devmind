"""
LLM Usage Statistics utilities for admin cost analysis.
All logic stays in llm_tracker for reuse in other projects.
"""
from datetime import datetime
from typing import Any, Optional

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate, TruncHour, TruncMonth
from django.utils.dateparse import parse_datetime

from llm_tracker.models import LLMUsage


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = parse_datetime(value)
        if dt:
            return dt
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _parse_end_date(value: Optional[str]) -> Optional[datetime]:
    """
    Parse end_date; if value is date-only (no time part), return end of that
    day so that the whole day is included in range filters.
    """
    dt = _parse_date(value)
    if dt is None:
        return None
    value = (value or "").strip()
    if "T" not in value and " " not in value and len(value) <= 10:
        return dt.replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
    return dt


def get_summary_stats(start_date=None, end_date=None, user_id=None):
    qs = LLMUsage.objects.all()
    if user_id:
        qs = qs.filter(user_id=user_id)
    if start_date:
        qs = qs.filter(created_at__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__lte=end_date)
    agg = qs.aggregate(
        total_calls=Count("id"),
        total_prompt_tokens=Sum("prompt_tokens"),
        total_completion_tokens=Sum("completion_tokens"),
        total_tokens=Sum("total_tokens"),
        total_cached_tokens=Sum("cached_tokens"),
        total_reasoning_tokens=Sum("reasoning_tokens"),
        successful_calls=Count("id", filter=Q(success=True)),
        failed_calls=Count("id", filter=Q(success=False)),
    )
    return {
        "total_prompt_tokens": agg["total_prompt_tokens"] or 0,
        "total_completion_tokens": agg["total_completion_tokens"] or 0,
        "total_tokens": agg["total_tokens"] or 0,
        "total_cached_tokens": agg["total_cached_tokens"] or 0,
        "total_reasoning_tokens": agg["total_reasoning_tokens"] or 0,
        "total_calls": agg["total_calls"] or 0,
        "successful_calls": agg["successful_calls"] or 0,
        "failed_calls": agg["failed_calls"] or 0,
    }


def get_stats_by_model(start_date=None, end_date=None, user_id=None):
    qs = LLMUsage.objects.values("model").annotate(
        total_calls=Count("id"),
        total_prompt_tokens=Sum("prompt_tokens"),
        total_completion_tokens=Sum("completion_tokens"),
        total_tokens=Sum("total_tokens"),
        total_cached_tokens=Sum("cached_tokens"),
        total_reasoning_tokens=Sum("reasoning_tokens"),
    ).order_by("-total_tokens")
    if user_id:
        qs = qs.filter(user_id=user_id)
    if start_date:
        qs = qs.filter(created_at__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__lte=end_date)
    return list(qs)


def get_time_series_stats(
    granularity: str,
    start_date=None,
    end_date=None,
    user_id=None,
):
    """
    Returns time-series token usage points for charting.

    Supported granularity:
    - day: points bucketed by hour
    - month: points bucketed by day
    - year: points bucketed by month
    """
    granularity = (granularity or "").strip().lower()
    if granularity == "day":
        trunc = TruncHour("created_at")
    elif granularity == "month":
        trunc = TruncDate("created_at")
    elif granularity == "year":
        trunc = TruncMonth("created_at")
    else:
        raise ValueError(
            "Unsupported granularity. Use one of: day, month, year."
        )

    qs = (
        LLMUsage.objects.annotate(bucket=trunc)
        .values("bucket")
        .annotate(
            total_calls=Count("id"),
            total_prompt_tokens=Sum("prompt_tokens"),
            total_completion_tokens=Sum("completion_tokens"),
            total_tokens=Sum("total_tokens"),
            total_cached_tokens=Sum("cached_tokens"),
            total_reasoning_tokens=Sum("reasoning_tokens"),
        )
        .order_by("bucket")
    )
    if user_id:
        qs = qs.filter(user_id=user_id)
    if start_date:
        qs = qs.filter(created_at__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__lte=end_date)

    def _row(i):
        bucket = i["bucket"]
        if bucket is None:
            bucket_str = None
        else:
            bucket_str = bucket.isoformat()
        return {
            "bucket": bucket_str,
            "total_calls": i["total_calls"],
            "total_prompt_tokens": i["total_prompt_tokens"] or 0,
            "total_completion_tokens": i["total_completion_tokens"] or 0,
            "total_tokens": i["total_tokens"] or 0,
            "total_cached_tokens": i["total_cached_tokens"] or 0,
            "total_reasoning_tokens": i["total_reasoning_tokens"] or 0,
        }

    return [_row(r) for r in qs]


def get_token_stats_from_query(params: Any) -> dict:
    """
    Build token stats dict from query params (e.g. request.query_params).
    Raises ValueError for unsupported granularity.
    All parsing and aggregation logic lives in llm_tracker for reuse.
    """
    start_date = _parse_date(params.get("start_date"))
    end_date = _parse_end_date(params.get("end_date"))
    user_id = params.get("user_id") or None
    if user_id is not None and str(user_id).strip() == "":
        user_id = None
    granularity = params.get("granularity")

    summary = get_summary_stats(
        start_date=start_date, end_date=end_date, user_id=user_id
    )
    by_model = get_stats_by_model(
        start_date=start_date, end_date=end_date, user_id=user_id
    )
    series = None
    if granularity:
        series_items = get_time_series_stats(
            granularity=granularity,
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
        )
        series = {
            "granularity": (granularity or "").strip().lower(),
            "items": series_items,
        }
    return {
        "summary": summary,
        "by_model": by_model,
        "series": series,
    }
