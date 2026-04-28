"""
Dashboard aggregation service for the HyperBDR Data Operations Dashboard.

This module builds the dashboard payload from hyperbdr_dashboard models,
reshaping the data into the product-facing dashboard contract.

Business rules:
- expiring soon:           remaining_days <= 30
- PoC expiring soon:      is_poc and remaining_days <= 7
- high-potential:          is_poc and utilization >= 60% and remaining_days <= 30
- low activity:            utilization < 30% and total_amount > 0
- conversion_rate:        official_count / (poc_count + official_count)

Tenant classification:
- PoC: any license has remaining_days <= 1
- official: otherwise
"""

from calendar import monthrange
from collections import defaultdict
from datetime import date

from django.db.models import Count, IntegerField, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from ..models import License, Tenant


def _get_license_remaining_days(lic: dict) -> int | None:
    """
    Return remaining days for a single license.
    Returns None if no expire_at or license is expired.
    """
    expire_at = lic.get("expire_at")
    if expire_at is None:
        return None
    delta = expire_at - timezone.now()
    return delta.days


def _is_test_tenant(tenant: Tenant, licenses: list[dict]) -> bool:
    """
    Return True if the tenant is a test user based on license count and expiration.

    Test user criteria (ALL must be true):
    - License count <= 3
    - ALL licenses have remaining_days <= 14

    Otherwise -> real user.
    """
    if not licenses:
        # No license -> real user
        return False

    if len(licenses) > 3:
        # More than 3 licenses -> real user
        return False

    # Check all licenses have remaining_days <= 14
    for lic in licenses:
        remaining = _get_license_remaining_days(lic)
        if remaining is None or remaining > 14:
            return False

    return True


def _prefetch_licenses(tenants):
    """
    Return a dict mapping tenant_id -> list of license dicts,
    prefetched in a single query to avoid N+1.
    """
    tenant_ids = [t.id for t in tenants]
    rows = License.objects.filter(
        tenant_id__in=tenant_ids,
        data_source__is_active=True,
    ).values(
        "tenant_id",
        "scene",
        "total_amount",
        "total_used",
        "expire_at",
        "start_at",
    )
    by_tenant = defaultdict(list)
    for row in rows:
        by_tenant[row["tenant_id"]].append(row)
    return by_tenant


def _classify_tenant(tenant: Tenant, licenses: list[dict]) -> dict:
    """
    Return tenant-level classification metadata.

    Classification logic:
    - If any license has remaining_days <= 1 -> PoC
    - Otherwise -> official
    """
    # Check if any license has remaining_days <= 1
    is_poc = False
    for lic in licenses:
        remaining = _get_license_remaining_days(lic)
        if remaining is not None and remaining <= 1:
            is_poc = True
            break

    tenant_type = "poc" if is_poc else "official"

    total_amount = sum(lic.get("total_amount") or 0 for lic in licenses)
    total_used = sum(lic.get("total_used") or 0 for lic in licenses)

    utilization = round((total_used / total_amount) * 100,
                        2) if total_amount > 0 else 0.0

    expire_dates = [
        lic.get("expire_at")
        for lic in licenses
        if lic.get("expire_at") is not None
    ]
    nearest_expire_at = min(expire_dates) if expire_dates else None

    remaining_days = None
    if nearest_expire_at:
        delta = nearest_expire_at - timezone.now()
        remaining_days = delta.days

    return {
        "tenant_type": tenant_type,
        "utilization": utilization,
        "remaining_days": remaining_days,
        "nearest_expire_at": nearest_expire_at,
        "total_amount": total_amount,
        "total_used": total_used,
    }


def _is_poc(tenant: Tenant, licenses: list[dict]) -> bool:
    return _classify_tenant(tenant, licenses)["tenant_type"] == "poc"


def _build_license_stats_summary() -> dict:
    """Return global license aggregates for the overview endpoint."""
    license_qs = License.objects.filter(data_source__is_active=True)
    base = license_qs.aggregate(
        total_amount=Coalesce(Sum("total_amount"), 0,
                              output_field=IntegerField()),
        total_used=Coalesce(Sum("total_used"), 0, output_field=IntegerField()),
        total_unused=Coalesce(Sum("total_unused"), 0,
                              output_field=IntegerField()),
        total=Count("id"),
    )
    total_amount = base["total_amount"] or 0
    total_used = base["total_used"] or 0
    usage_ratio = round((total_used / total_amount) * 100,
                        2) if total_amount > 0 else 0.0
    valid_amount = license_qs.filter(
        total_unused__gt=0, start_at__lte=timezone.now()
    ).aggregate(
        amount=Coalesce(Sum("total_amount"), 0, output_field=IntegerField())
    )["amount"] or 0
    exhausted_amount = license_qs.filter(
        total_unused__lte=0, start_at__lte=timezone.now()
    ).aggregate(
        amount=Coalesce(Sum("total_amount"), 0, output_field=IntegerField())
    )["amount"] or 0
    inactive_amount = license_qs.filter(
        start_at__gt=timezone.now()
    ).aggregate(
        amount=Coalesce(Sum("total_amount"), 0, output_field=IntegerField())
    )["amount"] or 0
    return {
        "total": base["total"] or 0,
        "total_amount": total_amount,
        "total_used": total_used,
        "total_unused": base["total_unused"] or 0,
        "usage_ratio": usage_ratio,
        "dr_count": license_qs.filter(scene="dr").count(),
        "migration_count": license_qs.filter(scene="migration").count(),
        "valid_amount": valid_amount,
        "exhausted_amount": exhausted_amount,
        "inactive_amount": inactive_amount,
    }


def _build_kpis_from_tenants(tenants: list, licenses_by_tenant: dict) -> list[dict]:
    poc_count = sum(1 for t in tenants if _is_poc(
        t, licenses_by_tenant.get(t.id, [])))
    official_count = len(tenants) - poc_count
    total = poc_count + official_count
    conversion_rate_val = round(
        (official_count / total) * 100, 2) if total > 0 else 0.0

    return [
        {
            "key": "totalTenants",
            "value": len(tenants),
            "trend": None,
            "progress": None,
            "progressLabelKey": None,
        },
        {
            "key": "pocTenants",
            "value": poc_count,
            "trend": None,
            "progress": None,
            "progressLabelKey": None,
        },
        {
            "key": "officialTenants",
            "value": official_count,
            "trend": None,
            "progress": None,
            "progressLabelKey": None,
        },
        {
            "key": "conversionRate",
            "value": f"{conversion_rate_val:.1f}%",
            "trend": f"+{conversion_rate_val:.1f}%",
            "progress": conversion_rate_val,
            "progressLabelKey": "hyperbdrDashboard.conversionRate",
        },
    ]


def _build_focus_cards_from_tenants(tenants: list, licenses_by_tenant: dict) -> list[dict]:
    """
    Focus card rules:
    - expiring soon:        remaining_days in [0, 30]
    - PoC expiring soon:   is_poc and remaining_days in [0, 7]
    - high-potential:       is_poc and utilization >= 60% and remaining_days in [0, 30]
    - low activity:         utilization < 30% and total_amount > 0

    PoC: any license has remaining_days <= 1
    """
    expiring = []
    poc_expiring = []
    high_potential = []
    low_activity = []

    for tenant in tenants:
        licenses = licenses_by_tenant.get(tenant.id, [])
        cls = _classify_tenant(tenant, licenses)
        rem = cls["remaining_days"]
        util = cls["utilization"]

        if rem is not None and 0 <= rem <= 30:
            expiring.append(tenant)
        if _is_poc(tenant, licenses) and rem is not None and 0 <= rem <= 7:
            poc_expiring.append(tenant)
        if _is_poc(tenant, licenses) and util >= 60 and rem is not None and 0 <= rem <= 30:
            high_potential.append(tenant)
        if util < 30 and cls["total_amount"] > 0:
            low_activity.append(tenant)

    def _sort_by_auth(tenant_list):
        """Sort tenants by total_authorization descending."""
        def get_auth(t):
            licenses = licenses_by_tenant.get(t.id, [])
            return sum(lic.get("total_amount") or 0 for lic in licenses)
        return sorted(tenant_list, key=get_auth, reverse=True)

    cards = [
        {
            "key": "expiring_soon",
            "labelKey": "hyperbdrDashboard.expiringSoon",
            "descriptionKey": "hyperbdrDashboard.expiringSoonDesc",
            "count": len(expiring),
            "tenants": [{"id": t.source_tenant_id, "name": t.name} for t in _sort_by_auth(expiring)[:5]],
        },
        {
            "key": "high_potential",
            "labelKey": "hyperbdrDashboard.highPotential",
            "descriptionKey": "hyperbdrDashboard.highPotentialDesc",
            "count": len(high_potential),
            "tenants": [{"id": t.source_tenant_id, "name": t.name} for t in _sort_by_auth(high_potential)[:5]],
        },
        {
            "key": "poc_expiring",
            "labelKey": "hyperbdrDashboard.pocExpiring",
            "descriptionKey": "hyperbdrDashboard.pocExpiringDesc",
            "count": len(poc_expiring),
            "tenants": [{"id": t.source_tenant_id, "name": t.name} for t in _sort_by_auth(poc_expiring)[:5]],
        },
        {
            "key": "low_activity",
            "labelKey": "hyperbdrDashboard.lowActivity",
            "descriptionKey": "hyperbdrDashboard.lowActivityDesc",
            "count": len(low_activity),
            "tenants": [{"id": t.source_tenant_id, "name": t.name} for t in _sort_by_auth(low_activity)[:5]],
        },
    ]

    return cards


def _build_distribution_from_tenants(tenants: list, licenses_by_tenant: dict) -> dict:
    """PoC vs official breakdown with utilization distribution."""
    poc_count = sum(1 for t in tenants if _is_poc(
        t, licenses_by_tenant.get(t.id, [])))
    official_count = len(tenants) - poc_count
    total = poc_count + official_count

    utilization_buckets = {
        "0-30%": 0,
        "30-60%": 0,
        "60-90%": 0,
        "90-100%": 0,
        "100%+": 0,
    }
    for tenant in tenants:
        licenses = licenses_by_tenant.get(tenant.id, [])
        cls = _classify_tenant(tenant, licenses)
        util = cls["utilization"]
        if util < 30:
            utilization_buckets["0-30%"] += 1
        elif util < 60:
            utilization_buckets["30-60%"] += 1
        elif util < 90:
            utilization_buckets["60-90%"] += 1
        elif util <= 100:
            utilization_buckets["90-100%"] += 1
        else:
            utilization_buckets["100%+"] += 1

    return {
        "poc_count": poc_count,
        "official_count": official_count,
        "total": total,
        "poc_percentage": round((poc_count / total) * 100, 2) if total > 0 else 0.0,
        "official_percentage": round((official_count / total) * 100, 2) if total > 0 else 0.0,
        "utilization_buckets": utilization_buckets,
    }


def _build_funnel_from_tenants(tenants: list, licenses_by_tenant: dict) -> dict:
    """
    Conversion funnel: total -> trialed (PoC) -> converted (official).
    """
    poc_count = sum(1 for t in tenants if _is_poc(
        t, licenses_by_tenant.get(t.id, [])))
    official_count = len(tenants) - poc_count
    total = poc_count + official_count

    return {
        "total": total,
        "poc": poc_count,
        "official": official_count,
        "conversion_rate": round((official_count / total) * 100, 2) if total > 0 else 0.0,
    }


def _build_tenant_rows_from_tenants(tenants: list, licenses_by_tenant: dict) -> list[dict]:
    """
    Tenant operations table rows with all key metrics.
    """

    def _compute_conversion_cycle_days(licenses: list[dict]) -> int | None:
        """Compute days from PoC expiration to official start for one tenant."""
        poc_expire_ats = [
            lic.get("expire_at")
            for lic in licenses
            if lic.get("scene") in ("dr", "", None) and lic.get("expire_at")
        ]
        official_start_ats = [
            lic.get("start_at")
            for lic in licenses
            if lic.get("scene") not in ("dr", "", None) and lic.get("start_at")
        ]
        if not poc_expire_ats or not official_start_ats:
            return None

        poc_end = max(poc_expire_ats)
        official_start = min(official_start_ats)
        days = (official_start.date() - poc_end.date()).days
        return days if days >= 0 else None

    rows = []
    for tenant in tenants:
        licenses = licenses_by_tenant.get(tenant.id, [])
        cls = _classify_tenant(tenant, licenses)
        conversion_cycle_days = _compute_conversion_cycle_days(licenses)

        scenes = list({lic.get("scene") or "" for lic in licenses})
        scene_display = ", ".join(scenes) if scenes else "-"
        rows.append({
            "id": tenant.source_tenant_id,
            "name": tenant.name,
            "description": tenant.description,
            "status": tenant.status or "-",
            "scenario": scene_display,
            "tenant_type": cls["tenant_type"],
            "total_authorization": cls["total_amount"],
            "used_authorization": cls["total_used"],
            "utilization": cls["utilization"],
            "remaining_days": cls["remaining_days"],
            "expire_at": (
                cls["nearest_expire_at"].isoformat()
                if cls["nearest_expire_at"]
                else None
            ),
            "agent_enabled": tenant.agent_enabled,
            "trialed": tenant.trialed,
            "migration_way": tenant.migration_way or "-",
            "data_source": tenant.data_source.name,
            "conversion_cycle_days": conversion_cycle_days,
        })

    return rows


def build_hyperbdr_dashboard_overview(
    year: int | None = None,
    month: int | None = None,
    customer_type: str = "all",
) -> dict:
    """
    Build the complete HyperBDR dashboard overview payload.

    Args:
        year: filter to a specific year (e.g. 2026)
        month: filter to a specific month (1-12), requires year
        customer_type: filter tenant scope - "all", "real" (exclude test accounts),
                      or "test" (only test accounts)

    Returns:
        dict with keys: kpis, focus_cards, distribution, funnel, tenant_table
    """
    period_start, period_end = _compute_period_range(year, month)

    base_qs = Tenant.objects.filter(data_source__is_active=True)
    all_tenants = list(base_qs.select_related("data_source").order_by("name"))

    # Prefetch licenses for customer_type filtering
    licenses_for_filter = _prefetch_licenses(all_tenants)

    # Apply customer_type filter
    if customer_type == "real":
        all_tenants = [t for t in all_tenants if not _is_test_tenant(t, licenses_for_filter.get(t.id, []))]
    elif customer_type == "test":
        all_tenants = [t for t in all_tenants if _is_test_tenant(t, licenses_for_filter.get(t.id, []))]

    if year is not None and period_start and period_end:
        period_tenant_ids = set(
            License.objects.filter(
                data_source__is_active=True,
                expire_at__gte=period_start,
                expire_at__lte=period_end,
            ).values_list("tenant_id", flat=True)
        )
        filtered_tenants = [
            t for t in all_tenants if t.id in period_tenant_ids]
    else:
        filtered_tenants = all_tenants

    licenses_by_tenant = _prefetch_licenses(filtered_tenants)

    license_stats = _build_license_stats_summary()

    return {
        "kpis": _build_kpis_from_tenants(filtered_tenants, licenses_by_tenant),
        "license_stats": license_stats,
        "focus_cards": _build_focus_cards_from_tenants(
            filtered_tenants, licenses_by_tenant
        ),
        "distribution": _build_distribution_from_tenants(
            filtered_tenants, licenses_by_tenant
        ),
        "funnel": _build_funnel_from_tenants(filtered_tenants, licenses_by_tenant),
        "tenant_table": _build_tenant_rows_from_tenants(
            filtered_tenants, licenses_by_tenant
        ),
    }


def _compute_period_range(year: int | None, month: int | None):
    """Return (period_start, period_end) date tuple for filtering."""
    today = timezone.now().date()
    if year is None:
        return None, None
    if month:
        _, last_day = monthrange(year, month)
        period_start = date(year, month, 1)
        period_end = min(date(year, month, last_day), today)
    else:
        period_start = date(year, 1, 1)
        period_end = min(date(year, 12, 31), today)
    return period_start, period_end


def build_hyperbdr_dashboard_monthly_trends(year: int | None = None, customer_type: str = "all") -> dict:
    """
    Return monthly tenant growth and conversion trends (cumulative).

    Groups tenants by their source system created_at month.
    Filters by customer_type (real/test/all) based on license count <= 3 AND all remaining_days <= 14.
    Each month shows the cumulative count from the start up to that month.
    """
    today = timezone.now().date()

    if year is not None:
        start_date = date(year, 1, 1)
        end_date = min(date(year, 12, 31), today)
    else:
        months_ago_11 = date(today.year, today.month, 1)
        for _ in range(11):
            if months_ago_11.month == 1:
                months_ago_11 = date(months_ago_11.year - 1, 12, 1)
            else:
                months_ago_11 = date(months_ago_11.year,
                                     months_ago_11.month - 1, 1)
        start_date = months_ago_11
        end_date = today

    month_keys = []
    current = date(start_date.year, start_date.month, 1)
    end = date(end_date.year, end_date.month, 1)
    while current <= end:
        month_keys.append((current.year, current.month))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    all_tenants = list(Tenant.objects.filter(data_source__is_active=True))
    licenses_all = _prefetch_licenses(all_tenants)

    # Apply customer_type filter
    if customer_type == "real":
        all_tenants = [t for t in all_tenants if not _is_test_tenant(t, licenses_all.get(t.id, []))]
    elif customer_type == "test":
        all_tenants = [t for t in all_tenants if _is_test_tenant(t, licenses_all.get(t.id, []))]
    counts_by_month = defaultdict(int)
    official_by_month = defaultdict(int)
    churned_by_month = defaultdict(set)
    for tenant in all_tenants:
        created = tenant.created_at
        if created is None:
            created = tenant.last_collected_at
        if created is None:
            continue
        created_date = created.date()
        if start_date <= created_date <= end_date:
            key = (created_date.year, created_date.month)
            counts_by_month[key] += 1
            if not _is_poc(tenant, licenses_all.get(tenant.id, [])):
                official_by_month[key] += 1

        for lic in licenses_all.get(tenant.id, []):
            scene = lic.get("scene")
            expire_at = lic.get("expire_at")
            if scene in ("dr", "", None) or expire_at is None:
                continue
            expire_date = expire_at.date()
            if start_date <= expire_date <= end_date and expire_date <= today:
                churned_by_month[(expire_date.year, expire_date.month)].add(
                    tenant.id)

    cumulative = 0
    official_cumulative = 0
    prev_cumulative = 0
    months = []
    for key in month_keys:
        monthly_count = counts_by_month.get(key, 0)
        monthly_official = official_by_month.get(key, 0)
        cumulative += monthly_count
        official_cumulative += monthly_official
        conv_rate = round((official_cumulative / cumulative)
                          * 100, 2) if cumulative > 0 else 0.0
        churned_count = len(churned_by_month.get(key, set()))
        net_growth = monthly_count - churned_count
        growth_rate = round((net_growth / prev_cumulative) * 100, 2) if prev_cumulative > 0 else 0.0
        months.append({
            "year": key[0],
            "month": key[1],
            "label": f"{key[0]}-{key[1]:02d}",
            "total_tenants": cumulative,
            "new_tenants": monthly_count,
            "churned_tenants": churned_count,
            "net_growth": net_growth,
            "growth_rate": growth_rate,
            "total_licenses": 0,
            "total_hosts": 0,
            "conversion_rate": conv_rate,
        })
        prev_cumulative = cumulative

    poc_total = sum(1 for t in all_tenants if _is_poc(
        t, licenses_all.get(t.id, [])))
    official_total = len(all_tenants) - poc_total
    total = poc_total + official_total
    global_conv_rate = round((official_total / total)
                             * 100, 2) if total > 0 else 0.0

    return {
        "period_year": year,
        "months": months,
        "conversion_rate": global_conv_rate,
        "snapshot_at": timezone.now().isoformat(),
    }


def build_hyperbdr_dashboard_trends(days: int = 30) -> dict:
    """
    Return a simple trend view based on current snapshot data.

    For V1, this returns static distribution data since we don't have
    longitudinal history. Future versions can query CollectionTask records
    over time for a proper trend chart.
    """
    tenants_for_dist = list(Tenant.objects.filter(data_source__is_active=True))
    licenses_for_dist = _prefetch_licenses(tenants_for_dist)
    dist = _build_distribution_from_tenants(
        tenants_for_dist, licenses_for_dist)
    return {
        "period_days": days,
        "snapshot_at": timezone.now().isoformat(),
        "current": dist,
        "conversion_rate": dist.get("conversion_rate", 0.0),
    }


def build_hyperbdr_dashboard_tenants() -> list[dict]:
    """Return the tenant table rows for direct API access."""
    tenants = (
        Tenant.objects.filter(data_source__is_active=True)
        .select_related("data_source")
        .order_by("name")
    )
    tenants_list = list(tenants)
    licenses_by_tenant = _prefetch_licenses(tenants_list)
    return _build_tenant_rows_from_tenants(tenants_list, licenses_by_tenant)
