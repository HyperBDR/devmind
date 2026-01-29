"""
Admin configuration for notifier app.
"""
from django.contrib import admin

from .models import NotificationRecord


@admin.register(NotificationRecord)
class NotificationRecordAdmin(admin.ModelAdmin):
    """
    Admin interface for NotificationRecord.
    """
    list_display = [
        'id',
        'user',
        'provider_type',
        'source_app',
        'source_type',
        'status',
        'created_at',
        'sent_at'
    ]
    list_filter = [
        'status',
        'provider_type',
        'source_app',
        'created_at'
    ]
    search_fields = [
        'user__username',
        'user__email',
        'source_app',
        'source_type',
        'source_id',
        'error_message'
    ]
    readonly_fields = [
        'created_at',
        'sent_at'
    ]
    fieldsets = (
        ('Notification Info', {
            'fields': (
                'provider_type',
                'channel',
            )
        }),
        ('User Info', {
            'fields': ('user',)
        }),
        ('Source Info', {
            'fields': (
                'source_app',
                'source_type',
                'source_id',
            )
        }),
        ('Status', {
            'fields': (
                'status',
                'response',
                'error_message',
            )
        }),
        ('Content', {
            'fields': (
                'payload',
                'metadata',
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'sent_at',
            )
        }),
    )
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
