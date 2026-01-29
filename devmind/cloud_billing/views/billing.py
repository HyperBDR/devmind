"""
Views for BillingData API.
"""
from datetime import datetime, timedelta

from django.db.models import Avg, Max, Sum, OuterRef, Q, Subquery

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
        description=(
            "Get detailed information about a specific billing data record."
        ),
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
            # Start date: include from 00:00:00 of that day
            queryset = queryset.filter(
                collected_at__gte=start_date
            )
        if end_date:
            # End date: include until 23:59:59 of that day
            # Add one day and use __lt to include the entire end_date
            end_datetime = (
                datetime.strptime(end_date, '%Y-%m-%d') +
                timedelta(days=1)
            )
            queryset = queryset.filter(
                collected_at__lt=end_datetime
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

        Statistics are grouped by month (period).
        Total cost: sum of latest total_cost for each
        (provider, account_id, period)
        Average cost: total_cost / number of
        (provider, account_id) combinations
        """
        queryset = self.get_queryset()

        provider_id = request.query_params.get('provider_id', None)
        period = request.query_params.get('period', None)
        start_period = request.query_params.get('start_period', None)
        end_period = request.query_params.get('end_period', None)

        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        if period:
            queryset = queryset.filter(period=period)
        if start_period:
            queryset = queryset.filter(period__gte=start_period)
        if end_period:
            queryset = queryset.filter(period__lte=end_period)

        # Get the latest billing record for each
        # (provider, account_id, period)
        # This represents the cumulative total cost for that month
        # Order by hour descending to get the last hour of each period
        latest_billings = {}
        for billing in queryset.order_by(
            'provider_id', 'account_id', 'period', '-hour',
            '-collected_at'
        ):
            key = (
                f"{billing.provider_id}_{billing.account_id or ''}_"
                f"{billing.period}"
            )
            # Keep only the first (latest) record for each key
            # This ensures we get the last hour's data for each month
            if key not in latest_billings:
                latest_billings[key] = billing

        # Total cost: sum of latest total_cost for each
        # (provider, account_id, period)
        total_cost = sum(
            float(b.total_cost) for b in latest_billings.values()
        )

        # Average cost: total_cost / number of unique
        # (provider, account_id) combinations
        # Count unique provider+account combinations across all periods
        unique_provider_accounts = set()
        for billing in latest_billings.values():
            unique_provider_accounts.add(
                (billing.provider_id, billing.account_id or '')
            )
        
        average_cost = (
            total_cost / len(unique_provider_accounts)
            if unique_provider_accounts else 0
        )

        count = queryset.count()

        # Determine if grouping by year or month
        # If start_period and end_period span a full year
        # (YYYY-01 to YYYY-12), group by year; otherwise group by month
        group_by_year = False
        if start_period and end_period:
            try:
                start_year, start_month = start_period.split('-')
                end_year, end_month = end_period.split('-')
                if (start_year == end_year and 
                    start_month == '01' and 
                    end_month == '12'):
                    group_by_year = True
            except (ValueError, AttributeError):
                pass

        # Group by period (year or month)
        cost_by_period = {}
        cost_by_service = {}
        by_provider = {}

        # Track which months are included for debugging
        months_by_year = {} if group_by_year else None

        for billing in latest_billings.values():
            if group_by_year:
                # Extract year from period (YYYY-MM -> YYYY)
                # This groups all months of the same year together
                period_key = billing.period.split('-')[0]
                
                # Track which months are included for this year
                if period_key not in months_by_year:
                    months_by_year[period_key] = set()
                months_by_year[period_key].add(billing.period)
            else:
                # Use full period (YYYY-MM) for month grouping
                period_key = billing.period

            # Sum total_cost for each period
            # Note: total_cost is the cumulative cost for that month
            # (from start of month)
            # When grouping by year: sum all months' total_cost to get
            # yearly total
            # When grouping by month: use the month's total_cost directly
            if period_key not in cost_by_period:
                cost_by_period[period_key] = 0
            
            # Add this month's total_cost to the period total
            # For year grouping: accumulates costs from all months in
            # that year
            # Each billing record represents one
            # (provider, account_id, month) combination
            # The total_cost is the month's cumulative cost
            # (last hour of that month)
            cost_by_period[period_key] += float(billing.total_cost)

            # Group by service (sum service costs from latest records)
            if billing.service_costs:
                for service_name, service_cost in (
                    billing.service_costs.items()
                ):
                    if service_name not in cost_by_service:
                        cost_by_service[service_name] = 0
                    cost_by_service[service_name] += float(service_cost)

            # Group by provider + account_id
            # Use latest total_cost for each provider+account combination
            provider_key = (
                f"{billing.provider_id}_{billing.account_id or ''}"
            )
            if provider_key not in by_provider:
                by_provider[provider_key] = {
                    'provider_id': billing.provider_id,
                    'provider_name': billing.provider.display_name,
                    'account_id': billing.account_id or '',
                    'total_cost': 0,
                    'count': 0
                }
            # Use the maximum total_cost across all periods for this
            # provider+account
            by_provider[provider_key]['total_cost'] = max(
                by_provider[provider_key]['total_cost'],
                float(billing.total_cost)
            )
            by_provider[provider_key]['count'] += 1

        return Response({
            'total_cost': float(total_cost),
            'average_cost': float(average_cost),
            'count': count,
            'cost_by_period': cost_by_period,
            'cost_by_service': cost_by_service,
            'by_provider': by_provider,
        })

    @extend_schema(
        tags=['cloud-billing'],
        summary="Get latest billing data by provider and account",
        description=(
            "Get the latest billing data grouped by provider and account_id. "
            "Returns the most recent billing record for each unique "
            "provider + account_id combination."
        ),
        responses={200: BillingDataListSerializer(many=True)},
    )
    @action(
        detail=False, methods=['get'],
        url_path='latest-by-provider-account'
    )
    def latest_by_provider_account(self, request):
        """
        Get latest billing data grouped by provider and account_id.

        Returns the most recent billing record for each unique
        provider + account_id combination within the specified date range.
        """
        queryset = BillingData.objects.select_related('provider').all()

        provider_id = request.query_params.get('provider_id', None)
        start_date = request.query_params.get('start_date', None)
        end_date = request.query_params.get('end_date', None)

        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        if start_date:
            queryset = queryset.filter(collected_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(collected_at__lte=end_date)

        # Get the latest billing record for each provider + account_id
        # combination using subquery
        latest_ids = BillingData.objects.filter(
            provider_id=OuterRef('provider_id'),
            account_id=OuterRef('account_id')
        ).order_by('-collected_at').values('id')[:1]

        latest_records = queryset.filter(
            id__in=Subquery(latest_ids)
        ).order_by('provider__display_name', 'account_id')

        serializer = BillingDataListSerializer(latest_records, many=True)
        return Response(serializer.data)
