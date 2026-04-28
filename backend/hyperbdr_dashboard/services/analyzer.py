from datetime import timedelta

from django.db.models import Avg, Count, DecimalField, IntegerField, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from ..models import CollectionTask, License, Tenant


def _dict_from_rows(rows, key="status", value="count"):
    return {row[key] or "unknown": row[value] for row in rows}


def build_dashboard_stats(data_source_id=None, days=7):
    tenant_qs = Tenant.objects.all()
    license_qs = License.objects.all()
    task_qs = CollectionTask.objects.all()

    if data_source_id:
        tenant_qs = tenant_qs.filter(data_source_id=data_source_id)
        license_qs = license_qs.filter(data_source_id=data_source_id)
        task_qs = task_qs.filter(data_source_id=data_source_id)

    task_qs = task_qs.filter(start_time__gte=timezone.now() - timedelta(days=days))

    tenant_total = tenant_qs.count()
    tenant_stats = _dict_from_rows(
        tenant_qs.values("status").annotate(count=Count("id")).order_by("status")
    )

    license_agg = license_qs.aggregate(
        total_amount=Coalesce(Sum("total_amount"), 0, output_field=IntegerField()),
        total_used=Coalesce(Sum("total_used"), 0, output_field=IntegerField()),
        total_unused=Coalesce(Sum("total_unused"), 0, output_field=IntegerField()),
        total=Count("id"),
    )
    usage_ratio = 0
    if license_agg["total_amount"]:
        usage_ratio = round((license_agg["total_used"] / license_agg["total_amount"]) * 100, 2)

    task_status_stats = _dict_from_rows(
        task_qs.values("status").annotate(count=Count("id")).order_by("status")
    )
    task_avg = task_qs.exclude(duration_seconds__isnull=True).aggregate(
        avg_duration=Coalesce(
            Avg("duration_seconds"),
            0,
            output_field=DecimalField(max_digits=10, decimal_places=2),
        ),
        total=Count("id"),
    )

    return {
        "tenant": {
            "total": tenant_total,
            "status_stats": tenant_stats,
            "active": tenant_stats.get("active", 0) + tenant_stats.get("activated", 0),
            "disabled": tenant_stats.get("disabled", 0),
        },
        "license": {
            **license_agg,
            "usage_ratio": usage_ratio,
            "scene_stats": _dict_from_rows(
                license_qs.values("scene").annotate(count=Count("id")).order_by("scene"),
                key="scene",
            ),
        },
        "task": {
            "total": task_avg["total"],
            "status_stats": task_status_stats,
            "avg_duration": round(float(task_avg["avg_duration"] or 0), 2),
        },
    }
