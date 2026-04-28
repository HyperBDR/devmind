import logging

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CollectionTask, DataSource, License, Tenant
from .serializers import (
    CollectionTaskSerializer,
    DataSourceSerializer,
    LicenseSerializer,
    TenantSerializer,
)
from . import services as dashboard_services
from .services.analyzer import build_dashboard_stats
from .tasks import run_collection_for_data_source
from accounts.access import get_effective_feature_keys

logger = logging.getLogger(__name__)


def paginated_response(items, total, skip, limit):
    return {"items": items, "total": total, "skip": skip, "limit": limit}


FEATURE_KEY = "hyperbdr_dashboard"


def _check_feature_permission(user):
    features = get_effective_feature_keys(user)
    if FEATURE_KEY not in features:
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied("You do not have access to the HyperMotion / HyperBDR Dashboard.")


class OverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["hyperbdr-dashboard"], summary="Dashboard Overview")
    def get(self, request):
        _check_feature_permission(request.user)
        customer_type = request.query_params.get("customer_type", "all")
        if customer_type not in ("all", "real", "test"):
            customer_type = "all"
        payload = dashboard_services.build_hyperbdr_dashboard_overview(
            year=int(request.query_params.get("year", 0)) or None,
            month=int(request.query_params.get("month", 0)) or None,
            customer_type=customer_type,
        )
        return Response(payload)


class TrendsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["hyperbdr-dashboard"], summary="Dashboard Trends")
    def get(self, request):
        _check_feature_permission(request.user)
        days = int(request.query_params.get("days", 30))
        days = max(1, min(days, 365))
        return Response(dashboard_services.build_hyperbdr_dashboard_trends(days=days))


class MonthlyTrendsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["hyperbdr-dashboard"], summary="Dashboard Monthly Trends")
    def get(self, request):
        _check_feature_permission(request.user)
        year_param = request.query_params.get("year", "all")
        year = None if year_param == "all" else (int(year_param) if year_param.isdigit() else None)
        customer_type = request.query_params.get("customer_type", "all")
        if customer_type not in ("all", "real", "test"):
            customer_type = "all"
        return Response(dashboard_services.build_hyperbdr_dashboard_monthly_trends(year=year, customer_type=customer_type))


class TenantsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["hyperbdr-dashboard"], summary="Dashboard Tenants")
    def get(self, request):
        _check_feature_permission(request.user)
        all_tenants = dashboard_services.build_hyperbdr_dashboard_tenants()
        total = len(all_tenants)
        skip = int(request.query_params.get("skip", 0))
        limit = int(request.query_params.get("limit", 100))
        return Response({
            "items": all_tenants[skip: skip + limit],
            "total": total,
            "skip": skip,
            "limit": limit,
        })


class DataSourceListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        skip = int(request.query_params.get("skip", 0))
        limit = int(request.query_params.get("limit", 100))
        qs = DataSource.objects.all().order_by("name", "id")
        total = qs.count()
        serializer = DataSourceSerializer(
            qs[skip: skip + limit],
            many=True,
            context={"request": request},
        )
        return Response(paginated_response(serializer.data, total, skip, limit))

    def post(self, request):
        payload = request.data.copy()
        if "url" in payload and "api_url" not in payload:
            payload["api_url"] = payload["url"]
        serializer = DataSourceSerializer(data=payload, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DataSourceDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, data_source_id):
        return DataSource.objects.get(pk=data_source_id)

    def get(self, request, data_source_id):
        serializer = DataSourceSerializer(
            self.get_object(data_source_id),
            context={"request": request, "include_password": True},
        )
        return Response(serializer.data)

    def put(self, request, data_source_id):
        payload = request.data.copy()
        if "url" in payload and "api_url" not in payload:
            payload["api_url"] = payload["url"]
        serializer = DataSourceSerializer(
            self.get_object(data_source_id),
            data=payload,
            partial=False,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request, data_source_id):
        serializer = DataSourceSerializer(
            self.get_object(data_source_id),
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, data_source_id):
        self.get_object(data_source_id).delete()
        return Response({"success": True})


class DataSourceCollectAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, data_source_id):
        data_source = DataSource.objects.get(pk=data_source_id)
        task = CollectionTask.objects.create(
            data_source=data_source,
            status=CollectionTask.STATUS_PENDING,
            start_time=timezone.now(),
            trigger_mode="manual",
        )
        celery_task = run_collection_for_data_source.delay(data_source.id, task.id, "manual")
        task.celery_task_id = celery_task.id
        task.save(update_fields=["celery_task_id", "updated_at"])
        return Response(
            {
                "success": True,
                "task_id": task.id,
                "celery_task_id": celery_task.id,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class TenantListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        skip = int(request.query_params.get("skip", 0))
        limit = int(request.query_params.get("limit", 100))
        qs = Tenant.objects.select_related("data_source")
        name = request.query_params.get("name")
        data_source_id = request.query_params.get("data_source_id")
        if name:
            qs = qs.filter(name__icontains=name)
        if data_source_id:
            qs = qs.filter(data_source_id=data_source_id)
        qs = qs.annotate(
            license_total=Coalesce(Sum("licenses__total_amount"), 0),
            license_used=Coalesce(Sum("licenses__total_used"), 0),
            license_remaining=Coalesce(Sum("licenses__total_unused"), 0),
        )
        total = qs.count()
        serializer = TenantSerializer(qs.order_by("name")[skip: skip + limit], many=True)
        return Response(paginated_response(serializer.data, total, skip, limit))


class TenantDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, tenant_id):
        qs = Tenant.objects.select_related("data_source").annotate(
            license_total=Coalesce(Sum("licenses__total_amount"), 0),
            license_used=Coalesce(Sum("licenses__total_used"), 0),
            license_remaining=Coalesce(Sum("licenses__total_unused"), 0),
        )
        tenant = qs.get(source_tenant_id=tenant_id)
        return Response(TenantSerializer(tenant).data)


class LicenseListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        skip = int(request.query_params.get("skip", 0))
        limit = int(request.query_params.get("limit", 100))
        qs = License.objects.select_related("tenant", "data_source")
        type_value = request.query_params.get("type")
        tenant_id = request.query_params.get("tenant_id")
        data_source_id = request.query_params.get("data_source_id")
        status_filter = request.query_params.get("status")
        if type_value:
            qs = qs.filter(scene=type_value)
        if tenant_id:
            qs = qs.filter(tenant__source_tenant_id=tenant_id)
        if data_source_id:
            qs = qs.filter(data_source_id=data_source_id)
        if status_filter == "available":
            qs = qs.filter(total_unused__gt=0)
        elif status_filter == "exhausted":
            qs = qs.filter(total_unused__lte=0)
        total = qs.count()
        serializer = LicenseSerializer(qs.order_by("tenant__name", "scene")[skip: skip + limit], many=True)
        return Response(paginated_response(serializer.data, total, skip, limit))


class CollectionTaskListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        skip = int(request.query_params.get("skip", 0))
        limit = int(request.query_params.get("limit", 100))
        qs = CollectionTask.objects.select_related("data_source")
        status_value = request.query_params.get("status")
        data_source_id = request.query_params.get("data_source_id")
        if status_value:
            qs = qs.filter(status=status_value)
        if data_source_id:
            qs = qs.filter(data_source_id=data_source_id)
        total = qs.count()
        serializer = CollectionTaskSerializer(qs.order_by("-start_time")[skip: skip + limit], many=True)
        return Response(paginated_response(serializer.data, total, skip, limit))


class CollectionTaskDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        task = CollectionTask.objects.select_related("data_source").get(pk=task_id)
        return Response(CollectionTaskSerializer(task).data)


class TriggerCollectionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data_source_id = request.data.get("data_source_id") or request.query_params.get("data_source_id")
        if data_source_id:
            targets = [DataSource.objects.get(pk=data_source_id)]
        else:
            targets = list(DataSource.objects.filter(is_active=True))
        scheduled = []
        for source in targets:
            task = CollectionTask.objects.create(
                data_source=source,
                status=CollectionTask.STATUS_PENDING,
                start_time=timezone.now(),
                trigger_mode="manual",
            )
            celery_task = run_collection_for_data_source.delay(source.id, task.id, "manual")
            task.celery_task_id = celery_task.id
            task.save(update_fields=["celery_task_id", "updated_at"])
            scheduled.append({"task_id": task.id, "data_source_id": source.id, "celery_task_id": celery_task.id})
        return Response({"success": True, "scheduled": scheduled}, status=status.HTTP_202_ACCEPTED)


class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data_source_id = request.query_params.get("data_source_id")
        if data_source_id in {"", "all", None}:
            data_source_id = None
        return Response(build_dashboard_stats(data_source_id=data_source_id))


class TenantStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data_source_id = request.query_params.get("data_source_id")
        payload = build_dashboard_stats(data_source_id=data_source_id)
        return Response(payload["tenant"])


class LicenseUsageAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data_source_id = request.query_params.get("data_source_id")
        payload = build_dashboard_stats(data_source_id=data_source_id)
        return Response(payload["license"])


class TaskExecutionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data_source_id = request.query_params.get("data_source_id")
        days = int(request.query_params.get("days", 7))
        payload = build_dashboard_stats(data_source_id=data_source_id, days=days)
        return Response(payload["task"])


class HealthAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            DataSource.objects.exists()
            db_status = "healthy"
        except Exception as exc:
            db_status = "unhealthy"
            logger.warning("HyperBDR monitor health database check failed: %s", exc)
        return Response(
            {
                "status": "healthy" if db_status == "healthy" else "degraded",
                "components": {"api": "healthy", "database": db_status, "scheduler": "managed-by-celery"},
                "service": "hyperbdr-monitor",
                "version": "1.0.0",
            }
        )
