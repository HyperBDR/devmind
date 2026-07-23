from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from data_ops.models import (
    Contract,
    DomesticLedger,
    OverseaProject,
    Project,
    ProjectInit,
    SyncJob,
    SyncTableStatus,
)
from data_ops.services.metrics.currency import normalize_currency
from data_ops.services.metrics.owner_identities import (
    owner_payload,
    owner_payload_from_record,
)
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

ZERO_DECIMAL = Decimal("0")


def _number(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _amounts_by_currency(queryset, amount_field: str) -> list[dict]:
    rows = (
        queryset.values("currency")
        .annotate(amount=Coalesce(Sum(amount_field), ZERO_DECIMAL))
        .order_by("currency")
    )
    buckets = {}
    for item in rows:
        currency = normalize_currency(item["currency"])
        buckets[currency] = buckets.get(currency, 0.0) + _number(item["amount"])
    return [
        {"currency": currency, "amount": amount}
        for currency, amount in sorted(buckets.items())
    ]


def _single_currency_amount(items: list[dict]) -> float | None:
    if len(items) != 1:
        return None
    return items[0]["amount"]


def _amount_map(items: list[dict], value_key: str = "amount") -> dict:
    return {item["currency"]: item[value_key] for item in items}


def _percentage_change(current: float | None, previous: float | None):
    if current is None or previous in (None, 0):
        return None
    return (current - previous) / previous * 100


def _changes_by_currency(
    current_items: list[dict],
    previous_items: list[dict],
) -> list[dict]:
    current = _amount_map(current_items)
    previous = _amount_map(previous_items)
    return [
        {
            "currency": currency,
            "current_amount": current.get(currency, 0.0),
            "previous_amount": previous.get(currency, 0.0),
            "change_rate": _percentage_change(
                current.get(currency, 0.0),
                previous.get(currency, 0.0),
            ),
        }
        for currency in sorted(set(current) | set(previous))
    ]


def _ratios_by_currency(
    numerator_items: list[dict],
    denominator_items: list[dict],
) -> list[dict]:
    numerators = _amount_map(numerator_items)
    denominators = _amount_map(denominator_items)
    return [
        {
            "currency": currency,
            "ratio": (
                numerators.get(currency, 0.0) / denominators[currency] * 100
                if denominators.get(currency)
                else None
            ),
        }
        for currency in sorted(set(numerators) | set(denominators))
    ]


def _single_value(items: list[dict], value_key: str):
    if len(items) != 1:
        return None
    return items[0][value_key]


def get_summary() -> dict:
    contract_total = Contract.objects.aggregate(count=Count("id"))
    contract_amounts = _amounts_by_currency(
        Contract.objects.all(),
        "total_amount",
    )
    income_rows = DomesticLedger.objects.filter(ledger_type="收入")
    expense_rows = DomesticLedger.objects.filter(ledger_type="支出")
    received_amounts = _amounts_by_currency(
        income_rows,
        "payment_received",
    )
    outstanding_amounts = _amounts_by_currency(
        income_rows,
        "outstanding",
    )
    expense_amounts = _amounts_by_currency(
        expense_rows,
        "payment_amount",
    )
    return {
        "total_contracts": contract_total["count"],
        "total_contract_amount": _single_currency_amount(contract_amounts),
        "total_contract_amount_by_currency": contract_amounts,
        "total_received_amount": _single_currency_amount(received_amounts),
        "total_received_amount_by_currency": received_amounts,
        "total_outstanding_amount": _single_currency_amount(
            outstanding_amounts,
        ),
        "total_outstanding_amount_by_currency": outstanding_amounts,
        "total_expense_amount": _single_currency_amount(expense_amounts),
        "total_expense_amount_by_currency": expense_amounts,
    }


def get_executive_overview() -> dict:
    today = timezone.localdate()
    month_start = today.replace(day=1)
    previous_month_end = month_start - timedelta(days=1)
    previous_month_start = previous_month_end.replace(day=1)
    signed_amounts = _amounts_by_currency(
        Contract.objects.filter(
            signing_date__gte=month_start,
            signing_date__lte=today,
        ),
        "total_amount",
    )
    received_amounts = _amounts_by_currency(
        DomesticLedger.objects.filter(
            ledger_type="收入",
            receipt_time__gte=month_start,
            receipt_time__lte=today,
        ),
        "payment_received",
    )
    outstanding_amounts = _amounts_by_currency(
        DomesticLedger.objects.filter(ledger_type="收入"),
        "outstanding",
    )
    expense_amounts = _amounts_by_currency(
        DomesticLedger.objects.filter(
            ledger_type="支出",
            signing_date__gte=month_start,
            signing_date__lte=today,
        ),
        "payment_amount",
    )
    previous_signed_amounts = _amounts_by_currency(
        Contract.objects.filter(
            signing_date__gte=previous_month_start,
            signing_date__lte=previous_month_end,
        ),
        "total_amount",
    )
    previous_received_amounts = _amounts_by_currency(
        DomesticLedger.objects.filter(
            ledger_type="收入",
            receipt_time__gte=previous_month_start,
            receipt_time__lte=previous_month_end,
        ),
        "payment_received",
    )
    previous_expense_amounts = _amounts_by_currency(
        DomesticLedger.objects.filter(
            ledger_type="支出",
            signing_date__gte=previous_month_start,
            signing_date__lte=previous_month_end,
        ),
        "payment_amount",
    )
    expense_received_ratios = _ratios_by_currency(
        expense_amounts,
        received_amounts,
    )
    previous_expense_received_ratios = _ratios_by_currency(
        previous_expense_amounts,
        previous_received_amounts,
    )
    signed_changes = _changes_by_currency(
        signed_amounts,
        previous_signed_amounts,
    )
    received_changes = _changes_by_currency(
        received_amounts,
        previous_received_amounts,
    )
    expense_changes = _changes_by_currency(
        expense_amounts,
        previous_expense_amounts,
    )
    ratio_changes = _changes_by_currency(
        [
            {"currency": item["currency"], "amount": item["ratio"]}
            for item in expense_received_ratios
            if item["ratio"] is not None
        ],
        [
            {"currency": item["currency"], "amount": item["ratio"]}
            for item in previous_expense_received_ratios
            if item["ratio"] is not None
        ],
    )

    return {
        "kpis": {
            "monthly_signed_amount": _single_currency_amount(signed_amounts),
            "monthly_signed_amount_by_currency": signed_amounts,
            "monthly_received_amount": _single_currency_amount(
                received_amounts,
            ),
            "monthly_received_amount_by_currency": received_amounts,
            "monthly_outstanding_amount": _single_currency_amount(
                outstanding_amounts,
            ),
            "monthly_outstanding_amount_by_currency": outstanding_amounts,
            "monthly_expense_amount": _single_currency_amount(expense_amounts),
            "monthly_expense_amount_by_currency": expense_amounts,
            "expense_received_ratio": _single_value(
                expense_received_ratios,
                "ratio",
            ),
            "expense_received_ratio_by_currency": expense_received_ratios,
            "target_achievement_rate": None,
        },
        "mom": {
            "monthly_signed_amount": _single_value(
                signed_changes,
                "change_rate",
            ),
            "monthly_received_amount": _single_value(
                received_changes,
                "change_rate",
            ),
            "monthly_outstanding_amount": None,
            "monthly_expense_amount": _single_value(
                expense_changes,
                "change_rate",
            ),
            "expense_received_ratio": _single_value(
                ratio_changes,
                "change_rate",
            ),
        },
        "mom_by_currency": {
            "monthly_signed_amount": signed_changes,
            "monthly_received_amount": received_changes,
            "monthly_expense_amount": expense_changes,
            "expense_received_ratio": ratio_changes,
        },
        "meta": {
            "current_month": month_start.strftime("%Y-%m"),
            "previous_month": previous_month_start.strftime("%Y-%m"),
            "currency_note": "Amounts follow source table currencies.",
        },
    }


def get_data_quality() -> dict:
    statuses = list(SyncTableStatus.objects.order_by("source_key", "table_key"))
    running_sync_count = SyncJob.objects.filter(
        status__in=["pending", "running"],
    ).count()
    failed_count = sum(1 for item in statuses if item.status == "failed")
    warning_count = sum(1 for item in statuses if item.status == "warning")
    sync_status = "ok"
    if failed_count:
        sync_status = "failed"
    elif warning_count:
        sync_status = "warning"

    summary = get_summary()
    currency_groups = [
        summary["total_contract_amount_by_currency"],
        summary["total_received_amount_by_currency"],
        summary["total_outstanding_amount_by_currency"],
        summary["total_expense_amount_by_currency"],
    ]
    currency_counts = [
        sum(1 for item in items if abs(item["amount"]) > 0) for items in currency_groups
    ]
    has_mixed_currency = any(count > 1 for count in currency_counts)

    overall_status = sync_status
    if overall_status == "ok" and has_mixed_currency:
        overall_status = "warning"

    issues = []
    if has_mixed_currency:
        issues.append(
            {
                "id": "mixed-currency",
                "title": "Mixed-currency aggregation",
                "severity": "warning",
                "count": max(currency_counts),
                "detail": (
                    "Amounts retain their source currencies and cannot be "
                    "combined into one decision metric."
                ),
                "recommendation": (
                    "Review currency buckets separately until a governed "
                    "exchange-rate policy is available."
                ),
            }
        )
    issues.extend(
        {
            "id": f"{item.source_key}:{item.table_key}",
            "title": item.table_name,
            "severity": item.status,
            "count": len(item.missing_fields or []),
            "detail": item.message,
            "recommendation": item.resolution_hint,
        }
        for item in statuses
        if item.status in {"failed", "warning"}
    )

    return {
        "overall_status": overall_status,
        "analysis_status": (
            "blocked"
            if sync_status == "failed"
            else "limited" if overall_status == "warning" else "ready"
        ),
        "sync_status": sync_status,
        "running_sync_count": running_sync_count,
        "failed_sync_count": failed_count,
        "warning_sync_count": warning_count,
        "currency_note": "Amounts are not normalized across currencies yet.",
        "issues": issues,
    }


def get_trends() -> dict:
    monthly_signed = _monthly_amounts(
        Contract.objects.exclude(signing_date__isnull=True),
        "signing_date",
        "total_amount",
    )
    monthly_received = _monthly_amounts(
        DomesticLedger.objects.filter(ledger_type="收入").exclude(
            receipt_time__isnull=True,
        ),
        "receipt_time",
        "payment_received",
    )
    monthly_expense = _monthly_amounts(
        DomesticLedger.objects.filter(ledger_type="支出").exclude(
            signing_date__isnull=True,
        ),
        "signing_date",
        "payment_amount",
    )
    monthly_net = _subtract_amount_series(
        monthly_received,
        monthly_expense,
        "month",
    )
    return {
        "monthly_signed": monthly_signed,
        "monthly_received": monthly_received,
        "monthly_expense": monthly_expense,
        "monthly_net": monthly_net,
        "quarterly_signed": _aggregate_amount_period(
            monthly_signed,
            "quarter",
        ),
        "quarterly_received": _aggregate_amount_period(
            monthly_received,
            "quarter",
        ),
        "quarterly_expense": _aggregate_amount_period(
            monthly_expense,
            "quarter",
        ),
        "quarterly_net": _aggregate_amount_period(
            monthly_net,
            "quarter",
        ),
        "yearly_signed": _aggregate_amount_period(monthly_signed, "year"),
        "yearly_received": _aggregate_amount_period(
            monthly_received,
            "year",
        ),
        "yearly_expense": _aggregate_amount_period(
            monthly_expense,
            "year",
        ),
        "yearly_net": _aggregate_amount_period(monthly_net, "year"),
    }


def get_top_customers() -> dict:
    income_rows = DomesticLedger.objects.filter(
        ledger_type="收入",
    ).exclude(customer_name="")
    contract_counts = {
        item["customer_name"]: item["contract_count"]
        for item in Contract.objects.exclude(customer_name="")
        .values("customer_name")
        .annotate(contract_count=Count("id"))
    }
    sales_by_customer_currency = {}
    sales_rows = (
        income_rows.exclude(sales_person="")
        .values("customer_name", "currency", "sales_person")
        .distinct()
        .order_by("customer_name", "currency", "sales_person")
    )
    for item in sales_rows:
        key = (
            item["customer_name"],
            normalize_currency(item["currency"]),
        )
        sales_by_customer_currency.setdefault(key, []).append(item["sales_person"])

    customer_amounts = {}
    amount_rows = income_rows.values("customer_name", "currency").annotate(
        received_amount=Coalesce(
            Sum("payment_received"),
            ZERO_DECIMAL,
        ),
        outstanding_amount=Coalesce(
            Sum("outstanding"),
            ZERO_DECIMAL,
        ),
    )
    for item in amount_rows:
        customer_name = item["customer_name"]
        currency = normalize_currency(item["currency"])
        key = (customer_name, currency)
        amounts = customer_amounts.setdefault(
            key,
            {"received_amount": 0.0, "outstanding_amount": 0.0},
        )
        amounts["received_amount"] += _number(item["received_amount"])
        amounts["outstanding_amount"] += _number(item["outstanding_amount"])

    customer_rows = []
    for (customer_name, currency), amounts in customer_amounts.items():
        outstanding_amount = amounts["outstanding_amount"]
        customer_rows.append(
            {
                "customer_name": customer_name,
                "currency": currency,
                "sales_person": "、".join(
                    sales_by_customer_currency.get(
                        (customer_name, currency),
                        [],
                    )
                ),
                "received_amount": amounts["received_amount"],
                "outstanding_amount": outstanding_amount,
                "contract_count": contract_counts.get(customer_name, 0),
                "risk_level": ("medium" if outstanding_amount > 0 else "low"),
            }
        )

    return {
        "top_received": _rank_customer_rows(
            customer_rows,
            "received_amount",
        ),
        "top_outstanding": _rank_customer_rows(
            customer_rows,
            "outstanding_amount",
        ),
        "renewal_risks": _renewal_risks(),
    }


def get_top_sales() -> dict:
    income_rows = DomesticLedger.objects.filter(
        ledger_type="收入",
    ).exclude(sales_person="")
    customer_counts = {
        item["sales_person"]: item["customer_count"]
        for item in income_rows.exclude(customer_name="")
        .values("sales_person")
        .annotate(customer_count=Count("customer_name", distinct=True))
    }
    high_potential_counts = {
        item["sales_person"]: item["project_count"]
        for item in Project.objects.filter(is_high_potential=True)
        .exclude(sales_person="")
        .values("sales_person")
        .annotate(project_count=Count("id"))
    }
    amount_buckets = {}
    amount_rows = income_rows.values("sales_person", "currency").annotate(
        received_amount=Coalesce(
            Sum("payment_received"),
            ZERO_DECIMAL,
        ),
        outstanding_amount=Coalesce(
            Sum("outstanding"),
            ZERO_DECIMAL,
        ),
    )
    for item in amount_rows:
        sales_person = item["sales_person"]
        currency = normalize_currency(item["currency"])
        key = (sales_person, currency)
        amounts = amount_buckets.setdefault(
            key,
            {"received_amount": 0.0, "outstanding_amount": 0.0},
        )
        amounts["received_amount"] += _number(item["received_amount"])
        amounts["outstanding_amount"] += _number(item["outstanding_amount"])

    sales_rows = []
    for (sales_person, currency), amounts in amount_buckets.items():
        outstanding_amount = amounts["outstanding_amount"]
        sales_rows.append(
            {
                "sales_person": sales_person,
                **owner_payload(sales_person),
                "currency": currency,
                "received_amount": amounts["received_amount"],
                "outstanding_amount": outstanding_amount,
                "customer_count": customer_counts.get(sales_person, 0),
                "high_potential_count": high_potential_counts.get(
                    sales_person,
                    0,
                ),
                "risk_level": ("medium" if outstanding_amount > 0 else "low"),
            }
        )
    return {
        "top_received": _rank_sales_rows(
            sales_rows,
            "received_amount",
        ),
        "top_outstanding": _rank_sales_rows(
            sales_rows,
            "outstanding_amount",
        ),
    }


def get_risks() -> dict:
    today = timezone.localdate()
    renewal_queryset = _renewal_risk_queryset(today)
    renewal_alerts = _renewal_risks(queryset=renewal_queryset)
    high_outstanding_queryset = DomesticLedger.objects.filter(
        ledger_type="收入",
        outstanding__gt=0,
    )
    high_outstanding = [
        {
            "customer_name": item.customer_name or "-",
            "sales_person": item.sales_person,
            **owner_payload_from_record(item, "sales_person"),
            "project_name": item.project_name,
            "outstanding_amount": _number(item.outstanding),
            "expected_payment_date": (
                item.expected_payment_date.isoformat()
                if item.expected_payment_date
                else None
            ),
            "risk_level": (
                "high"
                if item.expected_payment_date and item.expected_payment_date < today
                else "medium"
            ),
        }
        for item in high_outstanding_queryset.order_by("-outstanding")[:20]
    ]
    opportunities = _opportunity_items(limit=20)
    key_customer_risks = [
        item
        for item in get_top_customers()["top_received"]
        if item["outstanding_amount"] > 0
    ]
    return {
        "summary": {
            "renewal_alert_count": renewal_queryset.count(),
            "high_outstanding_count": high_outstanding_queryset.count(),
            "stalled_opportunity_count": len(opportunities),
            "key_customer_risk_count": len(key_customer_risks),
        },
        "renewal_alerts": renewal_alerts,
        "high_outstanding_items": high_outstanding,
        "stalled_opportunities": opportunities,
        "key_customer_risks": key_customer_risks,
    }


def get_opportunities() -> dict:
    items = _opportunity_items(limit=100)
    summary = _opportunity_queryset().aggregate(
        count=Count("id"),
        total_amount=Coalesce(Sum("estimated_amount"), ZERO_DECIMAL),
    )
    return {
        "summary": {
            "high_potential_count": summary["count"],
            "high_potential_total_amount": _number(summary["total_amount"]),
        },
        "items": items,
    }


def get_contract_kanban() -> dict:
    rows = (
        Contract.objects.values("status", "order_platform")
        .annotate(
            contract_count=Count("id"),
            total_amount=Coalesce(Sum("total_amount"), Decimal("0")),
        )
        .order_by("status", "order_platform")
    )
    groups = {}
    for row in rows:
        status = row["status"] or "未知"
        platform = row["order_platform"] or "未知"
        groups.setdefault(status, {"status": status, "platforms": []})
        groups[status]["platforms"].append(
            {
                "platform": platform,
                "contract_count": row["contract_count"],
                "total_amount": _number(row["total_amount"]),
            }
        )
    return {"status_groups": list(groups.values())}


def get_contract_cards() -> dict:
    queryset = Contract.objects.order_by("-synced_at")
    contracts = queryset[:500]
    cards = [
        {
            "id": str(item.id),
            "contract_number": item.contract_number,
            "customer_name": item.customer_name,
            "sales_person": item.sales_person,
            "order_platform": item.order_platform,
            "currency": normalize_currency(item.currency),
            "total_amount": _number(item.total_amount),
            "signing_date": (
                item.signing_date.isoformat() if item.signing_date else None
            ),
            "status": item.status,
        }
        for item in contracts
    ]
    return {
        "cards": cards,
        "total": queryset.count(),
        "filters": _contract_filters(),
    }


def get_project_init_kanban() -> dict:
    queryset = ProjectInit.objects.order_by("-synced_at")
    rows = queryset[:500]
    cards = [
        {
            "id": str(item.id),
            "project_code": item.project_code,
            "domestic_international": item.domestic_international,
            "customer_full_name": item.customer_full_name,
            "oa_initiation_date": (
                item.oa_initiation_date.isoformat() if item.oa_initiation_date else None
            ),
            "project_name": item.project_name,
            "sales_person": item.sales_person,
            "estimated_amount": _number(item.estimated_amount),
            "currency": normalize_currency(item.currency),
        }
        for item in rows
    ]
    return {
        "cards": cards,
        "total": queryset.count(),
        "filters": _filter_options(
            ProjectInit,
            (
                "domestic_international",
                "sales_person",
                "currency",
                "signing_party_type",
            ),
        ),
    }


def get_oversea_project_kanban() -> dict:
    queryset = OverseaProject.objects.order_by("-synced_at")
    rows = queryset[:500]
    cards = [
        {
            "id": str(item.id),
            "project_name": item.project_name,
            "po_number": item.po_number,
            "country": item.country,
            "stat_amount_usd": _number(item.stat_amount_usd),
            "license_expiry": (
                item.license_expiry.isoformat() if item.license_expiry else None
            ),
            "project_owner": item.project_owner,
            "order_type": item.order_type,
            "product_type": item.product_type,
            "sales_person": item.project_owner,
            "order_status": item.order_status,
            "acceptance_status": item.acceptance_status,
        }
        for item in rows
    ]
    return {
        "cards": cards,
        "total": queryset.count(),
        "filters": _filter_options(
            OverseaProject,
            (
                "country",
                "project_owner",
                "currency",
                "product_type",
                "status",
                "order_type",
                "order_status",
                "acceptance_status",
            ),
        ),
    }


def get_domestic_ledger_kanban() -> dict:
    queryset = DomesticLedger.objects.filter(
        ledger_type="收入",
    )
    rows = queryset.order_by("expected_payment_date")[:500]
    cards = [
        {
            "id": str(item.id),
            "customer_name": item.customer_name,
            "project_name": item.project_name,
            "sales_person": item.sales_person,
            "signing_entity": item.signing_entity,
            "total_contract_amount": _number(item.total_contract_amount),
            "payment_received": _number(item.payment_received),
            "outstanding": _number(item.outstanding),
            "expected_payment_date": (
                item.expected_payment_date.isoformat()
                if item.expected_payment_date
                else None
            ),
            "payment_status": item.payment_status,
        }
        for item in rows
    ]
    return {
        "cards": cards,
        "total": queryset.count(),
        "groups": _domestic_ledger_groups(queryset),
        "filters": _filter_options(
            DomesticLedger,
            (
                "sales_person",
                "signing_entity",
                "payment_status",
                "currency",
                "year",
            ),
            base_queryset=queryset,
        ),
    }


def _monthly_amounts(queryset, date_field: str, amount_field: str) -> list:
    rows = (
        queryset.annotate(period=TruncMonth(date_field))
        .values("period", "currency")
        .annotate(amount=Coalesce(Sum(amount_field), Decimal("0")))
        .order_by("period", "currency")
    )
    buckets = {}
    for item in rows:
        if not item["period"]:
            continue
        key = (
            item["period"].strftime("%Y-%m"),
            normalize_currency(item["currency"]),
        )
        buckets[key] = buckets.get(key, 0.0) + _number(item["amount"])
    return [
        {"month": month, "currency": currency, "amount": amount}
        for (month, currency), amount in sorted(buckets.items())
    ]


def _subtract_amount_series(
    minuend_items: list[dict],
    subtrahend_items: list[dict],
    period_key: str,
) -> list[dict]:
    buckets = {}
    for item in minuend_items:
        key = (item[period_key], item["currency"])
        buckets[key] = buckets.get(key, 0.0) + item["amount"]
    for item in subtrahend_items:
        key = (item[period_key], item["currency"])
        buckets[key] = buckets.get(key, 0.0) - item["amount"]
    return [
        {period_key: period, "currency": currency, "amount": amount}
        for (period, currency), amount in sorted(buckets.items())
    ]


def _aggregate_amount_period(
    monthly_items: list[dict],
    period_type: str,
) -> list[dict]:
    buckets = {}
    for item in monthly_items:
        year, month = item["month"].split("-")
        if period_type == "quarter":
            quarter = (int(month) - 1) // 3 + 1
            period = f"{year}-Q{quarter}"
        else:
            period = year
        key = (period, item["currency"])
        buckets[key] = buckets.get(key, 0.0) + item["amount"]
    return [
        {period_type: period, "currency": currency, "amount": amount}
        for (period, currency), amount in sorted(buckets.items())
    ]


def _rank_amounts(queryset, name_field: str, amount_field: str) -> list:
    rows = (
        queryset.exclude(**{name_field: ""})
        .values(name_field, "currency")
        .annotate(amount=Coalesce(Sum(amount_field), Decimal("0")))
        .order_by("currency", "-amount")
    )
    amount_buckets = {}
    for item in rows:
        key = (
            item[name_field] or "-",
            normalize_currency(item["currency"]),
        )
        amount_buckets[key] = amount_buckets.get(key, 0.0) + _number(item["amount"])

    ranked = []
    counts = {}
    ordered_rows = sorted(
        amount_buckets.items(),
        key=lambda item: (item[0][1], -item[1], item[0][0]),
    )
    for (name, currency), amount in ordered_rows:
        if counts.get(currency, 0) >= 10:
            continue
        counts[currency] = counts.get(currency, 0) + 1
        ranked.append(
            {
                "name": name,
                "currency": currency,
                "amount": amount,
                "amount_by_currency": [
                    {
                        "currency": currency,
                        "amount": amount,
                    }
                ],
            }
        )
    return ranked


def _rank_customer_rows(rows: list[dict], amount_field: str) -> list[dict]:
    ordered_rows = sorted(
        rows,
        key=lambda item: (
            item["currency"],
            -item[amount_field],
            item["customer_name"],
        ),
    )
    ranked = []
    counts = {}
    for item in ordered_rows:
        currency = item["currency"]
        if counts.get(currency, 0) >= 10:
            continue
        counts[currency] = counts.get(currency, 0) + 1
        ranked.append(item)
    return ranked


def _rank_sales_rows(rows: list[dict], amount_field: str) -> list[dict]:
    ordered_rows = sorted(
        rows,
        key=lambda item: (
            item["currency"],
            -item[amount_field],
            item["sales_person"],
        ),
    )
    ranked = []
    counts = {}
    for item in ordered_rows:
        currency = item["currency"]
        if counts.get(currency, 0) >= 10:
            continue
        counts[currency] = counts.get(currency, 0) + 1
        ranked.append(item)
    return ranked


def _renewal_risk_queryset(today=None):
    today = today or timezone.localdate()
    deadline = today + timedelta(days=30)
    return Contract.objects.filter(
        service_end__gte=today,
        service_end__lte=deadline,
    ).order_by("service_end")


def _renewal_risks(*, queryset=None) -> list:
    today = timezone.localdate()
    rows = queryset if queryset is not None else _renewal_risk_queryset(today)
    return [
        {
            "customer_name": item.customer_name or "-",
            "contract_number": item.contract_number,
            "service_end": item.service_end.isoformat(),
            "days_left": (item.service_end - today).days,
            "sales_person": item.sales_person,
            **owner_payload_from_record(item, "sales_person"),
            "risk_level": (
                "high" if (item.service_end - today).days <= 14 else "medium"
            ),
        }
        for item in rows[:20]
    ]


def _opportunity_items(*, limit: int) -> list:
    rows = _opportunity_queryset()[:limit]
    return [
        {
            "id": str(item.id),
            "project_name": item.project_name,
            "customer_full_name": item.customer_full_name,
            "sales_person": item.sales_person,
            **owner_payload_from_record(item, "sales_person"),
            "domestic_international": item.domestic_international,
            "estimated_amount": _number(item.estimated_amount),
            "oa_initiation_date": (
                item.oa_initiation_date.isoformat() if item.oa_initiation_date else None
            ),
            "risk_level": "low",
        }
        for item in rows
    ]


def _opportunity_queryset():
    return ProjectInit.objects.filter(
        estimated_amount__gt=Decimal("500000"),
    ).order_by("-estimated_amount")


def _contract_filters() -> dict:
    fields = {
        "sales_person": "sales_person",
        "platform": "order_platform",
        "region": "region",
        "signing_entity": "signing_entity",
        "channel_type": "channel_type",
        "order_type": "signing_type",
        "status": "status",
    }
    return {
        key: list(
            Contract.objects.exclude(**{f"{field}": ""})
            .order_by(field)
            .values_list(field, flat=True)
            .distinct()
        )
        for key, field in fields.items()
    }


def _filter_options(
    model,
    fields: tuple[str, ...],
    *,
    base_queryset=None,
) -> dict:
    queryset = base_queryset if base_queryset is not None else model.objects
    payload = {}
    for field in fields:
        values = queryset.values_list(field, flat=True).distinct()
        if field == "currency":
            payload[field] = sorted({normalize_currency(value) for value in values})
        else:
            payload[field] = sorted(value for value in values if value)
    return payload


def _domestic_ledger_groups(queryset) -> list[dict]:
    rows = (
        queryset.values("payment_status", "currency")
        .annotate(
            record_count=Count("id"),
            total_contract_amount=Coalesce(
                Sum("total_contract_amount"),
                ZERO_DECIMAL,
            ),
            payment_received=Coalesce(
                Sum("payment_received"),
                ZERO_DECIMAL,
            ),
            outstanding=Coalesce(Sum("outstanding"), ZERO_DECIMAL),
        )
        .order_by("payment_status", "currency")
    )
    buckets = {}
    for item in rows:
        payment_status = item["payment_status"] or "未更新"
        currency = normalize_currency(item["currency"])
        bucket = buckets.setdefault(
            (payment_status, currency),
            {
                "payment_status": payment_status,
                "currency": currency,
                "record_count": 0,
                "total_contract_amount": 0.0,
                "payment_received": 0.0,
                "outstanding": 0.0,
            },
        )
        bucket["record_count"] += item["record_count"]
        bucket["total_contract_amount"] += _number(item["total_contract_amount"])
        bucket["payment_received"] += _number(item["payment_received"])
        bucket["outstanding"] += _number(item["outstanding"])
    return [buckets[key] for key in sorted(buckets)]
