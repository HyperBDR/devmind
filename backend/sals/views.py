"""
SALS API views.
"""
import logging
import re
from collections import Counter

from django.db.models import Avg, Count, Q, Sum, Case, When, Value, CharField, IntegerField, FloatField
from django.db.models.functions import Coalesce
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.access import get_effective_feature_keys
from core.paginations import APIPagination
from rest_framework.exceptions import PermissionDenied

from .models import Company, User, Incident
from .serializers import (
    CompanySerializer,
    IncidentSerializer,
    UserSerializer,
)
from .services import etl

logger = logging.getLogger(__name__)

FEATURE_KEY = "operations_console"


def _check_feature_permission(user):
    features = get_effective_feature_keys(user)
    if FEATURE_KEY not in features:
        raise PermissionDenied("You do not have access to the SALS Operations Console.")


class PingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="Health check")
    def get(self, request):
        return Response({"pong": True})


class KpiStatAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="KPI statistics")
    def get(self, request):
        _check_feature_permission(request.user)
        total = Incident.objects.count()
        pending = Incident.objects.filter(state="Pending").count()
        in_progress = Incident.objects.filter(state="In Progress").count()
        resolved = Incident.objects.filter(state="Resolved").count()
        closed = Incident.objects.filter(state="Closed").count()
        canceled = Incident.objects.filter(state="Canceled").count()

        avg_h = (
            Incident.objects.aggregate(avg=Avg("resolve_hours"))["avg"] or 0
        )

        sla_ok = Incident.objects.filter(is_sla_met=True).count()
        sla_rate = (sla_ok / total * 100) if total > 0 else 0

        p1_total = Incident.objects.filter(priority="P1").count()
        p1_overdue = Incident.objects.filter(
            priority="P1", resolve_hours__gt=4
        ).count()
        p2_total = Incident.objects.filter(priority="P2").count()

        resolved_total = resolved + closed
        resolved_rate = (resolved_total / total * 100) if total > 0 else 0

        return Response({
            "total": total,
            "pending": pending,
            "in_progress": in_progress,
            "resolved": resolved,
            "closed": closed,
            "canceled": canceled,
            "resolved_rate": round(resolved_rate, 2),
            "sla_rate": round(sla_rate, 2),
            "avg_resolve_hours": round(float(avg_h or 0), 2),
            "p1_total": p1_total,
            "p1_overdue": p1_overdue,
            "p2_total": p2_total,
        })


class PriorityDistAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="Priority distribution")
    def get(self, request):
        _check_feature_permission(request.user)
        rows = (
            Incident.objects.values("priority")
            .annotate(count=Count("id"))
            .order_by("priority")
        )
        return Response([
            {"priority": r["priority"] or "未知", "count": r["count"]}
            for r in rows
        ])


class StateDistAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="State distribution")
    def get(self, request):
        _check_feature_permission(request.user)
        rows = (
            Incident.objects.values("state")
            .annotate(count=Count("id"))
            .order_by("state")
        )
        return Response([
            {"state": r["state"] or "未知", "count": r["count"]}
            for r in rows
        ])


class MonthlyTrendAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="Monthly trend")
    def get(self, request):
        _check_feature_permission(request.user)
        rows = (
            Incident.objects.values("month")
            .annotate(
                total=Count("id"),
                avg_hours=Avg("resolve_hours"),
            )
            .exclude(month__isnull=True)
            .order_by("month")
        )
        return Response([
            {
                "month": r["month"],
                "total": r["total"],
                "avg_hours": round(float(r["avg_hours"] or 0), 2),
            }
            for r in rows
        ])


class GroupStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="Group statistics")
    def get(self, request):
        _check_feature_permission(request.user)
        rows = (
            Incident.objects.values("assignment_group")
            .annotate(
                count=Count("id"),
                avg_hours=Avg("resolve_hours"),
                resolved_count=Sum(
                    Case(
                        When(state__in=["Resolved", "Closed"], then=1),
                        default=0,
                        output_field=IntegerField(),
                    )
                ),
            )
            .order_by("assignment_group")
        )
        return Response([
            {
                "group": r["assignment_group"] or "未知",
                "count": r["count"],
                "avg_hours": round(float(r["avg_hours"] or 0), 2),
                "resolved_rate": round(
                    (r["count"] and r["resolved_count"] / r["count"] * 100) or 0, 1
                ),
            }
            for r in rows
        ])


class AssigneeStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["sals"],
        summary="Assignee statistics",
        parameters=[{"name": "limit", "in": "query", "schema": {"type": "integer", "default": 12}}],
    )
    def get(self, request):
        _check_feature_permission(request.user)
        limit = int(request.query_params.get("limit", 12))
        limit = max(1, min(limit, 50))
        rows = (
            Incident.objects.values("assigned_to")
            .filter(assigned_to__isnull=False)
            .annotate(
                count=Count("id"),
                avg_hours=Avg("resolve_hours"),
                pending_count=Sum(
                    Case(
                        When(
                            ~Q(state__in=["Resolved", "Closed", "Canceled"]),
                            then=1,
                        ),
                        default=0,
                        output_field=IntegerField(),
                    )
                ),
            )
            .order_by("-count")[:limit]
        )
        return Response([
            {
                "assignee": r["assigned_to"] or "未知",
                "count": r["count"],
                "avg_hours": round(float(r["avg_hours"] or 0), 2),
                "pending_count": r["pending_count"] or 0,
            }
            for r in rows
        ])


class CustomerStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["sals"],
        summary="Customer statistics",
        parameters=[{"name": "limit", "in": "query", "schema": {"type": "integer", "default": 15}}],
    )
    def get(self, request):
        _check_feature_permission(request.user)
        limit = int(request.query_params.get("limit", 15))
        limit = max(1, min(limit, 50))

        sub_rows = (
            Incident.objects.values("company", "category")
            .filter(company__isnull=False)
            .annotate(cnt=Count("id"))
            .all()
        )
        by_company: dict = {}
        for co, cat, cnt in [(r["company"], r["category"], r["cnt"]) for r in sub_rows]:
            if co not in by_company:
                by_company[co] = {"count": 0, "cat_cnt": {}}
            by_company[co]["count"] += cnt
            by_company[co]["cat_cnt"][cat or "未知"] = (
                by_company[co]["cat_cnt"].get(cat or "未知", 0) + cnt
            )

        rows = (
            Incident.objects.values("company")
            .filter(company__isnull=False)
            .annotate(
                count=Count("id"),
                resolved_count=Sum(
                    Case(
                        When(state__in=["Resolved", "Closed"], then=1),
                        default=0,
                        output_field=IntegerField(),
                    )
                ),
                avg_hours=Avg("resolve_hours"),
            )
            .order_by("-count")[:limit]
        )
        return Response([
            {
                "company": r["company"] or "未知",
                "count": r["count"],
                "resolved_count": r["resolved_count"] or 0,
                "resolve_rate": round(
                    (r["count"] and r["resolved_count"] / r["count"] * 100) or 0, 1
                ),
                "avg_hours": round(float(r["avg_hours"] or 0), 2),
                "category": (
                    max(
                        by_company.get(r["company"] or "", {}).get("cat_cnt", {}),
                        key=lambda k: by_company.get(r["company"] or "", {})
                        .get("cat_cnt", {})
                        .get(k, 0),
                    )
                    if by_company.get(r["company"] or "") else "未知"
                ) or "未知",
            }
            for r in rows
        ])


class ProductStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="Product statistics")
    def get(self, request):
        _check_feature_permission(request.user)
        rows = (
            Incident.objects.values("category")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        return Response([
            {"category": r["category"] or "未知", "count": r["count"]}
            for r in rows
        ])


class SlaStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="SLA statistics")
    def get(self, request):
        _check_feature_permission(request.user)
        rows = (
            Incident.objects.values("priority")
            .filter(priority__isnull=False)
            .annotate(
                count=Count("id"),
                sla_met=Sum(
                    Case(
                        When(is_sla_met=True, then=1),
                        default=0,
                        output_field=IntegerField(),
                    )
                ),
                avg_hours=Avg("resolve_hours"),
                sla_limit=Avg("sla_limit"),
            )
            .order_by("priority")
        )
        return Response([
            {
                "priority": r["priority"],
                "count": r["count"],
                "sla_met": r["sla_met"] or 0,
                "sla_rate": round(
                    (r["count"] and (r["sla_met"] or 0) / r["count"] * 100) or 0, 1
                ),
                "avg_hours": round(float(r["avg_hours"] or 0), 2),
                "sla_limit": float(r["sla_limit"] or 0),
            }
            for r in rows
        ])


class KeywordStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["sals"],
        summary="Keyword statistics",
        parameters=[{"name": "top", "in": "query", "schema": {"type": "integer", "default": 20}}],
    )
    def get(self, request):
        _check_feature_permission(request.user)
        top = int(request.query_params.get("top", 20))
        top = max(1, min(top, 100))

        stopwords = {
            "the", "a", "an", "and", "or", "to", "of", "in", "for", "on", "is",
            "it", "this", "that", "with", "as", "by", "be", "are", "was",
            "were", "has", "have", "had", "not", "but", "from", "at", "can",
            "will", "my", "nan", "null", "fw", "re", "ll", "ve", "s", "t",
            "m", "的", "了", "在", "是", "我", "你",
        }

        texts = (
            Incident.objects.values_list("short_description", flat=True)
            .exclude(short_description__isnull=True)
            .exclude(short_description="")
        )
        words = []
        for text in texts:
            w = re.findall(r"[a-zA-Z]{3,}", str(text).lower())
            words.extend(x for x in w if x not in stopwords)
        counter = Counter(words)
        return Response([
            {"keyword": k, "count": c}
            for k, c in counter.most_common(top)
        ])


class ProductStateMatrixAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="Product state matrix")
    def get(self, request):
        _check_feature_permission(request.user)
        rows = (
            Incident.objects.values("category", "state")
            .annotate(count=Count("id"))
            .all()
        )
        matrix = {}
        for r in rows:
            matrix.setdefault(r["category"] or "未知", {})[
                r["state"] or "未知"
            ] = r["count"]
        return Response(matrix)


class DailyBreakdownAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="Daily breakdown")
    def get(self, request):
        _check_feature_permission(request.user)
        wd_rows = (
            Incident.objects.values("weekday")
            .filter(weekday__isnull=False)
            .annotate(count=Count("id"))
            .all()
        )
        weekday_dist = {r["weekday"]: r["count"] for r in wd_rows}

        hr_rows = (
            Incident.objects.values("hour")
            .filter(hour__isnull=False)
            .annotate(count=Count("id"))
            .all()
        )
        hourly_dist = {str(r["hour"]): r["count"] for r in hr_rows}

        return Response({
            "weekday_dist": weekday_dist,
            "hourly_dist": hourly_dist,
        })


class IncidentListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="List incidents")
    def get(self, request):
        _check_feature_permission(request.user)

        priority = request.query_params.get("priority")
        state = request.query_params.get("state")
        group = request.query_params.get("group")
        category = request.query_params.get("category")
        company = request.query_params.get("company")
        sort_by = request.query_params.get("sort_by", "created_at")
        order = request.query_params.get("order", "desc")

        qs = Incident.objects.all()
        if priority:
            qs = qs.filter(priority=priority)
        if state:
            qs = qs.filter(state=state)
        if group:
            qs = qs.filter(assignment_group=group)
        if category:
            qs = qs.filter(category=category)
        if company:
            qs = qs.filter(company=company)

        allowed_sorts = [
            "created_at", "priority", "state", "resolve_hours",
        ]
        if sort_by not in allowed_sorts:
            sort_by = "created_at"
        order_prefix = "-" if order == "desc" else ""
        qs = qs.order_by(f"{order_prefix}{sort_by}")

        paginator = APIPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = IncidentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class RecentIncidentsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["sals"],
        summary="Recent incidents",
        parameters=[{"name": "limit", "in": "query", "schema": {"type": "integer", "default": 20}}],
    )
    def get(self, request):
        _check_feature_permission(request.user)
        limit = int(request.query_params.get("limit", 20))
        limit = max(1, min(limit, 50))
        rows = (
            Incident.objects.order_by("-created_at")[:limit]
        )
        return Response(IncidentSerializer(rows, many=True).data)


class CompanyListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="List companies")
    def get(self, request):
        _check_feature_permission(request.user)
        page = max(1, int(request.query_params.get("page", 1)))
        page_size = int(request.query_params.get("page_size", 50))
        page_size = max(1, min(page_size, 500))
        offset = (page - 1) * page_size
        rows = Company.objects.order_by("name", "sys_id")[offset:offset + page_size]
        return Response(CompanySerializer(rows, many=True).data)


class CompanyCountAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="Count companies")
    def get(self, request):
        _check_feature_permission(request.user)
        return Response({"count": Company.objects.count()})


class SyncCompaniesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="Sync companies from API")
    def post(self, request):
        _check_feature_permission(request.user)
        result = etl.sync_companies_from_api()
        status_code = status.HTTP_200_OK if result.get("status") == "ok" else status.HTTP_400_BAD_REQUEST
        return Response(result, status=status_code)


class UserListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="List users")
    def get(self, request):
        _check_feature_permission(request.user)
        page = max(1, int(request.query_params.get("page", 1)))
        page_size = int(request.query_params.get("page_size", 50))
        page_size = max(1, min(page_size, 500))
        department = request.query_params.get("department")
        active = request.query_params.get("active")
        offset = (page - 1) * page_size

        qs = User.objects.all()
        if department:
            qs = qs.filter(department=department)
        if active is not None:
            qs = qs.filter(active=active)
        rows = qs.order_by("name", "sys_id")[offset:offset + page_size]
        return Response(UserSerializer(rows, many=True).data)


class UserCountAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="Count users")
    def get(self, request):
        _check_feature_permission(request.user)
        department = request.query_params.get("department")
        active = request.query_params.get("active")
        qs = User.objects.all()
        if department:
            qs = qs.filter(department=department)
        if active is not None:
            qs = qs.filter(active=active)
        return Response({"count": qs.count()})


class SyncUsersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="Sync users from API")
    def post(self, request):
        _check_feature_permission(request.user)
        result = etl.sync_users_from_api()
        status_code = status.HTTP_200_OK if result.get("status") == "ok" else status.HTTP_400_BAD_REQUEST
        return Response(result, status=status_code)


class EscalationStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="L1-to-L2 escalation stats")
    def get(self, request):
        _check_feature_permission(request.user)
        from .services.escalation import L1_GROUPS, L2_GROUPS

        classified = Incident.objects.annotate(
            support_level=Case(
                When(
                    assignment_group__in=L1_GROUPS,
                    then=Value("L1"),
                ),
                When(
                    assignment_group__in=L2_GROUPS,
                    then=Value("L2"),
                ),
                default=Value("unclassified"),
                output_field=CharField(),
            )
        )

        # Summary counts
        level_counts = (
            classified.values("support_level")
            .annotate(count=Count("id"))
        )
        counts = {r["support_level"]: r["count"] for r in level_counts}
        l1 = counts.get("L1", 0)
        l2 = counts.get("L2", 0)
        total_classified = l1 + l2
        rate = round(l2 / total_classified * 100, 1) if total_classified else 0

        # Priority distribution
        priority_rows = (
            classified
            .filter(support_level__in=["L1", "L2"])
            .values("priority", "support_level")
            .annotate(count=Count("id"))
            .order_by("priority")
        )
        prio_map: dict = {}
        for r in priority_rows:
            p = r["priority"] or "未知"
            if p not in prio_map:
                prio_map[p] = {"priority": p, "l1": 0, "l2": 0}
            prio_map[p][r["support_level"].lower()] = r["count"]

        # Monthly trend
        trend_rows = (
            classified
            .filter(
                support_level__in=["L1", "L2"],
                month__isnull=False,
            )
            .values("month", "support_level")
            .annotate(count=Count("id"))
            .order_by("month")
        )
        trend_map: dict = {}
        for r in trend_rows:
            m = r["month"]
            if m not in trend_map:
                trend_map[m] = {"month": m, "l1": 0, "l2": 0}
            trend_map[m][r["support_level"].lower()] = r["count"]

        return Response({
            "summary": {
                "l1_count": l1,
                "l2_count": l2,
                "escalation_rate": rate,
            },
            "priority_dist": list(prio_map.values()),
            "monthly_trend": list(trend_map.values()),
        })


class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="Full dashboard data")
    def get(self, request):
        _check_feature_permission(request.user)

        kpi_view = KpiStatAPIView()
        kpi_view.request = request
        kpi_response = kpi_view.get(request)

        priority_view = PriorityDistAPIView()
        priority_response = priority_view.get(request)

        state_view = StateDistAPIView()
        state_response = state_view.get(request)

        monthly_view = MonthlyTrendAPIView()
        monthly_response = monthly_view.get(request)

        group_view = GroupStatsAPIView()
        group_response = group_view.get(request)

        assignee_view = AssigneeStatsAPIView()
        assignee_view.request = request
        assignee_response = assignee_view.get(request)

        customer_view = CustomerStatsAPIView()
        customer_view.request = request
        customer_response = customer_view.get(request)

        product_view = ProductStatsAPIView()
        product_response = product_view.get(request)

        sla_view = SlaStatsAPIView()
        sla_response = sla_view.get(request)

        matrix_view = ProductStateMatrixAPIView()
        matrix_response = matrix_view.get(request)

        escalation_view = EscalationStatsAPIView()
        escalation_response = escalation_view.get(request)

        recent_view = RecentIncidentsAPIView()
        recent_view.request = request
        recent_response = recent_view.get(request)

        return Response({
            "kpi": kpi_response.data,
            "priority_dist": priority_response.data,
            "state_dist": state_response.data,
            "monthly_trend": monthly_response.data,
            "group_stats": group_response.data,
            "assignee_stats": assignee_response.data,
            "customer_stats": customer_response.data,
            "product_stats": product_response.data,
            "sla_stats": sla_response.data,
            "product_state_matrix": matrix_response.data,
            "escalation_stats": escalation_response.data,
            "recent_incidents": recent_response.data,
        })


class InitDbAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["sals"],
        summary="Initialize / sync database",
        parameters=[
            {"name": "source", "in": "query", "schema": {"type": "string", "enum": ["api", "excel"]}},
            {"name": "full_sync", "in": "query", "schema": {"type": "boolean"}},
        ],
    )
    def post(self, request):
        _check_feature_permission(request.user)
        source = request.query_params.get("source", "api")
        full_sync = request.query_params.get("full_sync", "true").lower() != "false"

        try:
            if source == "api":
                result = etl.sync_from_api(full_sync=full_sync)
            else:
                result = {"status": "error", "message": "Excel source not supported in Django mode"}
            status_code = status.HTTP_200_OK if result.get("status") == "ok" else status.HTTP_400_BAD_REQUEST
            return Response(result, status=status_code)
        except Exception as e:
            logger.exception("InitDb failed")
            return Response({"status": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SyncStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sals"], summary="Sync status")
    def get(self, request):
        _check_feature_permission(request.user)
        return Response({
            "scheduler_running": False,
            "api_configured": bool(etl.login_api()),
            "sync_limit": etl.API_SYNC_LIMIT,
        })
