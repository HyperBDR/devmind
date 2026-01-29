"""
Serializers for task management API.
"""
from rest_framework import serializers

from .models import TaskExecution


class TaskExecutionSerializer(serializers.ModelSerializer):
    """
    Serializer for TaskExecution model.
    """
    duration = serializers.ReadOnlyField()
    is_completed = serializers.ReadOnlyField()
    is_running = serializers.ReadOnlyField()
    created_by_username = serializers.CharField(
        source='created_by.username',
        read_only=True
    )
    created_by_id = serializers.IntegerField(
        source='created_by.id',
        read_only=True
    )

    class Meta:
        model = TaskExecution
        fields = [
            'id',
            'task_id',
            'task_name',
            'module',
            'status',
            'created_at',
            'started_at',
            'finished_at',
            'task_args',
            'task_kwargs',
            'result',
            'error',
            'traceback',
            'created_by',
            'created_by_id',
            'created_by_username',
            'metadata',
            'duration',
            'is_completed',
            'is_running',
        ]
        read_only_fields = [
            'id',
            'task_id',
            'status',
            'created_at',
            'started_at',
            'finished_at',
            'result',
            'error',
            'traceback',
        ]


class TaskExecutionListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for task execution list view.
    """
    duration = serializers.ReadOnlyField()
    is_completed = serializers.ReadOnlyField()
    is_running = serializers.ReadOnlyField()
    created_by_username = serializers.CharField(
        source='created_by.username',
        read_only=True
    )
    created_by_id = serializers.IntegerField(
        source='created_by.id',
        read_only=True
    )

    class Meta:
        model = TaskExecution
        fields = [
            'id',
            'task_id',
            'task_name',
            'module',
            'status',
            'created_at',
            'started_at',
            'finished_at',
            'created_by_id',
            'created_by_username',
            'duration',
            'is_completed',
            'is_running',
        ]


class TaskStatsSerializer(serializers.Serializer):
    """
    Serializer for task statistics.
    """
    total = serializers.IntegerField()
    pending = serializers.IntegerField()
    started = serializers.IntegerField()
    success = serializers.IntegerField()
    failure = serializers.IntegerField()
    retry = serializers.IntegerField()
    revoked = serializers.IntegerField()
    by_module = serializers.DictField(
        child=serializers.DictField()
    )
    by_task_name = serializers.DictField(
        child=serializers.DictField()
    )
