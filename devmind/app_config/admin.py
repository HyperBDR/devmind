"""
Admin configuration for GlobalConfig model.
"""
from django.contrib import admin
from django_json_widget.widgets import JSONEditorWidget
from django.db import models

from .models import GlobalConfig


@admin.register(GlobalConfig)
class GlobalConfigAdmin(admin.ModelAdmin):
    """
    Admin interface for GlobalConfig model.

    Provides a user-friendly interface for managing global configurations
    with JSON editor widget for the value field.
    """

    list_display = [
        'key',
        'category',
        'value_type',
        'value_preview',
        'is_active',
        'updated_at',
        'updated_by',
    ]

    list_filter = [
        'value_type',
        'category',
        'is_active',
        'created_at',
        'updated_at',
    ]

    search_fields = [
        'key',
        'category',
        'description',
    ]

    readonly_fields = [
        'created_at',
        'updated_at',
        'created_by',
        'updated_by',
    ]

    fieldsets = (
        ('Basic Information', {
            'fields': ('key', 'category', 'description')
        }),
        ('Value Configuration', {
            'fields': ('value_type', 'value', 'is_active')
        }),
        ('Metadata', {
            'fields': (
                'created_at',
                'updated_at',
                'created_by',
                'updated_by',
            ),
            'classes': ('collapse',)
        }),
    )

    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget},
    }

    def value_preview(self, obj):
        """
        Display a preview of the value (truncated if too long).
        """
        import json
        value_str = json.dumps(obj.value, ensure_ascii=False)
        if len(value_str) > 50:
            return value_str[:50] + '...'
        return value_str
    value_preview.short_description = 'Value Preview'

    def save_model(self, request, obj, form, change):
        """
        Automatically set created_by and updated_by fields.
        """
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
