"""
Admin configuration for cloud billing models.
"""
from django.contrib import admin

from .models import (
    AlertRecord,
    AlertRule,
    BillingData,
    CloudProvider,
    RechargeApprovalEvent,
    RechargeApprovalLLMRun,
    RechargeApprovalRecord,
)


@admin.register(CloudProvider)
class CloudProviderAdmin(admin.ModelAdmin):
    """
    Admin interface for CloudProvider model.
    """
    list_display = [
        'name', 'provider_type', 'display_name', 'is_active', 'created_at'
    ]
    list_filter = ['provider_type', 'is_active', 'created_at']
    search_fields = ['name', 'display_name', 'recharge_info']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(BillingData)
class BillingDataAdmin(admin.ModelAdmin):
    """
    Admin interface for BillingData model.
    """
    list_display = [
        'provider', 'period', 'hour', 'total_cost', 'currency', 'collected_at'
    ]
    list_filter = ['provider', 'period', 'currency', 'collected_at']
    search_fields = [
        'provider__name', 'provider__display_name', 'account_id'
    ]
    readonly_fields = ['collected_at']
    date_hierarchy = 'collected_at'


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    """
    Admin interface for AlertRule model.
    """
    list_display = [
        'provider', 'cost_threshold', 'growth_threshold',
        'balance_threshold', 'days_remaining_threshold',
        'auto_submit_recharge_approval', 'is_active',
        'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['provider__name', 'provider__display_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(AlertRecord)
class AlertRecordAdmin(admin.ModelAdmin):
    """
    Admin interface for AlertRecord model.
    """
    list_display = [
        'provider', 'current_cost', 'previous_cost', 'increase_percent',
        'currency', 'current_balance', 'current_days_remaining',
        'webhook_status', 'created_at'
    ]
    list_filter = ['provider', 'webhook_status', 'currency', 'created_at']
    search_fields = [
        'provider__name', 'provider__display_name', 'alert_message'
    ]
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(RechargeApprovalRecord)
class RechargeApprovalRecordAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'provider', 'trigger_source', 'status', 'submitter_identifier',
        'triggered_by_username_snapshot', 'latest_stage', 'submitted_at',
        'last_callback_at', 'created_at'
    ]
    list_filter = ['trigger_source', 'status', 'created_at']
    search_fields = [
        'provider__name', 'provider__display_name', 'submitter_identifier',
        'feishu_instance_code', 'feishu_approval_code'
    ]
    readonly_fields = ['trace_id', 'created_at', 'updated_at']


@admin.register(RechargeApprovalEvent)
class RechargeApprovalEventAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'record', 'event_type', 'stage', 'source', 'operator_label',
        'created_at'
    ]
    list_filter = ['event_type', 'stage', 'source', 'created_at']
    search_fields = ['record__id', 'message', 'operator_label']
    readonly_fields = ['created_at']


@admin.register(RechargeApprovalLLMRun)
class RechargeApprovalLLMRunAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'record', 'runner_type', 'stage', 'provider', 'model',
        'success', 'latency_ms', 'created_at'
    ]
    list_filter = ['runner_type', 'stage', 'success', 'created_at']
    search_fields = ['record__id', 'provider', 'model', 'error_message']
    readonly_fields = ['trace_id', 'span_id', 'created_at']
