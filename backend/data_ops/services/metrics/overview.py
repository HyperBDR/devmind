from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.db.models.functions import TruncMonth
from django.utils import timezone

from data_ops.models import (
    Contract,
    DomesticLedger,
    OverseaProject,
    ProjectInit,
    SyncJob,
    SyncTableStatus,
)
from data_ops.services.metrics.owner_identities import (
    owner_payload,
    owner_payload_from_record,
)


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
    return [
        {
            "currency": item["currency"] or "未知",
            "amount": _number(item["amount"]),
        }
        for item in rows
    ]


def _single_currency_amount(items: list[dict]) -> float | None:
    if len(items) != 1:
        return None
    return items[0]["amount"]


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
            "expense_received_ratio": None,
            "target_achievement_rate": None,
        },
        "mom": {
            "monthly_signed_amount": None,
            "monthly_received_amount": None,
            "monthly_outstanding_amount": None,
            "monthly_expense_amount": None,
            "expense_received_ratio": None,
        },
        "meta": {
            "current_month": month_start.strftime("%Y-%m"),
            "previous_month": None,
            "currency_note": "Amounts follow source table currencies.",
        },
    }


def get_data_quality() -> dict:
    statuses = list(
        SyncTableStatus.objects.order_by("source_key", "table_key")
    )
    running_sync_count = SyncJob.objects.filter(
        status__in=["pending", "running"],
    ).count()
    failed_count = sum(1 for item in statuses if item.status == "failed")
    warning_count = sum(1 for item in statuses if item.status == "warning")
    overall_status = "ok"
    if failed_count:
        overall_status = "failed"
    elif warning_count:
        overall_status = "warning"

    return {
        "overall_status": overall_status,
        "running_sync_count": running_sync_count,
        "failed_sync_count": failed_count,
        "warning_sync_count": warning_count,
        "currency_note": "Amounts are not normalized across currencies yet.",
        "issues": [
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
        ],
    }


def get_trends() -> dict:
    return {
        "monthly_signed": _monthly_amounts(
            Contract.objects.exclude(signing_date__isnull=True),
            "signing_date",
            "total_amount",
        ),
        "monthly_received": _monthly_amounts(
            DomesticLedger.objects.filter(ledger_type="收入").exclude(
                receipt_time__isnull=True,
            ),
            "receipt_time",
            "payment_received",
        ),
        "monthly_expense": _monthly_amounts(
            DomesticLedger.objects.filter(ledger_type="支出").exclude(
                signing_date__isnull=True,
            ),
            "signing_date",
            "payment_amount",
        ),
        "monthly_net": [],
        "quarterly_signed": [],
        "quarterly_received": [],
        "quarterly_expense": [],
        "quarterly_net": [],
        "yearly_signed": [],
        "yearly_received": [],
        "yearly_expense": [],
        "yearly_net": [],
    }


def get_top_customers() -> dict:
    received = _rank_amounts(
        DomesticLedger.objects.filter(ledger_type="收入"),
        "customer_name",
        "payment_received",
    )
    outstanding = _rank_amounts(
        DomesticLedger.objects.filter(ledger_type="收入"),
        "customer_name",
        "outstanding",
    )
    return {
        "top_received": [
            {
                "customer_name": item["name"],
                "received_amount": item["amount"],
                "outstanding_amount": 0,
                "contract_count": 0,
                "risk_level": "low",
            }
            for item in received
        ],
        "top_outstanding": [
            {
                "customer_name": item["name"],
                "received_amount": 0,
                "outstanding_amount": item["amount"],
                "contract_count": 0,
                "risk_level": "medium" if item["amount"] else "low",
            }
            for item in outstanding
        ],
        "renewal_risks": _renewal_risks(),
    }


def get_top_sales() -> dict:
    received = _rank_amounts(
        DomesticLedger.objects.filter(ledger_type="收入"),
        "sales_person",
        "payment_received",
    )
    outstanding = _rank_amounts(
        DomesticLedger.objects.filter(ledger_type="收入"),
        "sales_person",
        "outstanding",
    )
    return {
        "top_received": [
            {
                "sales_person": item["name"],
                **owner_payload(item["name"]),
                "received_amount": item["amount"],
                "outstanding_amount": 0,
                "customer_count": 0,
                "high_potential_count": 0,
                "risk_level": "low",
            }
            for item in received
        ],
        "top_outstanding": [
            {
                "sales_person": item["name"],
                "received_amount": 0,
                "outstanding_amount": item["amount"],
                "customer_count": 0,
                "high_potential_count": 0,
                "risk_level": "medium" if item["amount"] else "low",
            }
            for item in outstanding
        ],
    }


def get_risks() -> dict:
    renewal_alerts = _renewal_risks()
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
            "risk_level": "high",
        }
        for item in DomesticLedger.objects.filter(
            ledger_type="收入",
            outstanding__gt=0,
        ).order_by("-outstanding")[:20]
    ]
    opportunities = _opportunity_items(limit=20)
    return {
        "summary": {
            "renewal_alert_count": len(renewal_alerts),
            "high_outstanding_count": len(high_outstanding),
            "stalled_opportunity_count": len(opportunities),
            "key_customer_risk_count": 0,
        },
        "renewal_alerts": renewal_alerts,
        "high_outstanding_items": high_outstanding,
        "stalled_opportunities": opportunities,
        "key_customer_risks": [],
    }


def get_opportunities() -> dict:
    items = _opportunity_items(limit=100)
    return {
        "summary": {
            "high_potential_count": len(items),
            "high_potential_total_amount": sum(
                item["estimated_amount"] for item in items
            ),
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
    contracts = Contract.objects.order_by("-synced_at")[:500]
    cards = [
        {
            "id": str(item.id),
            "contract_number": item.contract_number,
            "customer_name": item.customer_name,
            "sales_person": item.sales_person,
            "order_platform": item.order_platform,
            "currency": item.currency,
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
        "total": len(cards),
        "filters": _contract_filters(),
    }


def get_project_init_kanban() -> dict:
    rows = ProjectInit.objects.order_by("-synced_at")[:500]
    cards = [
        {
            "id": str(item.id),
            "project_code": item.project_code,
            "domestic_international": item.domestic_international,
            "customer_full_name": item.customer_full_name,
            "oa_initiation_date": (
                item.oa_initiation_date.isoformat()
                if item.oa_initiation_date
                else None
            ),
            "project_name": item.project_name,
            "sales_person": item.sales_person,
            "estimated_amount": _number(item.estimated_amount),
            "currency": item.currency,
        }
        for item in rows
    ]
    return {"cards": cards, "total": len(cards), "filters": {}}


def get_oversea_project_kanban() -> dict:
    rows = OverseaProject.objects.order_by("-synced_at")[:500]
    cards = [
        {
            "id": str(item.id),
            "project_name": item.project_name,
            "po_number": item.po_number,
            "country": item.country,
            "stat_amount_usd": _number(item.stat_amount_usd),
            "license_expiry": (
                item.license_expiry.isoformat()
                if item.license_expiry
                else None
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
    return {"cards": cards, "total": len(cards), "filters": {}}


def get_domestic_ledger_kanban() -> dict:
    rows = DomesticLedger.objects.filter(
        ledger_type="收入",
    ).order_by("expected_payment_date")[:500]
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
        "total": len(cards),
        "groups": [],
        "filters": {},
    }


def _monthly_amounts(queryset, date_field: str, amount_field: str) -> list:
    rows = (
        queryset.annotate(period=TruncMonth(date_field))
        .values("period", "currency")
        .annotate(amount=Coalesce(Sum(amount_field), Decimal("0")))
        .order_by("period", "currency")
    )
    return [
        {
            "month": item["period"].strftime("%Y-%m"),
            "currency": item["currency"] or "未知",
            "amount": _number(item["amount"]),
        }
        for item in rows
        if item["period"]
    ][-12:]


def _rank_amounts(queryset, name_field: str, amount_field: str) -> list:
    rows = (
        queryset.exclude(**{name_field: ""})
        .values(name_field, "currency")
        .annotate(amount=Coalesce(Sum(amount_field), Decimal("0")))
        .order_by("currency", "-amount")
    )
    ranked = []
    counts = {}
    for item in rows:
        currency = item["currency"] or "未知"
        if counts.get(currency, 0) >= 10:
            continue
        counts[currency] = counts.get(currency, 0) + 1
        amount = _number(item["amount"])
        ranked.append(
            {
                "name": item[name_field] or "-",
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


def _renewal_risks() -> list:
    today = timezone.localdate()
    deadline = today + timedelta(days=30)
    rows = Contract.objects.filter(
        service_end__gte=today,
        service_end__lte=deadline,
    ).order_by("service_end")[:20]
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
        for item in rows
    ]


def _opportunity_items(*, limit: int) -> list:
    rows = ProjectInit.objects.filter(
        estimated_amount__gt=Decimal("500000"),
    ).order_by("-estimated_amount")[:limit]
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
                item.oa_initiation_date.isoformat()
                if item.oa_initiation_date
                else None
            ),
            "risk_level": "low",
        }
        for item in rows
    ]


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
