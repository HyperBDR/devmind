import logging
import csv

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CollectionTask, DataSource, Host, License, Tenant
from .serializers import (
    CollectionTaskSerializer,
    DataSourceSerializer,
    HostSerializer,
    LicenseSerializer,
    TenantSerializer,
)
from .services import build_dashboard_stats
from .tasks import run_collection_for_data_source

logger = logging.getLogger(__name__)


def paginated_response(items, total, skip, limit):
    return {"items": items, "total": total, "skip": skip, "limit": limit}


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
            host_count=Count("hosts", distinct=True),
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
            host_count=Count("hosts", distinct=True),
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


class HostListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    TASK_STATUS_MAP = {
        "completed": ["sync_snapshot_done", "host_register_done", "boot_done", "clean_done"],
        "failed": ["sync_failed", "clean_failed", "boot_failed"],
        "processing": ["sync_doing", "clean_doing", "boot_doing", "sync_queued"],
    }
    HEALTH_SCOPE_MAP = {
        "risky": ["warning", "unhealthy", "disconnected"],
        "healthy": ["healthy", "active"],
    }
    HOST_STATUS_LABELS = {
        "sync_snapshot_done": "同步完成",
        "host_register_done": "注册完成",
        "sync_failed": "同步失败",
        "clean_failed": "清理失败",
        "clean_done": "清理完成",
        "sync_doing": "同步中",
        "clean_doing": "清理中",
        "sync_queued": "等待中",
        "sync_stopped": "已停止",
    }
    BOOT_STATUS_LABELS = {
        "boot_done": "已启动",
        "boot_failed": "启动失败",
        "boot_doing": "启动中",
        "stopped": "未启动",
        "running": "运行中",
    }
    HEALTH_STATUS_LABELS = {
        "healthy": "健康",
        "active": "健康",
        "warning": "告警",
        "unhealthy": "异常",
        "disconnected": "断连",
    }

    def _base_queryset(self):
        return Host.objects.select_related("tenant", "data_source")

    def _apply_host_filters(
        self,
        qs,
        request,
        *,
        include_name=True,
        include_status=True,
        include_task_status=True,
        include_health_scope=True,
        include_license_valid=True,
        include_has_error=True,
        include_tenant=True,
        include_data_source=True,
    ):
        if include_name and request.query_params.get("name"):
            qs = qs.filter(name__icontains=request.query_params["name"])
        if include_status and request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        if include_task_status:
            task_status = request.query_params.get("task_status")
            if task_status:
                statuses = self.TASK_STATUS_MAP.get(task_status, [])
                if statuses:
                    qs = qs.filter(status__in=statuses)
                else:
                    qs = qs.none()
        if include_health_scope:
            health_scope = request.query_params.get("health_scope")
            if health_scope:
                health_statuses = self.HEALTH_SCOPE_MAP.get(health_scope, [])
                if health_statuses:
                    qs = qs.filter(health_status__in=health_statuses)
                else:
                    qs = qs.none()
        if include_license_valid:
            license_valid = request.query_params.get("license_valid")
            if license_valid in {"true", "false"}:
                qs = qs.filter(license_valid=(license_valid == "true"))
        if include_has_error:
            has_error = request.query_params.get("has_error")
            if has_error == "true":
                qs = qs.exclude(Q(error_message__isnull=True) | Q(error_message=""))
            elif has_error == "false":
                qs = qs.filter(Q(error_message__isnull=True) | Q(error_message=""))
        if include_tenant:
            tenant_id = request.query_params.get("tenant_id")
            if tenant_id:
                qs = qs.filter(tenant__source_tenant_id=tenant_id)
        if include_data_source:
            data_source_id = request.query_params.get("data_source_id")
            if data_source_id:
                qs = qs.filter(data_source_id=data_source_id)
        return qs

    def _summary_queryset(self, request):
        return self._apply_host_filters(
            self._base_queryset(),
            request,
            include_name=False,
            include_status=False,
            include_task_status=False,
            include_health_scope=False,
            include_license_valid=False,
            include_has_error=False,
        )

    def _format_datetime(self, value):
        if not value:
            return ""
        return timezone.localtime(value).strftime("%Y-%m-%d %H:%M:%S")

    def _host_status_label(self, value):
        return self.HOST_STATUS_LABELS.get(str(value or "").lower(), value or "-")

    def _boot_status_label(self, value):
        return self.BOOT_STATUS_LABELS.get(str(value or "").lower(), value or "-")

    def _health_status_label(self, value):
        return self.HEALTH_STATUS_LABELS.get(str(value or "").lower(), value or "-")

    def _license_label(self, value):
        return "有效" if value else "无效"

    def get(self, request):
        skip = int(request.query_params.get("skip", 0))
        limit = int(request.query_params.get("limit", 100))
        qs = self._apply_host_filters(self._base_queryset(), request)
        summary_qs = self._summary_queryset(request)
        total = qs.count()
        payload = paginated_response(
            HostSerializer(qs.order_by("tenant__name", "name")[skip: skip + limit], many=True).data,
            total,
            skip,
            limit,
        )
        payload["summary"] = {
            "total": summary_qs.count(),
            "healthy": summary_qs.filter(health_status__in=self.HEALTH_SCOPE_MAP["healthy"]).count(),
            "error": summary_qs.exclude(Q(error_message__isnull=True) | Q(error_message="")).count(),
            "invalid_license": summary_qs.filter(license_valid=False).count(),
        }
        return Response(payload)


class HostExportAPIView(HostListAPIView):
    permission_classes = [IsAuthenticated]

    def _export_queryset(self, request):
        scope = request.query_params.get("scope", "filtered")
        data_source_id = request.query_params.get("data_source_id")
        if scope == "data_source_all" and data_source_id:
            return self._apply_host_filters(
                self._base_queryset(),
                request,
                include_name=False,
                include_status=False,
                include_task_status=False,
                include_health_scope=False,
                include_license_valid=False,
                include_has_error=False,
                include_tenant=False,
            )
        return self._apply_host_filters(self._base_queryset(), request)

    def _filename(self, request):
        scope = request.query_params.get("scope", "filtered")
        if scope == "data_source_all" and request.query_params.get("data_source_id"):
            scope_label = "all"
        else:
            scope_label = "filtered"
        data_source_id = request.query_params.get("data_source_id") or "all-sources"
        timestamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
        return f"onepro-hosts-{scope_label}-{data_source_id}-{timestamp}.csv"

    def get(self, request):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{self._filename(request)}"'
        response.write("\ufeff")

        writer = csv.writer(response)
        writer.writerow(
            [
                "主机名称",
                "主机ID",
                "数据源",
                "租户",
                "主机状态",
                "启动状态",
                "健康状态",
                "操作系统",
                "主机类型",
                "CPU",
                "RAM(GB)",
                "授权状态",
                "错误摘要",
                "最后采集时间",
            ]
        )

        queryset = self._export_queryset(request).order_by("tenant__name", "name")
        for host in queryset.iterator(chunk_size=500):
            writer.writerow(
                [
                    host.name or "",
                    host.source_host_id or "",
                    getattr(host.data_source, "name", "") or "",
                    getattr(host.tenant, "name", "") or "",
                    self._host_status_label(host.status),
                    self._boot_status_label(host.boot_status),
                    self._health_status_label(host.health_status),
                    host.os_type or "",
                    host.host_type or "",
                    host.cpu_num or 0,
                    host.ram_size or 0,
                    self._license_label(host.license_valid),
                    host.error_message or "",
                    self._format_datetime(host.last_collected_at),
                ]
            )

        return response


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


class HostPerformanceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data_source_id = request.query_params.get("data_source_id")
        payload = build_dashboard_stats(data_source_id=data_source_id)
        return Response(payload["host"])


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
            logger.warning("OnePro monitor health database check failed: %s", exc)
        return Response(
            {
                "status": "healthy" if db_status == "healthy" else "degraded",
                "components": {"api": "healthy", "database": db_status, "scheduler": "managed-by-celery"},
                "service": "onepro-monitor",
                "version": "1.0.0",
            }
        )
