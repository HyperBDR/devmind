"""
Views for task execution management.
"""
from django.contrib.auth.models import User

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import TaskExecution
from ..serializers import (
    TaskExecutionListSerializer,
    TaskExecutionSerializer,
    TaskStatsSerializer,
)
from ..services.task_tracker import TaskTracker


@extend_schema_view(
    list=extend_schema(
        tags=['task-management'],
        summary="List task executions",
        description=(
            "Retrieve a list of task executions with filtering options."
        ),
    ),
    retrieve=extend_schema(
        tags=['task-management'],
        summary="Retrieve task execution",
        description=(
            "Get detailed information about a specific task execution."
        ),
    ),
)
class TaskExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for querying task executions.
    """
    queryset = TaskExecution.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """
        Return appropriate serializer class based on action.
        """
        if self.action == 'list':
            return TaskExecutionListSerializer
        return TaskExecutionSerializer

    def get_queryset(self):
        """
        Filter task executions by module, task_name, status, etc.
        By default, users can only see their own tasks unless they specify
        created_by parameter or have admin permissions.
        """
        queryset = TaskExecution.objects.select_related('created_by').all()

        # Check if user wants to see all tasks (admin) or specific user's tasks
        created_by = self.request.query_params.get('created_by', None)
        my_tasks_only = self.request.query_params.get('my_tasks', None)
        
        # Default: show only current user's tasks unless
        # 'my_tasks=false' or 'created_by' is specified
        if my_tasks_only is None and created_by is None:
            # Default behavior: show user's own tasks
            queryset = queryset.filter(created_by=self.request.user)
        elif my_tasks_only and my_tasks_only.lower() == 'false':
            # Explicitly request all tasks (requires appropriate permissions)
            pass
        elif created_by:
            # Filter by specific user ID
            queryset = queryset.filter(created_by_id=created_by)

        module = self.request.query_params.get('module', None)
        task_name = self.request.query_params.get('task_name', None)
        status_filter = self.request.query_params.get('status', None)
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)

        if module:
            queryset = queryset.filter(module=module)
        if task_name:
            queryset = queryset.filter(task_name=task_name)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)

        return queryset.order_by('-created_at')

    @extend_schema(
        tags=['task-management'],
        summary="Get task status",
        description="Get the status of a specific task by task_id.",
        responses={200: TaskExecutionSerializer},
    )
    @action(detail=False, methods=['get'], url_path='status')
    def status(self, request):
        """
        Get task status by task_id.
        """
        task_id = request.query_params.get('task_id', None)
        if not task_id:
            return Response({
                'error': 'task_id parameter is required',
            }, status=status.HTTP_400_BAD_REQUEST)

        sync = request.query_params.get('sync', 'true').lower() == 'true'
        task_execution = TaskTracker.get_task(task_id, sync=sync)

        if not task_execution:
            return Response({
                'error': 'Task not found',
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = TaskExecutionSerializer(task_execution)
        return Response(serializer.data)

    @extend_schema(
        tags=['task-management'],
        summary="Get task by task_id",
        description="Get task execution details by Celery task_id.",
        responses={200: TaskExecutionSerializer},
    )
    @action(
        detail=False, methods=['get'],
        url_path='by-task-id/(?P<task_id>[^/.]+)'
    )
    def by_task_id(self, request, task_id=None):
        """
        Get task execution by Celery task_id.
        """
        sync = request.query_params.get('sync', 'true').lower() == 'true'
        task_execution = TaskTracker.get_task(task_id, sync=sync)

        if not task_execution:
            return Response({
                'error': 'Task not found',
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = TaskExecutionSerializer(task_execution)
        return Response(serializer.data)

    @extend_schema(
        tags=['task-management'],
        summary="Sync task status",
        description="Manually sync task status from Celery result backend.",
        responses={200: TaskExecutionSerializer},
    )
    @action(detail=True, methods=['post'], url_path='sync')
    def sync(self, request, pk=None):
        """
        Manually sync task status from Celery.
        """
        task_execution = self.get_object()
        synced_task = TaskTracker.sync_task_from_celery(
            task_execution.task_id
        )

        if not synced_task:
            return Response({
                'error': 'Failed to sync task',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = TaskExecutionSerializer(synced_task)
        return Response(serializer.data)

    @extend_schema(
        tags=['task-management'],
        summary="Get task statistics",
        description="Get statistical information about task executions.",
        responses={200: TaskStatsSerializer},
    )
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get task execution statistics.
        By default, statistics are for current user's tasks only.
        """
        module = request.query_params.get('module', None)
        task_name = request.query_params.get('task_name', None)
        created_by = request.query_params.get('created_by', None)
        my_tasks_only = request.query_params.get('my_tasks', None)

        # Default: show stats for current user's tasks
        user_filter = None
        if my_tasks_only is None and created_by is None:
            user_filter = request.user
        elif created_by:
            try:
                user_filter = User.objects.get(id=created_by)
            except User.DoesNotExist:
                user_filter = None

        stats = TaskTracker.get_task_stats(
            module=module,
            task_name=task_name,
            created_by=user_filter
        )

        serializer = TaskStatsSerializer(stats)
        return Response(serializer.data)

    @extend_schema(
        tags=['task-management'],
        summary="Get my tasks",
        description="Get current user's task executions.",
        responses={200: TaskExecutionListSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path='my-tasks')
    def my_tasks(self, request):
        """
        Get current user's task executions.
        """
        queryset = TaskExecution.objects.filter(
            created_by=request.user
        ).select_related('created_by').order_by('-created_at')

        # Apply additional filters
        module = request.query_params.get('module', None)
        task_name = request.query_params.get('task_name', None)
        status_filter = request.query_params.get('status', None)
        start_date = request.query_params.get('start_date', None)
        end_date = request.query_params.get('end_date', None)

        if module:
            queryset = queryset.filter(module=module)
        if task_name:
            queryset = queryset.filter(task_name=task_name)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = TaskExecutionListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = TaskExecutionListSerializer(queryset, many=True)
        return Response(serializer.data)
