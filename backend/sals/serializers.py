"""
DRF serializers for SALS API.
"""
from rest_framework import serializers

from .models import Company, User, Incident


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            "id",
            "sys_id",
            "name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "sys_id",
            "name",
            "email",
            "user_name",
            "department",
            "phone",
            "mobile_phone",
            "title",
            "active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class IncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Incident
        fields = [
            "id",
            "number",
            "parent_incident",
            "short_description",
            "company",
            "caller",
            "created_by",
            "priority",
            "assigned_to",
            "state",
            "resolution_code",
            "category",
            "assignment_group",
            "updated_by",
            "created_at",
            "updated_at",
            "resolve_hours",
            "sla_limit",
            "is_sla_met",
            "month",
            "weekday",
            "hour",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "resolve_hours",
            "sla_limit",
            "is_sla_met",
            "month",
            "weekday",
            "hour",
        ]


class KpiStatSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    pending = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    resolved = serializers.IntegerField()
    closed = serializers.IntegerField()
    canceled = serializers.IntegerField()
    resolved_rate = serializers.FloatField()
    sla_rate = serializers.FloatField()
    avg_resolve_hours = serializers.FloatField()
    p1_total = serializers.IntegerField()
    p1_overdue = serializers.IntegerField()
    p2_total = serializers.IntegerField()


class PriorityDistSerializer(serializers.Serializer):
    priority = serializers.CharField()
    count = serializers.IntegerField()


class StateDistSerializer(serializers.Serializer):
    state = serializers.CharField()
    count = serializers.IntegerField()


class GroupStatSerializer(serializers.Serializer):
    group = serializers.CharField()
    count = serializers.IntegerField()
    avg_hours = serializers.FloatField()
    resolved_rate = serializers.FloatField()


class AssigneeStatSerializer(serializers.Serializer):
    assignee = serializers.CharField()
    count = serializers.IntegerField()
    avg_hours = serializers.FloatField()
    pending_count = serializers.IntegerField()


class MonthlyTrendSerializer(serializers.Serializer):
    month = serializers.CharField()
    total = serializers.IntegerField()
    avg_hours = serializers.FloatField()


class CustomerStatSerializer(serializers.Serializer):
    company = serializers.CharField()
    count = serializers.IntegerField()
    resolved_count = serializers.IntegerField()
    resolve_rate = serializers.FloatField()
    avg_hours = serializers.FloatField()
    category = serializers.CharField()


class ProductStatSerializer(serializers.Serializer):
    category = serializers.CharField()
    count = serializers.IntegerField()


class KeywordStatSerializer(serializers.Serializer):
    keyword = serializers.CharField()
    count = serializers.IntegerField()


class SlaStatSerializer(serializers.Serializer):
    priority = serializers.CharField()
    count = serializers.IntegerField()
    sla_met = serializers.IntegerField()
    sla_rate = serializers.FloatField()
    avg_hours = serializers.FloatField()
    sla_limit = serializers.FloatField()


class DailyBreakdownSerializer(serializers.Serializer):
    weekday_dist = serializers.DictField(child=serializers.IntegerField())
    hourly_dist = serializers.DictField(child=serializers.IntegerField())


class DashboardDataSerializer(serializers.Serializer):
    kpi = KpiStatSerializer()
    priority_dist = PriorityDistSerializer(many=True)
    state_dist = StateDistSerializer(many=True)
    monthly_trend = MonthlyTrendSerializer(many=True)
    group_stats = GroupStatSerializer(many=True)
    assignee_stats = AssigneeStatSerializer(many=True)
    customer_stats = CustomerStatSerializer(many=True)
    product_stats = ProductStatSerializer(many=True)
    sla_stats = SlaStatSerializer(many=True)
    product_state_matrix = serializers.DictField(
        child=serializers.DictField(child=serializers.IntegerField())
    )
