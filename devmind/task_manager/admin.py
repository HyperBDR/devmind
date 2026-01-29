"""
Admin configuration for task management models.
"""
from django.contrib import admin

from .models import TaskExecution


@admin.register(TaskExecution)
class TaskExecutionAdmin(admin.ModelAdmin):
    """
    Admin interface for TaskExecution model.
    """
    list_display = [
        'task_id',
        'task_name',
        'module',
        'status',
        'created_by',
        'created_at',
        'started_at',
        'finished_at',
    ]
    list_filter = [
        'module',
        'status',
        'created_at',
    ]
    search_fields = [
        'task_id',
        'task_name',
        'module',
    ]
    readonly_fields = [
        'task_id',
        'created_at',
        'started_at',
        'finished_at',
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
