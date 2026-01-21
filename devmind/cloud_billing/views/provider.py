"""
Views for CloudProvider API.
"""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import CloudProvider
from ..serializers import (
    CloudProviderListSerializer,
    CloudProviderSerializer,
)
from ..services.provider_service import ProviderService


@extend_schema_view(
    list=extend_schema(
        tags=['cloud-billing'],
        summary="List all cloud providers",
        description="Retrieve a list of all cloud provider configurations.",
    ),
    retrieve=extend_schema(
        tags=['cloud-billing'],
        summary="Retrieve a cloud provider",
        description="Get detailed information about a specific cloud provider.",
    ),
    create=extend_schema(
        tags=['cloud-billing'],
        summary="Create a cloud provider",
        description="Create a new cloud provider configuration.",
    ),
    update=extend_schema(
        tags=['cloud-billing'],
        summary="Update a cloud provider",
        description="Update an existing cloud provider configuration.",
    ),
    partial_update=extend_schema(
        tags=['cloud-billing'],
        summary="Partially update a cloud provider",
        description="Partially update an existing cloud provider configuration.",
    ),
    destroy=extend_schema(
        tags=['cloud-billing'],
        summary="Delete a cloud provider",
        description="Delete a cloud provider configuration.",
    ),
)
class CloudProviderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing cloud provider configurations.
    """
    queryset = CloudProvider.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """
        Return appropriate serializer class based on action.
        """
        if self.action == 'list':
            return CloudProviderListSerializer
        return CloudProviderSerializer

    def get_queryset(self):
        """
        Optionally filter by provider_type and is_active.
        """
        queryset = CloudProvider.objects.all()
        provider_type = self.request.query_params.get(
            'provider_type', None
        )
        is_active = self.request.query_params.get('is_active', None)

        if provider_type:
            queryset = queryset.filter(provider_type=provider_type)
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)

        return queryset.order_by('name')

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

    @extend_schema(
        tags=['cloud-billing'],
        summary="Validate provider credentials",
        description="Validate the authentication credentials for a cloud provider.",
        responses={200: {'type': 'object'}},
    )
    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """
        Validate provider credentials.
        """
        provider = self.get_object()

        try:
            provider_service = ProviderService()
            result = provider_service.validate_credentials(
                provider.provider_type,
                provider.config
            )

            if result.get('valid'):
                return Response({
                    'valid': True,
                    'message': 'Credentials are valid',
                    'account_id': result.get('account_id', ''),
                })
            else:
                error_msg = result.get(
                    'message', 'Credentials validation failed'
                )
                return Response({
                    'valid': False,
                    'message': error_msg,
                    'account_id': '',
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'valid': False,
                'message': str(e),
                'account_id': '',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
