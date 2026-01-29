"""
Views for AlertRule and AlertRecord API.
"""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from ..models import AlertRecord, AlertRule
from ..serializers import (
    AlertRecordListSerializer,
    AlertRecordSerializer,
    AlertRuleListSerializer,
    AlertRuleSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=['cloud-billing'],
        summary="List alert rules",
        description="Retrieve a list of alert rules.",
    ),
    retrieve=extend_schema(
        tags=['cloud-billing'],
        summary="Retrieve an alert rule",
        description="Get detailed information about a specific alert rule.",
    ),
    create=extend_schema(
        tags=['cloud-billing'],
        summary="Create an alert rule",
        description="Create a new alert rule.",
    ),
    update=extend_schema(
        tags=['cloud-billing'],
        summary="Update an alert rule",
        description="Update an existing alert rule.",
    ),
    partial_update=extend_schema(
        tags=['cloud-billing'],
        summary="Partially update an alert rule",
        description="Partially update an existing alert rule.",
    ),
    destroy=extend_schema(
        tags=['cloud-billing'],
        summary="Delete an alert rule",
        description="Delete an alert rule.",
    ),
)
class AlertRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing alert rules.
    """
    queryset = AlertRule.objects.select_related('provider').all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """
        Return appropriate serializer class based on action.
        """
        if self.action == 'list':
            return AlertRuleListSerializer
        return AlertRuleSerializer

    def get_queryset(self):
        """
        Optionally filter by provider_id and is_active.
        """
        queryset = AlertRule.objects.select_related('provider').all()
        provider_id = self.request.query_params.get('provider_id', None)
        is_active = self.request.query_params.get('is_active', None)

        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)

        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        """
        Set created_by and updated_by to current user when creating.
        """
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user
        )

    def perform_update(self, serializer):
        """
        Set updated_by to current user when updating.
        """
        serializer.save(updated_by=self.request.user)


@extend_schema_view(
    list=extend_schema(
        tags=['cloud-billing'],
        summary="List alert records",
        description="Retrieve a list of alert records with filtering options.",
    ),
    retrieve=extend_schema(
        tags=['cloud-billing'],
        summary="Retrieve an alert record",
        description="Get detailed information about a specific alert record.",
    ),
)
class AlertRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for querying alert records.
    """
    queryset = (
        AlertRecord.objects.select_related('provider', 'alert_rule').all()
    )
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """
        Return appropriate serializer class based on action.
        """
        if self.action == 'list':
            return AlertRecordListSerializer
        return AlertRecordSerializer

    def get_queryset(self):
        """
        Filter alert records by provider, date range, and webhook status.
        """
        queryset = (
            AlertRecord.objects.select_related('provider', 'alert_rule')
            .all()
        )

        provider_id = self.request.query_params.get('provider_id', None)
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        webhook_status = self.request.query_params.get('webhook_status', None)

        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        if webhook_status:
            queryset = queryset.filter(webhook_status=webhook_status)

        return queryset.order_by('-created_at')
