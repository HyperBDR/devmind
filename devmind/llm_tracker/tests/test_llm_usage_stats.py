"""
Tests for llm_usage_stats: _parse_date, get_summary_stats, by_model, series.

Uses real DB and LLMUsage records for aggregation tests.
"""
import pytest
from django.utils import timezone as django_tz

from llm_tracker.llm_usage_stats import (
    _parse_date,
    _parse_end_date,
    get_stats_by_model,
    get_summary_stats,
    get_time_series_stats,
    get_token_stats_from_query,
)
from llm_tracker.models import LLMUsage


@pytest.mark.unit
class TestParseDate:
    """
    _parse_date returns datetime or None.
    """

    def test_returns_none_for_none(self):
        assert _parse_date(None) is None

    def test_returns_none_for_empty_string(self):
        assert _parse_date("") is None

    def test_parses_iso_datetime_string(self):
        s = "2025-02-01T12:00:00+00:00"
        out = _parse_date(s)
        assert out is not None
        assert out.year == 2025
        assert out.month == 2
        assert out.day == 1

    def test_parses_iso_with_z_suffix(self):
        s = "2025-02-02T00:00:00Z"
        out = _parse_date(s)
        assert out is not None
        assert out.tzinfo is not None

    def test_returns_none_for_invalid_string(self):
        assert _parse_date("not-a-date") is None

    def test_returns_none_for_wrong_type(self):
        assert _parse_date(123) is None


@pytest.mark.unit
class TestParseEndDate:
    """
    _parse_end_date returns end of day for date-only strings so full day
    is included.
    """

    def test_returns_none_for_none(self):
        assert _parse_end_date(None) is None

    def test_date_only_returns_end_of_day(self):
        out = _parse_end_date("2025-02-01")
        assert out is not None
        assert out.year == 2025
        assert out.month == 2
        assert out.day == 1
        assert out.hour == 23
        assert out.minute == 59
        assert out.second == 59
        assert out.microsecond == 999999

    def test_datetime_string_unchanged(self):
        s = "2025-02-01T14:30:00+00:00"
        out = _parse_end_date(s)
        assert out is not None
        assert out.hour == 14
        assert out.minute == 30


@pytest.mark.unit
@pytest.mark.django_db
class TestGetSummaryStats:
    """
    get_summary_stats aggregates LLMUsage in date range.
    """

    def test_returns_zeros_when_no_records(self):
        out = get_summary_stats()
        assert out["total_calls"] == 0
        assert out["total_tokens"] == 0
        assert out["successful_calls"] == 0
        assert out["failed_calls"] == 0

    def test_aggregates_single_record(self):
        LLMUsage.objects.create(
            model="gpt-4",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            success=True,
        )
        out = get_summary_stats()
        assert out["total_calls"] == 1
        assert out["total_prompt_tokens"] == 10
        assert out["total_completion_tokens"] == 20
        assert out["total_tokens"] == 30
        assert out["successful_calls"] == 1
        assert out["failed_calls"] == 0

    def test_filters_by_start_and_end_date(self):
        base = django_tz.now()
        LLMUsage.objects.create(
            model="m1",
            total_tokens=1,
            created_at=base,
        )
        start = (base - django_tz.timedelta(days=2)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = (base + django_tz.timedelta(days=1)).replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
        out = get_summary_stats(start_date=start, end_date=end)
        assert out["total_calls"] == 1

    def test_counts_success_and_failed(self):
        LLMUsage.objects.create(model="m1", total_tokens=1, success=True)
        LLMUsage.objects.create(model="m2", total_tokens=1, success=False)
        out = get_summary_stats()
        assert out["successful_calls"] == 1
        assert out["failed_calls"] == 1
        assert out["total_calls"] == 2


@pytest.mark.unit
@pytest.mark.django_db
class TestGetStatsByModel:
    """
    get_stats_by_model groups by model and orders by total_tokens.
    """

    def test_empty_list_when_no_records(self):
        assert get_stats_by_model() == []

    def test_one_row_per_model_with_totals(self):
        LLMUsage.objects.create(
            model="gpt-4",
            prompt_tokens=5,
            completion_tokens=10,
            total_tokens=15,
        )
        LLMUsage.objects.create(
            model="gpt-4",
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
        )
        LLMUsage.objects.create(
            model="claude",
            prompt_tokens=2,
            completion_tokens=4,
            total_tokens=6,
        )
        rows = get_stats_by_model()
        assert len(rows) == 2
        by_model = {r["model"]: r for r in rows}
        assert by_model["gpt-4"]["total_calls"] == 2
        assert by_model["gpt-4"]["total_tokens"] == 18
        assert by_model["claude"]["total_tokens"] == 6
        assert rows[0]["model"] == "gpt-4"
        assert rows[0]["total_tokens"] >= rows[1]["total_tokens"]


@pytest.mark.unit
@pytest.mark.django_db
class TestGetTimeSeriesStats:
    """
    get_time_series_stats buckets by hour/day/month and applies filters.
    """

    def test_raises_for_unsupported_granularity(self):
        with pytest.raises(ValueError, match="Unsupported granularity"):
            get_time_series_stats(granularity="invalid")

    def test_day_granularity_returns_buckets(self):
        LLMUsage.objects.create(
            model="m1",
            total_tokens=10,
        )
        items = get_time_series_stats(granularity="day")
        assert isinstance(items, list)
        if items:
            row = items[0]
            assert "bucket" in row
            assert "total_calls" in row
            assert "total_tokens" in row

    def test_month_granularity_returns_buckets(self):
        LLMUsage.objects.create(model="m1", total_tokens=5)
        items = get_time_series_stats(granularity="month")
        assert isinstance(items, list)

    def test_year_granularity_returns_buckets(self):
        LLMUsage.objects.create(model="m1", total_tokens=5)
        items = get_time_series_stats(granularity="year")
        assert isinstance(items, list)

    def test_filters_by_user_and_dates(self, django_user_model):
        user = django_user_model.objects.create_user(
            username="u1", password="p", email="u1@example.com"
        )
        LLMUsage.objects.create(
            user=user,
            model="m1",
            total_tokens=1,
        )
        items = get_time_series_stats(
            granularity="day",
            user_id=user.id,
        )
        assert isinstance(items, list)


@pytest.mark.unit
@pytest.mark.django_db
class TestGetTokenStatsFromQuery:
    """
    get_token_stats_from_query builds summary, by_model, series from params.
    """

    def test_returns_summary_and_by_model_without_granularity(self):
        LLMUsage.objects.create(model="m1", total_tokens=10)
        out = get_token_stats_from_query({})
        assert "summary" in out
        assert out["summary"]["total_tokens"] == 10
        assert "by_model" in out
        assert out["series"] is None

    def test_parses_start_date_end_date_user_id(self, django_user_model):
        user = django_user_model.objects.create_user(
            username="u1", password="p", email="u1@example.com"
        )
        LLMUsage.objects.create(
            user=user,
            model="m1",
            total_tokens=1,
        )
        out = get_token_stats_from_query({
            "start_date": "2025-01-01T00:00:00+00:00",
            "end_date": "2025-12-31T23:59:59+00:00",
            "user_id": str(user.id),
        })
        assert "summary" in out
        assert "by_model" in out

    def test_includes_series_when_granularity_given(self):
        LLMUsage.objects.create(model="m1", total_tokens=1)
        out = get_token_stats_from_query({"granularity": "day"})
        assert out["series"] is not None
        assert out["series"]["granularity"] == "day"
        assert "items" in out["series"]

    def test_raises_for_unsupported_granularity_in_params(self):
        with pytest.raises(ValueError, match="Unsupported granularity"):
            get_token_stats_from_query({"granularity": "bad"})

