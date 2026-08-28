from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import (
    Count,
    DateTimeField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Sum,
)
from django.db.models.functions import (
    Coalesce,
    Trim,
    TruncMonth,
    TruncWeek,
    Upper,
)
from django.utils import timezone

from quotation.models import Quotation, QuotationVersion, QuoteStatus


OPEN_STATUSES = (
    QuoteStatus.GENERATED,
    QuoteStatus.UPLOADED,
    QuoteStatus.SENT,
)
CHART_STATUSES = tuple(
    value
    for value in QuoteStatus.values
    if value != QuoteStatus.CANCELLED
)
DEFAULT_DASHBOARD_CURRENCY = "USD"
MONTH_PERIOD_COUNT = 6
WEEK_PERIOD_COUNT = 8
BREAKDOWN_MIN_SHARE = Decimal("0.02")
BREAKDOWN_MAX_ITEMS = 8
CURRENCY_ALIASES = {
    "CNY": ("CNY", "RMB", "¥", "￥"),
    "EUR": ("EUR", "EURO", "EUROS", "€"),
    "GBP": ("GBP", "£"),
    "HKD": ("HKD", "HK$"),
    "MYR": ("MYR", "RM"),
}
_CURRENCY_CANONICAL = {
    alias: code
    for code, aliases in CURRENCY_ALIASES.items()
    for alias in aliases
}


def _money(value: Decimal | None) -> str:
    return f"{value or Decimal('0'):.2f}"


def _normalize_currency(currency: str) -> str:
    code = (currency or "").strip().upper()
    return _CURRENCY_CANONICAL.get(code, code)


def _currency_values(currency: str) -> tuple[str, ...]:
    return CURRENCY_ALIASES.get(currency, (currency,))


def _filter_by_currency(
    queryset: QuerySet[Quotation],
    currency: str,
) -> QuerySet[Quotation]:
    """Keep rows whose currency matches the selected code or alias."""
    values = {
        value.upper()
        for value in _currency_values(_normalize_currency(currency))
    }
    return queryset.annotate(
        currency_code=Upper(Trim("currency"))
    ).filter(currency_code__in=values)


def _available_currencies(queryset: QuerySet[Quotation]) -> list[str]:
    currencies = (
        queryset.exclude(currency="")
        .order_by("currency")
        .values_list("currency", flat=True)
        .distinct()
    )
    return sorted({_normalize_currency(currency) for currency in currencies})


def _available_periods(
    queryset: QuerySet[Quotation],
    selected_period: str,
) -> list[str]:
    periods = {
        value.strftime("%Y-%m")
        for value in queryset.dates("quote_date", "month", order="DESC")
    }
    periods.add(selected_period)
    return sorted(periods, reverse=True)


def _with_first_accepted_at(
    queryset: QuerySet[Quotation],
) -> QuerySet[Quotation]:
    accepted_at = QuotationVersion.objects.filter(
        quotation_id=OuterRef("pk"),
        status=QuoteStatus.ACCEPTED,
    ).order_by("created_at")
    return queryset.annotate(
        first_accepted_at=Subquery(
            accepted_at.values("created_at")[:1],
            output_field=DateTimeField(),
        ),
        won_at=Coalesce(
            "first_accepted_at",
            "updated_at",
            "created_at",
            output_field=DateTimeField(),
        ),
    )


def _month_start(value: datetime) -> datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _next_month(value: datetime) -> datetime:
    if value.month == 12:
        return value.replace(year=value.year + 1, month=1)
    return value.replace(month=value.month + 1)


def _shift_month(value: datetime, offset: int) -> datetime:
    month_index = value.year * 12 + value.month - 1 + offset
    return value.replace(
        year=month_index // 12,
        month=month_index % 12 + 1,
    )


def _dashboard_range(
    date_from: str = "",
    date_to: str = "",
) -> tuple[datetime, datetime]:
    """Return the selected inclusive month range as datetime bounds."""
    local_now = timezone.localtime()
    start = _month_start(local_now)
    if date_from:
        year, month = (int(part) for part in date_from.split("-"))
        start = start.replace(year=year, month=month)
    end_month = date_to or date_from
    if not end_month:
        end = _next_month(start)
    else:
        year, month = (int(part) for part in end_month.split("-"))
        end = _next_month(start.replace(year=year, month=month))
    return start, end


def _month_starts(start: datetime, end: datetime) -> list[datetime]:
    """Build every month start in the selected range."""
    values = []
    current = start
    while current < end:
        values.append(current)
        current = _next_month(current)
    return values


def _week_start(value: datetime) -> datetime:
    midnight = value.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=midnight.weekday())


def build_dashboard_summary(
    queryset: QuerySet[Quotation],
    currency: str = DEFAULT_DASHBOARD_CURRENCY,
    period: str = "",
    date_from: str = "",
    date_to: str = "",
) -> dict[str, object]:
    """Build lightweight KPI aggregates for the quotation dashboard."""
    currency = _normalize_currency(currency)
    currency_values = _currency_values(currency)
    currency_queryset = _filter_by_currency(queryset, currency)
    local_now = timezone.localtime()
    if period and not date_from:
        date_from = period
        date_to = period
    month_start, month_end = _dashboard_range(date_from, date_to)
    range_months = max(
        (month_end.year - month_start.year) * 12
        + month_end.month - month_start.month,
        1,
    )
    previous_month_start = _shift_month(month_start, -range_months)
    previous_month_end = _shift_month(previous_month_start, range_months)
    month_filter = Q(
        quote_date__gte=month_start.date(),
        quote_date__lt=month_end.date(),
    )
    previous_month_filter = Q(
        quote_date__gte=previous_month_start.date(),
        quote_date__lt=previous_month_end.date(),
    )
    counts = currency_queryset.aggregate(
        accepted_count=Count(
            "pk",
            filter=Q(status=QuoteStatus.ACCEPTED),
        ),
        open_count=Count(
            "pk",
            filter=Q(status__in=OPEN_STATUSES),
        ),
        draft_count=Count(
            "pk",
            filter=Q(status=QuoteStatus.DRAFT),
        ),
        month_quote_count=Count("pk", filter=month_filter),
        previous_month_quote_count=Count(
            "pk",
            filter=previous_month_filter,
        ),
        month_quote_amount=Sum(
            "grand_total",
            filter=month_filter,
        ),
        previous_month_quote_amount=Sum(
            "grand_total",
            filter=previous_month_filter,
        ),
    )
    won_amount = (
        _with_first_accepted_at(
            currency_queryset.filter(
                currency__in=currency_values,
                status=QuoteStatus.ACCEPTED,
            )
        )
        .filter(won_at__gte=month_start, won_at__lt=month_end)
        .aggregate(total=Sum("grand_total"))["total"]
    )
    accepted_count = counts["accepted_count"]
    open_count = counts["open_count"]
    rate_denominator = accepted_count + open_count
    success_rate = (
        round(accepted_count * 100 / rate_denominator)
        if rate_denominator
        else 0
    )
    return {
        "currency": currency,
        "available_currencies": _available_currencies(queryset),
        "available_periods": _available_periods(
            queryset,
            month_start.strftime("%Y-%m"),
        ),
        "current_period": month_start.strftime("%Y-%m"),
        "previous_period": previous_month_start.strftime("%Y-%m"),
        "month_quote_count": counts["month_quote_count"],
        "previous_month_quote_count": counts[
            "previous_month_quote_count"
        ],
        "month_quote_amount": _money(counts["month_quote_amount"]),
        "previous_month_quote_amount": _money(
            counts["previous_month_quote_amount"]
        ),
        "month_won_amount": _money(won_amount),
        "success_rate": success_rate,
        "success_rate_numerator": accepted_count,
        "success_rate_denominator": rate_denominator,
        "follow_up_count": open_count,
        "active_count": open_count,
        "draft_count": counts["draft_count"],
        "generated_at": local_now.isoformat(),
    }


def _period_amounts(
    queryset: QuerySet[Quotation],
    field_name: str,
    truncation,
    start: datetime,
    end: datetime,
) -> dict[datetime, Decimal]:
    rows = (
        queryset.filter(
            **{
                f"{field_name}__gte": start,
                f"{field_name}__lt": end,
            }
        )
        .annotate(period=truncation(field_name))
        .values("period")
        .annotate(amount=Sum("grand_total"))
        .order_by("period")
    )
    return {row["period"]: row["amount"] for row in rows}


def _trend_rows(
    queryset: QuerySet[Quotation],
    starts: list[datetime],
    truncation,
    period_format,
) -> list[dict[str, str]]:
    end = (
        _next_month(starts[-1])
        if truncation is TruncMonth
        else starts[-1] + timedelta(days=7)
    )
    created = _period_amounts(
        queryset.filter(status__in=CHART_STATUSES),
        "created_at",
        truncation,
        starts[0],
        end,
    )
    won = _period_amounts(
        _with_first_accepted_at(
            queryset.filter(status=QuoteStatus.ACCEPTED)
        ),
        "won_at",
        truncation,
        starts[0],
        end,
    )
    return [
        {
            "period": period_format(start),
            "created_amount": _money(created.get(start)),
            "won_amount": _money(won.get(start)),
        }
        for start in starts
    ]


def _quotation_trend_rows(
    queryset: QuerySet[Quotation],
    starts: list[datetime],
    truncation,
    period_format,
) -> list[dict[str, object]]:
    """Aggregate quotation amount and count by business quote date."""
    end = (
        _next_month(starts[-1])
        if truncation is TruncMonth
        else starts[-1] + timedelta(days=7)
    )
    rows = (
        queryset.filter(
            quote_date__gte=starts[0].date(),
            quote_date__lt=end.date(),
        )
        .annotate(period=truncation("quote_date"))
        .values("period")
        .annotate(
            quote_amount=Sum("grand_total"),
            quote_count=Count("pk"),
        )
        .order_by("period")
    )
    aggregates: dict[date, dict[str, object]] = {
        row["period"]: row for row in rows
    }
    return [
        {
            "period": period_format(start),
            "quote_amount": _money(
                aggregates.get(start.date(), {}).get("quote_amount")
            ),
            "quote_count": aggregates.get(start.date(), {}).get(
                "quote_count",
                0,
            ),
        }
        for start in starts
    ]


def _merge_trend_rows(
    legacy_rows: list[dict[str, str]],
    quotation_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Keep legacy trend fields while adding quotation-only metrics."""
    return [
        {**legacy, **quotation}
        for legacy, quotation in zip(
            legacy_rows,
            quotation_rows,
            strict=True,
        )
    ]


def _breakdown_quote_no(row: dict, display_counts: dict[str, int]) -> str:
    display = (
        row["source_quote_no"]
        or row["quote_no"]
        or row["draft_quote_no"]
        or ""
    )
    if display_counts.get(display, 0) > 1:
        return row["quote_no"] or row["draft_quote_no"] or ""
    return display


def build_dashboard_analytics(
    queryset: QuerySet[Quotation],
    currency: str = DEFAULT_DASHBOARD_CURRENCY,
    date_from: str = "",
    date_to: str = "",
) -> dict[str, object]:
    """Build bounded chart aggregates without serializing quotation rows."""
    currency = _normalize_currency(currency)
    local_now = timezone.localtime()
    if date_from or date_to:
        range_start, range_end = _dashboard_range(date_from, date_to)
    else:
        range_end = _month_start(local_now)
        range_start = _shift_month(range_end, -(MONTH_PERIOD_COUNT - 1))
        range_end = _next_month(range_end)
    currency_queryset = _filter_by_currency(queryset, currency)
    breakdown_queryset = currency_queryset.filter(
        status__in=CHART_STATUSES,
        grand_total__gt=0,
        quote_date__gte=range_start.date(),
        quote_date__lt=range_end.date(),
    )
    breakdown_totals = breakdown_queryset.aggregate(
        amount=Sum("grand_total"),
        count=Count("pk"),
    )
    total_amount = breakdown_totals["amount"] or Decimal("0")
    minimum_amount = total_amount * BREAKDOWN_MIN_SHARE
    breakdown_rows = list(
        breakdown_queryset.filter(grand_total__gte=minimum_amount)
        .order_by("-grand_total", "pk")
        .values(
            "id",
            "quote_no",
            "draft_quote_no",
            "source_quote_no",
            "currency",
            "grand_total",
            "status",
        )[:BREAKDOWN_MAX_ITEMS]
    )
    displayed_amount = sum(
        (row["grand_total"] for row in breakdown_rows),
        Decimal("0"),
    )
    display_counts: dict[str, int] = {}
    for row in breakdown_rows:
        display = (
            row["source_quote_no"]
            or row["quote_no"]
            or row["draft_quote_no"]
            or ""
        )
        display_counts[display] = display_counts.get(display, 0) + 1
    breakdown = [
        {
            "quotation_id": row["id"],
            "quote_no": _breakdown_quote_no(row, display_counts),
            "amount": _money(row["grand_total"]),
            "currency": _normalize_currency(row["currency"]),
            "status": row["status"],
        }
        for row in breakdown_rows
    ]
    month_starts = _month_starts(range_start, range_end)
    week_end = _week_start(range_end - timedelta(microseconds=1))
    week_starts = [
        week_end - timedelta(weeks=offset)
        for offset in range(WEEK_PERIOD_COUNT - 1, -1, -1)
    ]
    return {
        "currency": currency,
        "available_currencies": _available_currencies(queryset),
        "amount_breakdown": breakdown,
        "breakdown_total_amount": _money(total_amount),
        "breakdown_omitted_count": max(
            breakdown_totals["count"] - len(breakdown),
            0,
        ),
        "breakdown_omitted_amount": _money(total_amount - displayed_amount),
        "trends": {
            "monthly": _merge_trend_rows(
                _trend_rows(
                    currency_queryset,
                    month_starts,
                    TruncMonth,
                    lambda value: value.strftime("%Y-%m"),
                ),
                _quotation_trend_rows(
                    currency_queryset,
                    month_starts,
                    TruncMonth,
                    lambda value: value.strftime("%Y-%m"),
                ),
            ),
            "weekly": _merge_trend_rows(
                _trend_rows(
                    currency_queryset,
                    week_starts,
                    TruncWeek,
                    lambda value: value.date().isoformat(),
                ),
                _quotation_trend_rows(
                    currency_queryset,
                    week_starts,
                    TruncWeek,
                    lambda value: value.date().isoformat(),
                ),
            ),
        },
        "generated_at": local_now.isoformat(),
    }


def build_dashboard_recent(
    queryset: QuerySet[Quotation],
    limit: int,
) -> dict[str, object]:
    """Return a bounded projection for the recent quotations card."""
    rows = queryset.order_by("-updated_at", "-id").values(
        "id",
        "quote_no",
        "draft_quote_no",
        "source_quote_no",
        "project_name",
        "client_company",
        "issuer_contact_name",
        "created_at",
        "updated_at",
        "currency",
        "grand_total",
        "status",
    )[:limit]
    return {
        "items": [
            {
                "id": row["id"],
                "quote_no": (
                    row["source_quote_no"]
                    or row["quote_no"]
                    or row["draft_quote_no"]
                    or ""
                ),
                "project_name": row["project_name"],
                "client_company": row["client_company"],
                "salesperson": row["issuer_contact_name"],
                "created_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat(),
                "currency": row["currency"],
                "grand_total": _money(row["grand_total"]),
                "status": row["status"],
            }
            for row in rows
        ]
    }
