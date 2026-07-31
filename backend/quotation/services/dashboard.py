from __future__ import annotations

from datetime import datetime, timedelta
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
from django.db.models.functions import Coalesce, TruncMonth, TruncWeek
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


def _money(value: Decimal | None) -> str:
    return f"{value or Decimal('0'):.2f}"


def _available_currencies(queryset: QuerySet[Quotation]) -> list[str]:
    return list(
        queryset.exclude(currency="")
        .order_by("currency")
        .values_list("currency", flat=True)
        .distinct()
    )


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


def _week_start(value: datetime) -> datetime:
    midnight = value.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=midnight.weekday())


def build_dashboard_summary(
    queryset: QuerySet[Quotation],
    currency: str = DEFAULT_DASHBOARD_CURRENCY,
) -> dict[str, object]:
    """Build lightweight KPI aggregates for the quotation dashboard."""
    local_now = timezone.localtime()
    month_start = _month_start(local_now)
    month_end = _next_month(month_start)
    counts = queryset.aggregate(
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
    )
    won_amount = (
        _with_first_accepted_at(
            queryset.filter(
                currency=currency,
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


def build_dashboard_analytics(
    queryset: QuerySet[Quotation],
    currency: str = DEFAULT_DASHBOARD_CURRENCY,
) -> dict[str, object]:
    """Build bounded chart aggregates without serializing quotation rows."""
    local_now = timezone.localtime()
    currency_queryset = queryset.filter(currency=currency)
    breakdown_queryset = currency_queryset.filter(
        status__in=CHART_STATUSES,
        grand_total__gt=0,
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
            "source_quote_no",
            "grand_total",
            "status",
        )[:BREAKDOWN_MAX_ITEMS]
    )
    displayed_amount = sum(
        (row["grand_total"] for row in breakdown_rows),
        Decimal("0"),
    )
    breakdown = [
        {
            "quotation_id": row["id"],
            "quote_no": row["source_quote_no"] or row["quote_no"],
            "amount": _money(row["grand_total"]),
            "status": row["status"],
        }
        for row in breakdown_rows
    ]
    month_start = _month_start(local_now)
    month_starts = [
        _shift_month(month_start, offset)
        for offset in range(-(MONTH_PERIOD_COUNT - 1), 1)
    ]
    week_start = _week_start(local_now)
    week_starts = [
        week_start - timedelta(weeks=offset)
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
            "monthly": _trend_rows(
                currency_queryset,
                month_starts,
                TruncMonth,
                lambda value: value.strftime("%Y-%m"),
            ),
            "weekly": _trend_rows(
                currency_queryset,
                week_starts,
                TruncWeek,
                lambda value: value.date().isoformat(),
            ),
        },
        "generated_at": local_now.isoformat(),
    }


def build_dashboard_recent(
    queryset: QuerySet[Quotation],
    limit: int,
) -> dict[str, object]:
    """Return a bounded projection for the recent quotations card."""
    rows = queryset.order_by("-created_at").values(
        "id",
        "quote_no",
        "source_quote_no",
        "project_name",
        "client_company",
        "issuer_contact_name",
        "created_at",
        "currency",
        "grand_total",
        "status",
    )[:limit]
    return {
        "items": [
            {
                "id": row["id"],
                "quote_no": row["source_quote_no"] or row["quote_no"],
                "project_name": row["project_name"],
                "client_company": row["client_company"],
                "salesperson": row["issuer_contact_name"],
                "created_at": row["created_at"].isoformat(),
                "currency": row["currency"],
                "grand_total": _money(row["grand_total"]),
                "status": row["status"],
            }
            for row in rows
        ]
    }
