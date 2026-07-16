from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.http import Http404
from django.utils import timezone

from data_ops.models import (
    Contract,
    ContractHistory,
    DomesticLedger,
    OverseaProject,
    OverseaSettlement,
    Project,
    ProjectInit,
    ProjectScope,
    SalesRecord,
)
from data_ops.services.metrics.currency import normalize_currency
from data_ops.services.metrics.owner_identities import (
    owner_payload_from_record,
)


ZERO_DECIMAL = Decimal("0")


def _number(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _date(value) -> str | None:
    return value.isoformat() if value else None


def _page_queryset(queryset, page: int, page_size: int):
    safe_page = max(_safe_int(page, 1), 1)
    safe_size = min(max(_safe_int(page_size, 50), 1), 200)
    start = (safe_page - 1) * safe_size
    return queryset[start : start + safe_size]


def _safe_int(value, default: int) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _split_multi(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _apply_contract_filters(queryset, params: dict[str, Any]):
    customer_name = str(params.get("customer_name") or "").strip()
    if customer_name:
        queryset = queryset.filter(customer_name__icontains=customer_name)

    field_map = {
        "sales_person": "sales_person",
        "platform": "order_platform",
        "status": "status",
        "signing_entity": "signing_entity",
        "channel_type": "channel_type",
        "enduser_customer": "enduser_customer",
        "region": "region",
        "product_category": "product_category",
        "signing_type": "signing_type",
        "currency": "currency",
    }
    for param_key, field_name in field_map.items():
        raw = params.get(param_key)
        values = _split_multi(raw)
        if values:
            queryset = queryset.filter(**{f"{field_name}__in": values})
        elif raw:
            queryset = queryset.filter(**{f"{field_name}__icontains": raw})
    return queryset


def _apply_sales_filters(queryset, params: dict[str, Any]):
    field_map = {
        "status": "status",
        "region": "region",
        "product_type": "product_type",
        "order_type": "order_type",
        "allocation_date": "allocation_date",
    }
    for param_key, field_name in field_map.items():
        value = params.get(param_key)
        if value:
            queryset = queryset.filter(**{field_name: value})
    return queryset


def _contract_row(contract: Contract) -> dict:
    return {
        "id": str(contract.id),
        "contract_number": contract.contract_number,
        "customer_name": contract.customer_name,
        "signing_entity": contract.signing_entity,
        "channel_type": contract.channel_type,
        "enduser_customer": contract.enduser_customer,
        "order_platform": contract.order_platform,
        "sales_person": contract.sales_person,
        **owner_payload_from_record(contract, "sales_person"),
        "region": contract.region,
        "currency": normalize_currency(contract.currency),
        "total_amount": _number(contract.total_amount),
        "product_category": contract.product_category,
        "signing_type": contract.signing_type,
        "signing_date": _date(contract.signing_date),
        "service_start": _date(contract.service_start),
        "service_end": _date(contract.service_end),
        "status": contract.status,
        "filing_type": contract.filing_type,
        "contract_sub_type": contract.contract_sub_type,
        "expiry_status": contract.expiry_status,
        "source_record_id": contract.source_record_id,
        "synced_at": contract.synced_at.isoformat(),
    }


def _sales_row(record: SalesRecord) -> dict:
    return {
        "id": str(record.id),
        "project_name": record.project_name,
        "po_number": record.po_number,
        "region": record.region,
        "product_type": record.product_type,
        "total_amount_usd": _number(record.total_amount_usd),
        "allocation_date": _date(record.allocation_date),
        "expiry_date": _date(record.expiry_date),
        "order_type": record.order_type,
        "status": record.status,
        "sales_person": record.sales_person,
        **owner_payload_from_record(record, "sales_person"),
        "source_record_id": record.source_record_id,
        "synced_at": record.synced_at.isoformat(),
    }


def get_contract_filter_options_data() -> dict:
    fields = [
        "sales_person",
        "order_platform",
        "status",
        "customer_name",
        "signing_entity",
        "channel_type",
        "enduser_customer",
        "region",
        "product_category",
        "signing_type",
        "currency",
    ]
    payload = {}
    for field in fields:
        values = (
            Contract.objects.exclude(**{field: ""})
            .values_list(field, flat=True)
            .distinct()
            .order_by(field)
        )
        key = "platform" if field == "order_platform" else field
        payload[key] = list(values)
    return payload


def list_contracts_data(params: dict[str, Any]) -> list[dict]:
    queryset = _apply_contract_filters(
        Contract.objects.order_by("-synced_at"),
        params,
    )
    return [
        _contract_row(item)
        for item in _page_queryset(
            queryset,
            params.get("page", 1),
            params.get("page_size", 50),
        )
    ]


def count_contracts_data(params: dict[str, Any]) -> dict:
    queryset = _apply_contract_filters(Contract.objects.all(), params)
    return {"total": queryset.count()}


def list_sales_records_data(params: dict[str, Any]) -> list[dict]:
    queryset = _apply_sales_filters(
        SalesRecord.objects.order_by("-synced_at"),
        params,
    )
    return [
        _sales_row(item)
        for item in _page_queryset(
            queryset,
            params.get("page", 1),
            params.get("page_size", 50),
        )
    ]


def count_sales_records_data(params: dict[str, Any]) -> dict:
    queryset = _apply_sales_filters(SalesRecord.objects.all(), params)
    return {"total": queryset.count()}


def list_sales_persons_data() -> dict:
    values = (
        Contract.objects.exclude(sales_person="")
        .values_list("sales_person", flat=True)
        .distinct()
        .order_by("sales_person")
    )
    return {"sales_persons": list(values)}


def get_contract_history_data(
    contract_id: str,
    *,
    limit: int,
    offset: int,
) -> dict:
    try:
        contract = Contract.objects.get(id=contract_id)
    except Contract.DoesNotExist as exc:
        raise Http404("合同不存在") from exc
    queryset = ContractHistory.objects.filter(contract=contract).order_by(
        "-changed_at",
    )
    safe_limit = min(max(_safe_int(limit, 100), 1), 500)
    safe_offset = max(_safe_int(offset, 0), 0)
    entries = queryset[safe_offset : safe_offset + safe_limit]
    return {
        "contract_id": str(contract.id),
        "total": queryset.count(),
        "entries": [
            {
                "id": str(item.id),
                "field_name": item.field_name,
                "old_value": item.old_value,
                "new_value": item.new_value,
                "changed_by": item.changed_by,
                "changed_at": item.changed_at.isoformat(),
                "change_type": item.change_type,
            }
            for item in entries
        ],
    }


def _project_card(project: Project) -> dict:
    display_amount, display_currency = _project_display_amount_currency(
        project,
    )
    return {
        "id": str(project.id),
        "project_scope": project.project_scope,
        "project_name": project.project_name,
        "project_code": project.project_code,
        "domestic_type": project.domestic_type,
        "customer_full_name": project.customer_full_name,
        "sales_person": project.sales_person,
        **owner_payload_from_record(project, "sales_person"),
        "estimated_amount": _number(project.estimated_amount),
        "total_amount": _number(project.total_amount),
        "payment_amount": _number(project.payment_amount),
        "currency": normalize_currency(project.currency),
        "payment_currency": normalize_currency(
            project.payment_currency or project.currency
        ),
        "display_amount": display_amount,
        "display_currency": display_currency,
        "oa_initiation_date": _date(project.oa_initiation_date),
        "is_high_potential": project.is_high_potential,
        "country": project.country,
        "status": project.status,
        "po_number": project.po_number,
        "signing_customer": project.signing_customer,
        "end_customer": project.end_customer,
        "project_owner": project.project_owner,
        **owner_payload_from_record(project, "project_owner"),
        "product_type": project.product_type,
        "order_type": project.order_type,
        "order_status": project.order_status,
        "acceptance_status": project.acceptance_status,
        "license_expiry": _date(project.license_expiry),
        "stat_amount_usd": _number(project.stat_amount_usd),
        "license_days_left": project.license_days_left,
        "license_risk_level": project.license_risk_level,
        "source_record_id": project.source_record_id,
    }


def _project_display_amount_currency(project: Project) -> tuple[float, str]:
    """Return the source-table amount and currency used for display."""

    candidates = [
        (project.payment_amount, project.payment_currency or project.currency),
        (project.total_amount, project.currency),
        (project.estimated_amount, project.currency),
        (project.stat_amount_usd, "USD"),
    ]
    for amount, currency in candidates:
        value = _number(amount)
        if value:
            return value, normalize_currency(currency)
    return 0.0, normalize_currency(
        project.currency or project.payment_currency
    )


def _project_amounts_by_currency(queryset) -> list[dict]:
    buckets: dict[str, float] = {}
    for project in queryset:
        amount, currency = _project_display_amount_currency(project)
        if not amount:
            continue
        key = normalize_currency(currency)
        buckets[key] = buckets.get(key, 0.0) + amount
    return [
        {"currency": currency, "amount": amount}
        for currency, amount in sorted(buckets.items())
    ]


def get_pipeline_projects_data(
    *,
    scope: str,
    include_landed: bool,
) -> dict:
    queryset = Project.objects.order_by("-synced_at")
    if scope == ProjectScope.DOMESTIC:
        queryset = queryset.filter(project_scope=ProjectScope.DOMESTIC)
    elif scope == ProjectScope.OVERSEAS:
        queryset = queryset.filter(project_scope=ProjectScope.OVERSEAS)
        if not include_landed:
            queryset = queryset.none()
    elif not include_landed:
        queryset = queryset.filter(project_scope=ProjectScope.DOMESTIC)
    cards = [_project_card(item) for item in queryset]
    return {"cards": cards, "total": len(cards)}


def get_pipeline_ledgers_data() -> dict:
    rows = DomesticLedger.objects.filter(
        ledger_type="收入",
        outstanding__gt=0,
    ).order_by("expected_payment_date")
    cards = [
        {
            "id": str(item.id),
            "customer_name": item.customer_name,
            "project_name": item.project_name,
            "sales_person": item.sales_person,
            **owner_payload_from_record(item, "sales_person"),
            "outstanding": _number(item.outstanding),
            "currency": normalize_currency(item.currency),
            "expected_payment_date": _date(item.expected_payment_date),
            "is_overdue": _is_overdue(item.expected_payment_date),
            "overdue_days": _overdue_days(item.expected_payment_date),
        }
        for item in rows
    ]
    return {"cards": cards, "total": len(cards)}


def get_pipeline_summary_data() -> dict:
    today = timezone.localdate()
    deadline_30 = today + timedelta(days=30)
    domestic_rows = Project.objects.filter(project_scope=ProjectScope.DOMESTIC)
    overseas_rows = Project.objects.filter(project_scope=ProjectScope.OVERSEAS)
    domestic_amounts = _project_amounts_by_currency(domestic_rows)
    overseas_amounts = _project_amounts_by_currency(overseas_rows)
    at_risk = Contract.objects.filter(
        service_end__isnull=False,
        service_end__lte=deadline_30,
    ).exclude(status__in=["已终止", "已归档"]).count()
    at_risk += overseas_rows.filter(
        license_expiry__isnull=False,
        license_expiry__lte=deadline_30,
    ).count()
    at_risk += DomesticLedger.objects.filter(
        ledger_type="收入",
        outstanding__gt=0,
        expected_payment_date__lt=today,
    ).count()
    return {
        "total_projects": domestic_rows.count() + overseas_rows.count(),
        "domestic_projects": domestic_rows.count(),
        "oversea_projects": overseas_rows.count(),
        "domestic_amount": _number(
            domestic_rows.aggregate(
                value=Coalesce(Sum("estimated_amount"), ZERO_DECIMAL),
            )["value"],
        ),
        "domestic_amount_by_currency": domestic_amounts,
        "oversea_amount_usd": _number(
            overseas_rows.aggregate(
                value=Coalesce(Sum("stat_amount_usd"), ZERO_DECIMAL),
            )["value"],
        ),
        "oversea_amount_by_currency": overseas_amounts,
        "high_potential": Project.objects.filter(
            is_high_potential=True,
        ).count(),
        "at_risk": at_risk,
    }


def get_pipeline_insights_data() -> dict:
    today = timezone.localdate()
    return {
        "high_potential_domestic": Project.objects.filter(
            project_scope=ProjectScope.DOMESTIC,
            is_high_potential=True,
        ).count(),
        "high_potential_overseas": Project.objects.filter(
            project_scope=ProjectScope.OVERSEAS,
            is_high_potential=True,
        ).count(),
        "upcoming_renewals": _upcoming_renewals(today, 30),
        "license_expiry_upcoming": _license_alerts(today, 60),
        "overdue_ledgers": get_pipeline_ledgers_data()["cards"],
        "settlement_receivable_trend": _settlement_trend(),
    }


def get_insights_data() -> dict:
    return {
        "monthly_signings": _monthly_amounts(
            Contract.objects.exclude(signing_date__isnull=True),
            "signing_date",
            "total_amount",
            currency_field="currency",
        ),
        "order_type_distribution": _distribution_amount(
            Contract,
            "signing_type",
            "total_amount",
            "type",
        ),
        "region_top10": _top_amounts(
            Contract,
            "region",
            "total_amount",
            "region",
            10,
        ),
        "upcoming_renewals": _upcoming_renewals(timezone.localdate(), 90),
        "contract_status_distribution": _count_distribution(
            Contract,
            "status",
            "status",
        ),
        "payment_status_distribution": _distribution_amount(
            DomesticLedger.objects.filter(ledger_type="收入"),
            "payment_status",
            "payment_received",
            "status",
        ),
        "monthly_payment_trend": _monthly_payment_trend(),
        "monthly_net_trend": _monthly_net_trend(),
        "oversea_projects_by_country_top10": _top_amounts(
            OverseaProject,
            "country",
            "stat_amount_usd",
            "country",
            10,
            amount_key="total_amount_usd",
            count_key="project_count",
        ),
        "oversea_projects_by_product_type": _top_amounts(
            OverseaProject,
            "product_type",
            "stat_amount_usd",
            "product_type",
            50,
            amount_key="total_amount_usd",
        ),
        "monthly_oversea_trend": _monthly_oversea_trend(),
        "license_expiry_upcoming": _license_alerts(timezone.localdate(), 60),
        "settlement_receivable_trend": _settlement_trend(),
        "settlement_by_project_category": _top_amounts(
            OverseaSettlement,
            "project_category",
            "actual_revenue",
            "category",
            50,
            amount_key="actual_revenue",
        ),
    }


def get_executive_briefing_data() -> dict:
    summary = get_pipeline_summary_data()
    today = timezone.localdate()
    renewals = _upcoming_renewals(today, 30)
    licenses = _license_alerts(today, 60)
    overdue = get_pipeline_ledgers_data()["cards"]
    return {
        "generated_at": timezone.now().isoformat(),
        "headline": "经营数据简报",
        "sections": [
            {
                "key": "pipeline",
                "title": "Pipeline",
                "primary_metric": {
                    "label": "项目总数",
                    "value": summary["total_projects"],
                    "unit": "个",
                },
                "summary": (
                    f"国内 {summary['domestic_projects']} 个，"
                    f"海外 {summary['oversea_projects']} 个。"
                ),
            },
            {
                "key": "risk",
                "title": "风险预警",
                "primary_metric": {
                    "label": "风险项",
                    "value": summary["at_risk"],
                    "unit": "项",
                },
                "summary": (
                    f"合同到期 {len(renewals)} 项，"
                    f"License 到期 {len(licenses)} 项，"
                    f"逾期回款 {len(overdue)} 项。"
                ),
            },
        ],
        "actions": [
            "检查飞书同步状态，确认权限和记录数完整。",
            "优先跟进 30 天内合同到期和逾期回款项目。",
        ],
    }


def get_oversea_settlement_kanban_data(params: dict[str, Any]) -> dict:
    queryset = OverseaSettlement.objects.order_by("payment_date")
    for key in ("region", "project_category", "huawei_settlement_party"):
        values = _split_multi(params.get(key))
        if values:
            queryset = queryset.filter(**{f"{key}__in": values})
    cards = [
        {
            "id": str(item.id),
            "project_name_cn": item.project_name_cn,
            "project_name_en": item.project_name_en,
            "region": item.region,
            "project_category": item.project_category,
            "project_progress": item.project_progress,
            "actual_revenue": _number(item.actual_revenue),
            "receivable_amount": _number(item.receivable_amount),
            "received_amount": _number(item.received_amount),
            "currency": normalize_currency(item.currency),
            "huawei_est_payment_time": item.huawei_est_payment_time,
            "payment_date": _date(item.payment_date),
            "huawei_settlement_party": item.huawei_settlement_party,
        }
        for item in queryset
    ]
    return {
        "cards": cards,
        "total": len(cards),
        "groups": _group_cards(cards, "project_progress", "actual_revenue"),
        "filters": {
            "region": _distinct(OverseaSettlement, "region"),
            "project_category": _distinct(
                OverseaSettlement,
                "project_category",
            ),
            "huawei_settlement_party": _distinct(
                OverseaSettlement,
                "huawei_settlement_party",
            ),
        },
    }


def list_domestic_ledgers_data(params: dict[str, Any]) -> list[dict]:
    queryset = DomesticLedger.objects.order_by("-synced_at")
    if params.get("ledger_type"):
        queryset = queryset.filter(ledger_type=params["ledger_type"])
    return [
        {
            "id": str(item.id),
            "ledger_type": item.ledger_type,
            "customer_name": item.customer_name,
            "project_name": item.project_name,
            "sales_person": item.sales_person,
            **owner_payload_from_record(item, "sales_person"),
            "currency": normalize_currency(item.currency),
            "total_contract_amount": _number(item.total_contract_amount),
            "payment_received": _number(item.payment_received),
            "payment_amount": _number(item.payment_amount),
            "outstanding": _number(item.outstanding),
            "payment_status": item.payment_status,
            "expected_payment_date": _date(item.expected_payment_date),
        }
        for item in queryset[:500]
    ]


def list_oversea_projects_data() -> list[dict]:
    return [
        {
            "id": str(item.id),
            "project_name": item.project_name,
            "po_number": item.po_number,
            "country": item.country,
            "stat_amount_usd": _number(item.stat_amount_usd),
            "license_expiry": _date(item.license_expiry),
            "project_owner": item.project_owner,
            **owner_payload_from_record(item, "project_owner"),
            "order_type": item.order_type,
            "product_type": item.product_type,
            "sales_person": item.project_owner,
            "order_status": item.order_status,
            "acceptance_status": item.acceptance_status,
        }
        for item in OverseaProject.objects.order_by("-synced_at")[:500]
    ]


def list_project_inits_data() -> list[dict]:
    return [
        {
            "id": str(item.id),
            "project_code": item.project_code,
            "project_name": item.project_name,
            "customer_full_name": item.customer_full_name,
            "sales_person": item.sales_person,
            **owner_payload_from_record(item, "sales_person"),
            "domestic_international": item.domestic_international,
            "estimated_amount": _number(item.estimated_amount),
            "currency": normalize_currency(item.currency),
            "oa_initiation_date": _date(item.oa_initiation_date),
        }
        for item in ProjectInit.objects.order_by("-synced_at")[:500]
    ]


def contract_export_rows() -> list[dict]:
    return [
        {
            "合同编号": item.contract_number,
            "合同对方": item.customer_name,
            "签约主体": item.signing_entity,
            "销售渠道": item.channel_type,
            "终端客户": item.enduser_customer,
            "订单平台": item.order_platform,
            "负责人": item.sales_person,
            **owner_payload_from_record(item, "sales_person"),
            "地区": item.region,
            "币种": normalize_currency(item.currency),
            "合同金额": _number(item.total_amount),
            "产品大类": item.product_category,
            "合同类型": item.signing_type,
            "签订日期": _date(item.signing_date) or "",
            "服务开始": _date(item.service_start) or "",
            "服务到期": _date(item.service_end) or "",
            "状态": item.status,
        }
        for item in Contract.objects.order_by("-synced_at")
    ]


def sales_export_rows() -> list[dict]:
    return [
        {
            "项目名称": item.project_name,
            "PO编号": item.po_number,
            "国家地区": item.region,
            "产品类型": item.product_type,
            "合计金额(USD)": _number(item.total_amount_usd),
            "分配时间": _date(item.allocation_date) or "",
            "到期时间": _date(item.expiry_date) or "",
            "订单类型": item.order_type,
            "项目状态": item.status,
            "负责人": item.sales_person,
            **owner_payload_from_record(item, "sales_person"),
        }
        for item in SalesRecord.objects.order_by("-synced_at")
    ]


def summary_export_rows() -> list[dict]:
    summary = get_pipeline_summary_data()
    return [
        {"指标": "项目总数", "数值": summary["total_projects"]},
        {"指标": "国内项目数", "数值": summary["domestic_projects"]},
        {"指标": "海外项目数", "数值": summary["oversea_projects"]},
        {"指标": "国内预估金额", "数值": summary["domestic_amount"]},
        {
            "指标": "海外统计金额 USD",
            "数值": summary["oversea_amount_usd"],
        },
        {"指标": "高潜项目", "数值": summary["high_potential"]},
        {"指标": "风险预警", "数值": summary["at_risk"]},
    ]


def _distinct(model, field_name: str) -> list[str]:
    values = (
        model.objects.exclude(**{field_name: ""})
        .values_list(field_name, flat=True)
        .distinct()
        .order_by(field_name)
    )
    return list(values)


def _is_overdue(value) -> bool:
    return bool(value and value < timezone.localdate())


def _overdue_days(value) -> int:
    if not value:
        return 0
    return max((timezone.localdate() - value).days, 0)


def _upcoming_renewals(today, days: int) -> list[dict]:
    deadline = today + timedelta(days=days)
    rows = Contract.objects.filter(
        service_end__isnull=False,
        service_end__gte=today,
        service_end__lte=deadline,
    ).exclude(status__in=["已终止", "已归档"]).order_by("service_end")
    return [
        {
            "customer_name": item.customer_name or "-",
            "customer": item.customer_name or "-",
            "contract_number": item.contract_number,
            "service_end": _date(item.service_end),
            "days_left": (item.service_end - today).days,
            "sales_person": item.sales_person,
            **owner_payload_from_record(item, "sales_person"),
        }
        for item in rows[:100]
    ]


def _license_alerts(today, days: int) -> list[dict]:
    deadline = today + timedelta(days=days)
    rows = Project.objects.filter(
        project_scope=ProjectScope.OVERSEAS,
        license_expiry__isnull=False,
        license_expiry__lte=deadline,
    ).order_by("license_expiry")
    return [
        {
            "project_name": item.project_name,
            "country": item.country,
            "license_expiry": _date(item.license_expiry),
            "days_left": item.license_days_left
            if item.license_days_left is not None
            else (item.license_expiry - today).days,
            "project_owner": item.project_owner,
            **owner_payload_from_record(item, "project_owner"),
        }
        for item in rows[:100]
    ]


def _settlement_trend() -> list[dict]:
    """Return receivable/received totals bucketed by currency and month.

    Overseas settlements can mix currencies. Keep month + currency buckets
    separate so charts do not add unrelated monetary units together.
    """

    rows = (
        OverseaSettlement.objects.exclude(payment_date__isnull=True)
        .annotate(month=TruncMonth("payment_date"))
        .values("month", "currency")
        .annotate(
            receivable_amount=Coalesce(
                Sum("receivable_amount"),
                ZERO_DECIMAL,
            ),
            received_amount=Coalesce(
                Sum("received_amount"),
                ZERO_DECIMAL,
            ),
        )
        .order_by("month", "currency")
    )
    grouped: dict[tuple[str, str], dict] = {}
    for item in rows:
        month = item["month"].strftime("%Y-%m") if item["month"] else ""
        currency = normalize_currency(item["currency"])
        bucket = grouped.setdefault(
            (month, currency),
            {
                "month": month,
                "currency": currency,
                "receivable_amount": 0.0,
                "received_amount": 0.0,
            },
        )
        bucket["receivable_amount"] += _number(item["receivable_amount"])
        bucket["received_amount"] += _number(item["received_amount"])
    buckets = sorted(
        grouped.values(),
        key=lambda item: (item["month"], item["currency"]),
    )
    return buckets[-36:]


def _monthly_amounts(
    queryset,
    date_field: str,
    amount_field: str,
    *,
    currency_field: str = "",
) -> list[dict]:
    values = ["month"]
    if currency_field:
        values.append(currency_field)
    rows = (
        queryset.annotate(month=TruncMonth(date_field))
        .values(*values)
        .annotate(amount=Coalesce(Sum(amount_field), ZERO_DECIMAL))
        .order_by("month")
    )
    buckets = {}
    for item in rows:
        month = item["month"].strftime("%Y-%m") if item["month"] else ""
        currency = normalize_currency(item.get(currency_field))
        key = (month, currency)
        buckets[key] = buckets.get(key, 0.0) + _number(item["amount"])
    return [
        {"month": month, "amount": amount, "currency": currency}
        for (month, currency), amount in sorted(buckets.items())
    ]


def _count_distribution(model_or_queryset, field_name: str, key: str):
    queryset = _as_queryset(model_or_queryset)
    rows = queryset.values(field_name).annotate(count=Count("id"))
    return [
        {key: item[field_name] or "未知", "count": int(item["count"] or 0)}
        for item in rows.order_by(field_name)
    ]


def _distribution_amount(
    model_or_queryset,
    field_name: str,
    amount_field: str,
    key: str,
) -> list[dict]:
    queryset = _as_queryset(model_or_queryset)
    rows = (
        queryset.values(field_name)
        .annotate(
            count=Count("id"),
            amount=Coalesce(Sum(amount_field), ZERO_DECIMAL),
        )
        .order_by(field_name)
    )
    amount_key = "total_amount" if key == "status" else "amount"
    return [
        {
            key: item[field_name] or "未知",
            "count": int(item["count"] or 0),
            amount_key: _number(item["amount"]),
        }
        for item in rows
    ]


def _top_amounts(
    model_or_queryset,
    field_name: str,
    amount_field: str,
    key: str,
    limit: int,
    *,
    amount_key: str = "amount",
    count_key: str = "count",
) -> list[dict]:
    queryset = _as_queryset(model_or_queryset)
    rows = (
        queryset.values(field_name)
        .annotate(
            count=Count("id"),
            amount=Coalesce(Sum(amount_field), ZERO_DECIMAL),
        )
        .order_by("-amount")[:limit]
    )
    return [
        {
            key: item[field_name] or "未知",
            count_key: int(item["count"] or 0),
            amount_key: _number(item["amount"]),
            "currency": "USD" if amount_key.endswith("usd") else "",
        }
        for item in rows
    ]


def _monthly_payment_trend() -> list[dict]:
    rows = (
        DomesticLedger.objects.filter(ledger_type="收入")
        .filter(
            Q(receipt_time__isnull=False)
            | Q(expected_payment_date__isnull=False)
        )
        .annotate(
            month=TruncMonth(
                Coalesce("receipt_time", "expected_payment_date"),
            )
        )
        .values("month", "currency")
        .annotate(
            payment_received=Coalesce(Sum("payment_received"), ZERO_DECIMAL),
            outstanding=Coalesce(Sum("outstanding"), ZERO_DECIMAL),
        )
        .order_by("month")
    )
    buckets = {}
    for item in rows:
        if not item["month"]:
            continue
        month = item["month"].strftime("%Y-%m")
        currency = normalize_currency(item["currency"])
        bucket = buckets.setdefault(
            (month, currency),
            {
                "month": month,
                "currency": currency,
                "payment_received": 0.0,
                "outstanding": 0.0,
            },
        )
        bucket["payment_received"] += _number(item["payment_received"])
        bucket["outstanding"] += _number(item["outstanding"])
    return [buckets[key] for key in sorted(buckets)]


def _monthly_net_trend() -> list[dict]:
    payment_rows = _monthly_payment_trend()
    expense_rows = _monthly_amounts(
        DomesticLedger.objects.filter(ledger_type="支出").exclude(
            signing_date__isnull=True,
        ),
        "signing_date",
        "payment_amount",
        currency_field="currency",
    )
    buckets = {}
    for item in payment_rows:
        key = (item["month"], item["currency"])
        buckets[key] = buckets.get(key, 0.0) + item["payment_received"]
    for item in expense_rows:
        key = (item["month"], item["currency"])
        buckets[key] = buckets.get(key, 0.0) - item["amount"]
    return [
        {"month": month, "currency": currency, "amount": amount}
        for (month, currency), amount in sorted(buckets.items())
    ]


def _monthly_oversea_trend() -> list[dict]:
    rows = (
        OverseaProject.objects.exclude(order_date__isnull=True)
        .annotate(month=TruncMonth("order_date"))
        .values("month")
        .annotate(
            new_projects=Count("id"),
            total_amount_usd=Coalesce(Sum("stat_amount_usd"), ZERO_DECIMAL),
        )
        .order_by("month")
    )
    return [
        {
            "month": item["month"].strftime("%Y-%m") if item["month"] else "",
            "new_projects": int(item["new_projects"] or 0),
            "total_amount_usd": _number(item["total_amount_usd"]),
        }
        for item in rows
    ]


def _group_cards(cards: list[dict], field_name: str, amount_field: str):
    grouped = {}
    for card in cards:
        key = card.get(field_name) or "未知"
        item = grouped.setdefault(key, {"count": 0, "amount": 0.0})
        item["count"] += 1
        item["amount"] += float(card.get(amount_field) or 0)
    return [
        {
            "status": key,
            "platforms": [
                {
                    "platform": "",
                    "contract_count": value["count"],
                    "total_amount": value["amount"],
                }
            ],
        }
        for key, value in sorted(grouped.items())
    ]


def _as_queryset(model_or_queryset):
    if hasattr(model_or_queryset, "objects"):
        return model_or_queryset.objects.all()
    return model_or_queryset
