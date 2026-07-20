import csv
import io
import json
from datetime import timedelta

from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasRequiredFeature

from .models import (
    DataOpsGlobalConfig,
    Observation,
    SyncCursor,
    SyncJob,
    SyncStatus,
    SyncTableStatus,
)
from .permissions import HasDataOpsAdminAccess
from .serializers import (
    DataOpsGlobalConfigSerializer,
    FeishuBitableCollectionConfigSerializer,
    KnowledgeProductionRunCreateSerializer,
    KnowledgeProductionRunSerializer,
    ObservationFilterSerializer,
    ObservationSerializer,
    SyncCursorSerializer,
    SyncJobSerializer,
    SyncTriggerSerializer,
    SyncTableStatusSerializer,
)
from .services.ai import (
    chat_with_data_ops_assistant,
    get_ai_context_metrics,
    stream_chat_with_data_ops_assistant,
)
from .services.feishu.client import (
    FeishuBitableClient,
    run_bitable_access_check,
)
from .services.feishu.config import (
    discover_bitable_table_ids,
    get_bitable_collection_config,
    list_bitable_collection_configs,
    mark_config_manual_trigger,
    mark_config_preflight,
)
from .services.feishu.global_config import get_active_sync_job_timeout_hours
from .services.feishu.mappings import ACTIVE_SOURCE_KEYS
from .services.knowledge.contract_renewal import (
    produce_contract_renewal_observations,
)
from .services.metrics.overview import (
    get_contract_cards,
    get_contract_kanban,
    get_data_quality,
    get_domestic_ledger_kanban,
    get_executive_overview,
    get_opportunities,
    get_oversea_project_kanban,
    get_project_init_kanban,
    get_risks,
    get_summary,
    get_top_customers,
    get_top_sales,
    get_trends,
)
from .services.metrics.operations import (
    contract_export_rows,
    count_contracts_data,
    count_sales_records_data,
    get_contract_filter_options_data,
    get_contract_history_data,
    get_executive_briefing_data,
    get_insights_data,
    get_oversea_settlement_kanban_data,
    get_pipeline_insights_data,
    get_pipeline_ledgers_data,
    get_pipeline_projects_data,
    get_pipeline_summary_data,
    list_contracts_data,
    list_domestic_ledgers_data,
    list_oversea_projects_data,
    list_project_inits_data,
    list_sales_persons_data,
    list_sales_records_data,
    sales_export_rows,
    summary_export_rows,
)
from .tasks import (
    SyncTaskDispatchError,
    dispatch_sync_task,
    run_full_sync_task,
    run_incremental_sync_task,
    run_table_sync_task,
)


FEATURE_KEY = "data_ops"


class DataOpsPermissionMixin:
    """Require access to the Data Ops app."""

    permission_classes = [HasRequiredFeature]
    required_feature = FEATURE_KEY


class DataOpsAdminPermissionMixin:
    """Require elevated Data Ops access for sensitive operations."""

    permission_classes = [HasDataOpsAdminAccess]


class ObservationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ObservationListAPIView(DataOpsPermissionMixin, APIView):
    """List traceable observations with stable, validated filters."""

    def get(self, request):
        filters = ObservationFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        queryset = (
            Observation.objects.select_related("run")
            .prefetch_related("evidence_links__evidence")
            .order_by("-generated_at", "-id")
        )
        for field, value in filters.validated_data.items():
            queryset = queryset.filter(**{field: value})

        paginator = ObservationPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = ObservationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ObservationDetailAPIView(DataOpsPermissionMixin, APIView):
    """Return one observation and its current supporting evidence."""

    def get(self, request, observation_id):
        queryset = Observation.objects.select_related("run").prefetch_related(
            "evidence_links__evidence",
        )
        observation = get_object_or_404(queryset, id=observation_id)
        return Response(ObservationSerializer(observation).data)


class ObservationRunCreateAPIView(DataOpsAdminPermissionMixin, APIView):
    """Create a deterministic knowledge production run."""

    def post(self, request):
        serializer = KnowledgeProductionRunCreateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        run = produce_contract_renewal_observations()
        return Response(
            KnowledgeProductionRunSerializer(run).data,
            status=status.HTTP_201_CREATED,
        )


class DataOpsGlobalConfigAPIView(DataOpsAdminPermissionMixin, APIView):
    def get(self, request):
        config = DataOpsGlobalConfig.get_solo()
        return Response(DataOpsGlobalConfigSerializer(config).data)

    def patch(self, request):
        config = DataOpsGlobalConfig.get_solo()
        serializer = DataOpsGlobalConfigSerializer(
            config,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class SyncStatusAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        table_statuses = SyncTableStatus.objects.order_by(
            "source_key",
            "table_key",
        )
        cursors = SyncCursor.objects.order_by("source_key", "table_key")
        jobs = SyncJob.objects.order_by("-started_at")[:10]
        status_values = list(table_statuses.values_list("status", flat=True))
        has_failed = "failed" in status_values
        has_warning = "warning" in status_values
        overall_status = "ok"
        if has_failed:
            overall_status = "failed"
        elif has_warning:
            overall_status = "warning"

        return Response(
            {
                "overall_status": overall_status,
                "tables": SyncTableStatusSerializer(
                    table_statuses,
                    many=True,
                ).data,
                "cursors": SyncCursorSerializer(cursors, many=True).data,
                "recent_jobs": SyncJobSerializer(jobs, many=True).data,
            }
        )


class FeishuPreflightAPIView(DataOpsAdminPermissionMixin, APIView):
    def post(self, request):
        client = FeishuBitableClient()
        discovery = discover_bitable_table_ids(client=client)
        statuses = run_bitable_access_check(client=client)
        has_failed = any(item.status == "failed" for item in statuses)
        has_warning = any(item.status == "warning" for item in statuses)
        overall_status = "ok"
        if has_failed:
            overall_status = "failed"
        elif has_warning:
            overall_status = "warning"

        return Response(
            {
                "overall_status": overall_status,
                "discovery": discovery,
                "tables": SyncTableStatusSerializer(statuses, many=True).data,
            }
        )


class FeishuCollectionConfigListAPIView(DataOpsAdminPermissionMixin, APIView):
    def get(self, request):
        configs = list_bitable_collection_configs()
        return Response(
            FeishuBitableCollectionConfigSerializer(
                configs,
                many=True,
            ).data
        )


class FeishuCollectionConfigDetailAPIView(
    DataOpsAdminPermissionMixin,
    APIView,
):
    def patch(self, request, config_id):
        config = get_bitable_collection_config(config_id)
        serializer = FeishuBitableCollectionConfigSerializer(
            config,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class FeishuCollectionConfigPreflightAPIView(
    DataOpsAdminPermissionMixin,
    APIView,
):
    def post(self, request, config_id):
        config = get_bitable_collection_config(config_id)
        client = FeishuBitableClient()
        discovery = discover_bitable_table_ids(
            client=client,
            source_key=config.source_key,
            table_key=config.table_key,
        )
        statuses = run_bitable_access_check(
            source_key=config.source_key,
            table_key=config.table_key,
            client=client,
        )
        mark_config_preflight(config)
        return Response(
            {
                "discovery": discovery,
                "tables": SyncTableStatusSerializer(statuses, many=True).data,
                "config": FeishuBitableCollectionConfigSerializer(
                    get_bitable_collection_config(config_id),
                ).data,
            }
        )


class FeishuCollectionConfigTriggerAPIView(
    DataOpsAdminPermissionMixin,
    APIView,
):
    def post(self, request, config_id):
        config = get_bitable_collection_config(config_id)
        if not config.is_enabled:
            return Response(
                {
                    "detail": (
                        "该采集配置已停用，"
                        "启用后才能手动触发。"
                    )
                },
                status=400,
            )
        job = SyncJob.objects.create(
            source_key=config.source_key,
            table_key=config.table_key,
            status=SyncStatus.PENDING,
        )
        try:
            dispatch_sync_task(
                run_table_sync_task,
                job,
                source_key=config.source_key,
                table_key=config.table_key,
                job_id=str(job.id),
            )
        except SyncTaskDispatchError:
            return _dispatch_failed_response(job)
        mark_config_manual_trigger(config)
        return Response(SyncJobSerializer(job).data, status=202)


class TriggerFullSyncAPIView(DataOpsAdminPermissionMixin, APIView):
    def post(self, request):
        serializer = SyncTriggerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        force = serializer.validated_data["force"]
        active_since = timezone.now() - timedelta(
            hours=get_active_sync_job_timeout_hours(),
        )
        active_job = (
            SyncJob.objects.filter(
                source_key="",
                table_key="",
                status__in=[SyncStatus.PENDING, SyncStatus.RUNNING],
                started_at__gte=active_since,
            )
            .order_by("-started_at")
            .first()
        )
        if active_job:
            data = dict(SyncJobSerializer(active_job).data)
            data["deduplicated"] = True
            return Response(data, status=202)
        job = SyncJob.objects.create(
            source_key="",
            status=SyncStatus.PENDING,
        )
        try:
            dispatch_sync_task(
                run_full_sync_task,
                job,
                job_id=str(job.id),
                force=force,
            )
        except SyncTaskDispatchError:
            return _dispatch_failed_response(job)
        return Response(SyncJobSerializer(job).data, status=202)


class TriggerIncrementalSyncAPIView(DataOpsAdminPermissionMixin, APIView):
    def post(self, request):
        source_key = str(request.data.get("source_key") or "").strip()
        allowed = set(ACTIVE_SOURCE_KEYS)
        if source_key not in allowed:
            return Response(
                {
                    "detail": (
                        "未知或未启用的数据源，source_key 可选值："
                        f"{', '.join(sorted(allowed))}。"
                    )
                },
                status=400,
            )
        job = SyncJob.objects.create(
            source_key=source_key,
            status="pending",
        )
        try:
            dispatch_sync_task(
                run_incremental_sync_task,
                job,
                source_key=source_key,
                job_id=str(job.id),
            )
        except SyncTaskDispatchError:
            return _dispatch_failed_response(job)
        return Response(SyncJobSerializer(job).data, status=202)


class SummaryAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_summary())


class ExecutiveOverviewAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_executive_overview())


class ExecutiveBriefingAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_executive_briefing_data())


class ExecutiveDataQualityAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_data_quality())


class ExecutiveTrendsAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_trends())


class ExecutiveTopCustomersAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_top_customers())


class ExecutiveTopSalesAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_top_sales())


class ExecutiveRisksAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_risks())


class ExecutiveOpportunitiesAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_opportunities())


class ContractKanbanAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_contract_kanban())


class ContractKanbanCardsAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_contract_cards())


class ProjectInitKanbanAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_project_init_kanban())


class OverseaProjectKanbanAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_oversea_project_kanban())


class DomesticLedgerKanbanAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_domestic_ledger_kanban())


class OverseaSettlementKanbanAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(
            get_oversea_settlement_kanban_data(request.query_params)
        )


class ContractListAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(list_contracts_data(request.query_params))


class ContractCountAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(count_contracts_data(request.query_params))


class ContractFilterOptionsAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_contract_filter_options_data())


class ContractHistoryAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request, contract_id):
        return Response(
            get_contract_history_data(
                contract_id,
                limit=request.query_params.get("limit", 100),
                offset=request.query_params.get("offset", 0),
            )
        )


class SalesRecordListAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(list_sales_records_data(request.query_params))


class SalesRecordCountAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(count_sales_records_data(request.query_params))


class SalesPersonListAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(list_sales_persons_data())


class InsightsAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_insights_data())


class PipelineProjectsAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        include_landed = str(
            request.query_params.get("include_landed", "true"),
        ).lower()
        return Response(
            get_pipeline_projects_data(
                scope=request.query_params.get("scope", "all"),
                include_landed=include_landed not in {"false", "0", "no"},
            )
        )


class PipelineDomesticLedgersAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_pipeline_ledgers_data())


class PipelineInsightsAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_pipeline_insights_data())


class PipelineSummaryAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_pipeline_summary_data())


class DomesticLedgerListAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(list_domestic_ledgers_data(request.query_params))


class OverseaProjectListAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(list_oversea_projects_data())


class ProjectInitListAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(list_project_inits_data())


class ExportContractsAPIView(DataOpsAdminPermissionMixin, APIView):
    def get(self, request):
        return _csv_response(contract_export_rows(), "contracts.csv")


class ExportSalesRecordsAPIView(DataOpsAdminPermissionMixin, APIView):
    def get(self, request):
        return _csv_response(sales_export_rows(), "sales_records.csv")


class ExportSummaryAPIView(DataOpsAdminPermissionMixin, APIView):
    def get(self, request):
        return _csv_response(summary_export_rows(), "summary.csv")


class AIContextAPIView(DataOpsPermissionMixin, APIView):
    def get(self, request):
        return Response(get_ai_context_metrics())


class LLMChatAPIView(DataOpsPermissionMixin, APIView):
    def post(self, request):
        message = str(request.data.get("message") or "").strip()
        if not message:
            return Response({"detail": "message is required"}, status=400)
        result = chat_with_data_ops_assistant(
            message=message,
            history=request.data.get("history") or [],
            preferred_config_uuid=str(
                request.data.get("llm_config_uuid") or ""
            ).strip(),
            user_id=getattr(request.user, "id", None),
        )
        return Response({"reply": result["reply"], "llm": result["llm"]})


class LLMChatStreamAPIView(DataOpsPermissionMixin, APIView):
    def post(self, request):
        message = str(request.data.get("message") or "").strip()
        if not message:
            return Response({"detail": "message is required"}, status=400)

        def event_stream():
            events = stream_chat_with_data_ops_assistant(
                message=message,
                history=request.data.get("history") or [],
                preferred_config_uuid=str(
                    request.data.get("llm_config_uuid") or ""
                ).strip(),
                user_id=getattr(request.user, "id", None),
            )
            for event in events:
                payload = json.dumps(event, ensure_ascii=False, default=str)
                yield f"data: {payload}\n\n"

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class LLMQueryAPIView(DataOpsPermissionMixin, APIView):
    def post(self, request):
        question = str(
            request.data.get("question") or request.data.get("message") or ""
        ).strip()
        if not question:
            return Response({"detail": "question is required"}, status=400)
        result = chat_with_data_ops_assistant(
            message=question,
            history=request.data.get("history") or [],
            preferred_config_uuid=str(
                request.data.get("llm_config_uuid") or ""
            ).strip(),
            user_id=getattr(request.user, "id", None),
        )
        return Response(
            {
                "data": {
                    "answer": result["answer"],
                    "sql": None,
                    "rows": [result["context"]],
                    "llm": result["llm"],
                }
            }
        )


def _csv_response(rows: list[dict], filename: str) -> HttpResponse:
    output = io.StringIO()
    if rows:
        fieldnames = list(
            dict.fromkeys(key for row in rows for key in row.keys())
        )
        safe_rows = [
            {key: _escape_csv_cell(value) for key, value in row.items()}
            for row in rows
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(safe_rows)
    response = HttpResponse(
        "\ufeff" + output.getvalue(),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _escape_csv_cell(value):
    """Prevent spreadsheet applications from evaluating untrusted formulas."""
    formula_prefixes = ("=", "+", "-", "@")
    if isinstance(value, str) and value.lstrip().startswith(formula_prefixes):
        return f"'{value}"
    return value


def _dispatch_failed_response(job: SyncJob) -> Response:
    return Response(
        {
            "detail": "同步任务投递失败，请检查 Celery broker/worker 状态。",
            "job": SyncJobSerializer(job).data,
        },
        status=503,
    )
