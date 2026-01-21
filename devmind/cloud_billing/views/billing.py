"""
Views for BillingData API.
"""
from django.db.models import Avg, Sum

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import BillingData
from ..serializers import (
    BillingDataListSerializer,
    BillingDataSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=['cloud-billing'],
        summary="List billing data",
        description="Retrieve a list of billing data with filtering options.",
    ),
    retrieve=extend_schema(
        tags=['cloud-billing'],
        summary="Retrieve billing data",
        description="Get detailed information about a specific billing data record.",
    ),
)
class BillingDataViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for querying billing data.
    """
    queryset = BillingData.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """
        Return appropriate serializer class based on action.
        """
        if self.action == 'list':
            return BillingDataListSerializer
        return BillingDataSerializer

    def get_queryset(self):
        """
        Filter billing data by provider, period, and date range.
        """
        queryset = BillingData.objects.select_related('provider').all()

        provider_id = self.request.query_params.get('provider_id', None)
        period = self.request.query_params.get('period', None)
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)

        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        if period:
            queryset = queryset.filter(period=period)
        if start_date:
            queryset = queryset.filter(
                collected_at__gte=start_date
            )
        if end_date:
            queryset = queryset.filter(
                collected_at__lte=end_date
            )

        return queryset.order_by('-period', '-hour')

    @extend_schema(
        tags=['cloud-billing'],
        summary="Get billing statistics",
        description="Get statistical information about billing data.",
        responses={200: {'type': 'object'}},
    )
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get billing statistics.
        """
        queryset = self.get_queryset()

        provider_id = request.query_params.get('provider_id', None)
        period = request.query_params.get('period', None)
        group_by = request.query_params.get('group_by', 'day')

        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        if period:
            queryset = queryset.filter(period=period)

        total_cost = queryset.aggregate(
            Sum('total_cost')
        )['total_cost__sum'] or 0
        average_cost = queryset.aggregate(
            Avg('total_cost')
        )['total_cost__avg'] or 0
        count = queryset.count()

        cost_by_period = {}
        cost_by_service = {}

        for billing in queryset:
            period_key = billing.period
            if group_by == 'hour':
                period_key = f"{billing.period}-{billing.hour:02d}"

            if period_key not in cost_by_period:
                cost_by_period[period_key] = 0
            cost_by_period[period_key] += float(billing.total_cost)

            if billing.service_costs:
                for service_name, service_cost in (
                    billing.service_costs.items()
                ):
                    if service_name not in cost_by_service:
                        cost_by_service[service_name] = 0
                    cost_by_service[service_name] += float(service_cost)

        return Response({
            'total_cost': float(total_cost),
            'average_cost': float(average_cost),
            'count': count,
            'cost_by_period': cost_by_period,
            'cost_by_service': cost_by_service,
        })
