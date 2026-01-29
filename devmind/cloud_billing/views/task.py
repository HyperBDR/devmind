"""
Views for billing task management.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from task_manager import is_task_locked
from task_manager.services.task_tracker import TaskTracker
from task_manager.utils import register_task_execution

from ..tasks import collect_billing_data


class BillingTaskViewSet(viewsets.ViewSet):
    """
    ViewSet for managing billing collection tasks.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['cloud-billing'],
        summary="Trigger billing collection",
        description=(
            "Manually trigger billing data collection for specified "
            "or all active providers."
        ),
        responses={200: {'type': 'object'}},
    )
    @action(detail=False, methods=['post'])
    def collect(self, request):
        """
        Manually trigger billing data collection.
        Task locker will prevent duplicate execution per user.
        """
        provider_id = request.query_params.get('provider_id', None)

        try:
            provider_id_int = (
                int(provider_id) if provider_id else None
            )
            user_id = (
                request.user.id
                if request.user.is_authenticated else None
            )

            # Check if task is already running for this user using task lock
            if user_id:
                lock_name = f"collect_billing_data_{user_id}"
            else:
                lock_name = "collect_billing_data"
            if is_task_locked(lock_name):
                return Response({
                    'success': False,
                    'message': (
                        'Collection task is already running for your '
                        'account. Please wait for it to complete.'
                    ),
                    'reason': 'task_already_running',
                }, status=status.HTTP_409_CONFLICT)

            task = collect_billing_data.delay(
                provider_id_int, user_id=user_id
            )

            # Register task in unified task management system
            register_task_execution(
                task_id=task.id,
                task_name='cloud_billing.tasks.collect_billing_data',
                module='cloud_billing',
                task_kwargs={
                    'provider_id': provider_id_int,
                    'user_id': user_id
                },
                created_by=(
                    request.user
                    if request.user.is_authenticated else None
                ),
                metadata={
                    'provider_id': provider_id_int,
                    'user_id': user_id
                }
            )

            return Response({
                'success': True,
                'message': 'Billing collection task started',
                'task_id': task.id,
            })
        except Exception as e:
            return Response({
                'success': False,
                'message': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        tags=['cloud-billing'],
        summary="Get task status",
        description=(
            "Get the status of billing collection tasks. "
            "Uses task_manager for unified task tracking."
        ),
        responses={200: {'type': 'object'}},
    )
    @action(detail=False, methods=['get'])
    def status(self, request):
        """
        Get task status using task_manager.
        """
        task_id = request.query_params.get('task_id', None)
        if not task_id:
            return Response({
                'error': 'task_id parameter is required',
            }, status=status.HTTP_400_BAD_REQUEST)

        sync = (
            request.query_params.get('sync', 'true').lower() == 'true'
        )
        task_execution = TaskTracker.get_task(task_id, sync=sync)

        if not task_execution:
            return Response({
                'error': 'Task not found',
            }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'task_id': task_execution.task_id,
            'task_name': task_execution.task_name,
            'status': task_execution.status,
            'result': task_execution.result,
            'error': task_execution.error,
            'created_at': task_execution.created_at,
            'started_at': task_execution.started_at,
            'finished_at': task_execution.finished_at,
        })
