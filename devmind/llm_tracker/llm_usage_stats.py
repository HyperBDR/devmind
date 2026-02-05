"""
LLM Usage Statistics utilities for admin cost analysis.
"""
from datetime import datetime
from typing import Optional

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
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


def get_summary_stats(start_date=None, end_date=None):
    qs = LLMUsage.objects.all()
    if start_date:
        qs = qs.filter(created_at__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__lte=end_date)
    agg = qs.aggregate(
        total_calls=Count("id"),
        total_prompt_tokens=Sum("prompt_tokens"),
        total_completion_tokens=Sum("completion_tokens"),
        total_tokens=Sum("total_tokens"),
        successful_calls=Count("id", filter=Q(success=True)),
        failed_calls=Count("id", filter=Q(success=False)),
    )
    return {
        "total_prompt_tokens": agg["total_prompt_tokens"] or 0,
        "total_completion_tokens": agg["total_completion_tokens"] or 0,
        "total_tokens": agg["total_tokens"] or 0,
        "total_calls": agg["total_calls"] or 0,
        "successful_calls": agg["successful_calls"] or 0,
        "failed_calls": agg["failed_calls"] or 0,
    }


def get_stats_by_model(start_date=None, end_date=None):
    qs = LLMUsage.objects.values("model").annotate(
        total_calls=Count("id"),
        total_prompt_tokens=Sum("prompt_tokens"),
        total_completion_tokens=Sum("completion_tokens"),
        total_tokens=Sum("total_tokens"),
    ).order_by("-total_tokens")
    if start_date:
        qs = qs.filter(created_at__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__lte=end_date)
    return list(qs)


def get_stats_by_day(start_date=None, end_date=None):
    qs = (
        LLMUsage.objects.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            total_calls=Count("id"),
            total_tokens=Sum("total_tokens"),
        )
        .order_by("day")
    )
    if start_date:
        qs = qs.filter(created_at__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__lte=end_date)

    def _row(i):
        return {
            "date": str(i["day"]) if i["day"] else None,
            "total_calls": i["total_calls"],
            "total_tokens": i["total_tokens"] or 0,
        }

    return [_row(r) for r in qs]
