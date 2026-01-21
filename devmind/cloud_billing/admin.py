"""
Admin configuration for cloud billing models.
"""
from django.contrib import admin

from .models import AlertRecord, AlertRule, BillingData, CloudProvider


@admin.register(CloudProvider)
class CloudProviderAdmin(admin.ModelAdmin):
    """
    Admin interface for CloudProvider model.
    """
    list_display = [
        'name', 'provider_type', 'display_name', 'is_active', 'created_at'
    ]
    list_filter = ['provider_type', 'is_active', 'created_at']
    search_fields = ['name', 'display_name']
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
        'provider', 'cost_threshold', 'growth_threshold', 'is_active',
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
        'currency', 'webhook_status', 'created_at'
    ]
    list_filter = ['provider', 'webhook_status', 'currency', 'created_at']
    search_fields = [
        'provider__name', 'provider__display_name', 'alert_message'
    ]
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
