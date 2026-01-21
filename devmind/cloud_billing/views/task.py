"""
Views for billing task management.
"""
from celery.result import AsyncResult

from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..tasks import collect_billing_data


class BillingTaskViewSet(viewsets.ViewSet):
    """
    ViewSet for managing billing collection tasks.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['cloud-billing'],
        summary="Trigger billing collection",
        description="Manually trigger billing data collection for specified or all active providers.",
        responses={200: {'type': 'object'}},
    )
    @action(detail=False, methods=['post'])
    def collect(self, request):
        """
        Manually trigger billing data collection.
        """
        provider_id = request.query_params.get('provider_id', None)

        try:
            provider_id_int = int(provider_id) if provider_id else None
            task = collect_billing_data.delay(provider_id_int)
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
        description="Get the status of billing collection tasks.",
        responses={200: {'type': 'object'}},
    )
    @action(detail=False, methods=['get'])
    def status(self, request):
        """
        Get task status.
        """
        task_id = request.query_params.get('task_id', None)
        if not task_id:
            return Response({
                'message': 'task_id parameter is required',
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = AsyncResult(task_id)
            result_data = result.result if result.ready() else None
            return Response({
                'task_id': task_id,
                'status': result.status,
                'result': result_data,
            })
        except Exception as e:
            return Response({
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
