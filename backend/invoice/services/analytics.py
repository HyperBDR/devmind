from __future__ import annotations

from collections import defaultdict
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Prefetch

from invoice.models import (
    Invoice,
    InvoiceDocumentKind,
    InvoiceItem,
    InvoiceStatus,
)
from invoice.permissions import invoice_visibility_filter
from invoice.services.regions import derive_customer_region


INCLUDED_STATUSES = (InvoiceStatus.ISSUED, InvoiceStatus.PAID)


def _is_dashboard_excluded_product(value: str | None) -> bool:
    """Exclude invoice detail descriptions that are not catalog products."""
    name = (value or "").strip().casefold()
    return name.startswith("landing zone design") or name.startswith(
        "landing zone build"
    )


def _period_key(value: date, granularity: str) -> str:
    if granularity == "year":
        return str(value.year)
    if granularity == "quarter":
        return f"{value.year}-Q{((value.month - 1) // 3) + 1}"
    return f"{value.year}-{value.month:02d}"


def _quarter_start(value: date) -> date:
    month = ((value.month - 1) // 3) * 3 + 1
    return value.replace(month=month, day=1)


def _year_start(value: date) -> date:
    return value.replace(month=1, day=1)


def _invoice_queryset(
    currency: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    user=None,
):
    queryset = Invoice.objects.filter(
        invoice_date__isnull=False,
        status__in=INCLUDED_STATUSES,
    ).exclude(
        document_kind=InvoiceDocumentKind.REFUND,
    )
    if currency:
        queryset = queryset.filter(currency=currency.upper())
    if start_date:
        queryset = queryset.filter(invoice_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(invoice_date__lte=end_date)
    if user is not None:
        queryset = queryset.filter(invoice_visibility_filter(user))
    return queryset.prefetch_related(
        Prefetch("items", queryset=InvoiceItem.objects.only(
            "invoice_id", "product_name", "total_amount", "net_amount"
        ))
    )


def _amount_series(invoices, granularity: str):
    totals = defaultdict(lambda: {"amount": Decimal("0"), "count": 0})
    for invoice in invoices:
        key = _period_key(invoice.invoice_date, granularity)
        totals[key]["amount"] += invoice.total_amount
        totals[key]["count"] += 1
    return [
        {
            "period": key,
            "amount": f"{value['amount']:.2f}",
            "invoice_count": value["count"],
        }
        for key, value in sorted(totals.items())
    ]


def _total_amount(invoices) -> Decimal:
    return sum(
        (invoice.total_amount for invoice in invoices),
        Decimal("0"),
    )


def _ranked_totals(rows, limit: int | None = None):
    totals = defaultdict(lambda: {"amount": Decimal("0"), "count": 0})
    for key, amount, count in rows:
        label = key or "Unspecified"
        totals[label]["amount"] += amount
        totals[label]["count"] += count
    ranked = sorted(
        totals.items(),
        key=lambda item: (-item[1]["amount"], item[0].casefold()),
    )
    if limit is not None:
        ranked = ranked[:limit]
    return [
        {
            "name": key,
            "amount": f"{value['amount']:.2f}",
            "invoice_count": value["count"],
        }
        for key, value in ranked
    ]


def _ranked_customers(invoices, limit: int = 10):
    totals = defaultdict(
        lambda: {"amount": Decimal("0"), "count": 0, "region": ""}
    )
    for invoice in invoices:
        label = invoice.customer_name or "Unspecified"
        totals[label]["amount"] += invoice.total_amount
        totals[label]["count"] += 1
        region = derive_customer_region(invoice.customer_address)
        if not region:
            region = invoice.region
        if region:
            totals[label]["region"] = region
    ranked = sorted(
        totals.items(),
        key=lambda item: (-item[1]["amount"], item[0].casefold()),
    )[:limit]
    return [
        {
            "name": key,
            "region": value["region"] or "Unspecified",
            "amount": f"{value['amount']:.2f}",
            "invoice_count": value["count"],
        }
        for key, value in ranked
    ]


def _shift_year(value: date, years: int) -> date:
    target_year = value.year + years
    day = min(value.day, monthrange(target_year, value.month)[1])
    return value.replace(year=target_year, day=day)


def sales_dashboard(
    *,
    as_of: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    currency: str | None = None,
    granularity: str = "month",
    comparison_years: int = 2,
    user=None,
) -> dict:
    """Build aggregates for issued and paid non-refund documents."""
    if granularity not in {"month", "quarter", "year"}:
        raise ValueError("granularity must be month, quarter, or year")
    if comparison_years not in {1, 2}:
        raise ValueError("comparison_years must be 1 or 2")
    end_date = end_date or as_of or date.today()
    start_date = start_date or _year_start(end_date)
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")
    invoices = list(
        _invoice_queryset(currency, start_date, end_date, user)
    )
    available_currencies = list(
        _invoice_queryset(None, start_date, end_date, user)
        .exclude(currency="")
        .values_list("currency", flat=True)
        .order_by("currency")
        .distinct()
    )
    quarter_start = _quarter_start(end_date)
    year_start = _year_start(end_date)
    qtd = list(_invoice_queryset(currency, quarter_start, end_date, user))
    ytd = list(_invoice_queryset(currency, year_start, end_date, user))
    region_rows = [
        (
            derive_customer_region(invoice.customer_address) or invoice.region,
            invoice.total_amount,
            1,
        )
        for invoice in invoices
    ]
    product_rows = [
        (
            item.product_name,
            item.total_amount or item.net_amount,
            1,
        )
        for invoice in invoices
        for item in invoice.items.all()
        if not _is_dashboard_excluded_product(item.product_name)
    ]
    comparison = []
    for year_offset in range(1, max(0, comparison_years) + 1):
        comparison_year = end_date.year - year_offset
        comparison_start = date(comparison_year, 1, 1)
        comparison_end = date(comparison_year, 12, 31)
        selected_comparison_end = _shift_year(end_date, -year_offset)
        year_invoices = list(
            _invoice_queryset(
                currency,
                comparison_start,
                comparison_end,
                user,
            )
        )
        comparison_quarter_start = _shift_year(
            quarter_start,
            -year_offset,
        )
        comparison_year_start = _shift_year(
            year_start,
            -year_offset,
        )
        comparison_qtd = list(
            _invoice_queryset(
                currency,
                comparison_quarter_start,
                selected_comparison_end,
                user,
            )
        )
        comparison_ytd = list(
            _invoice_queryset(
                currency,
                comparison_year_start,
                selected_comparison_end,
                user,
            )
        )
        comparison.append(
            {
                "year": comparison_year,
                "series": _amount_series(year_invoices, granularity),
                "quarter_to_date_amount": (
                    f"{_total_amount(comparison_qtd):.2f}"
                ),
                "year_to_date_amount": (
                    f"{_total_amount(comparison_ytd):.2f}"
                ),
            }
        )
    rolling_end = end_date
    rolling_start = _shift_year(rolling_end, -1) + timedelta(days=1)
    previous_rolling_end = _shift_year(rolling_end, -1)
    previous_rolling_start = (
        _shift_year(previous_rolling_end, -1) + timedelta(days=1)
    )
    rolling_invoices = list(
        _invoice_queryset(currency, rolling_start, rolling_end, user)
    )
    previous_rolling_invoices = list(
        _invoice_queryset(
            currency,
            previous_rolling_start,
            previous_rolling_end,
            user,
        )
    )
    return {
        "as_of": end_date.isoformat(),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "currency": currency.upper() if currency else None,
        "available_currencies": available_currencies,
        "granularity": granularity,
        "series": _amount_series(invoices, granularity),
        "quarter_to_date": _amount_series(qtd, "year"),
        "year_to_date": _amount_series(ytd, "year"),
        "by_region": _ranked_totals(region_rows),
        "by_product": _ranked_totals(product_rows),
        "top_customers": _ranked_customers(invoices),
        "comparison": comparison,
        "year_over_year": {
            "amount": f"{_total_amount(rolling_invoices):.2f}",
            "previous_amount": (
                f"{_total_amount(previous_rolling_invoices):.2f}"
            ),
            "start_date": rolling_start.isoformat(),
            "end_date": rolling_end.isoformat(),
            "previous_start_date": previous_rolling_start.isoformat(),
            "previous_end_date": previous_rolling_end.isoformat(),
        },
    }
