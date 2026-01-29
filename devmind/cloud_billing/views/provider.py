"""
Views for CloudProvider API.
"""
import logging
import re

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import CloudProvider
from ..serializers import (
    CloudProviderListSerializer,
    CloudProviderSerializer,
)
from ..services.provider_service import ProviderService
from ..utils.logging import mask_sensitive_config


@extend_schema_view(
    list=extend_schema(
        tags=['cloud-billing'],
        summary="List all cloud providers",
        description="Retrieve a list of all cloud provider configurations.",
    ),
    retrieve=extend_schema(
        tags=['cloud-billing'],
        summary="Retrieve a cloud provider",
        description=(
            "Get detailed information about a specific cloud provider."
        ),
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
        description=(
            "Partially update an existing cloud provider configuration."
        ),
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
        Auto-generate name if not provided.
        """
        data = serializer.validated_data

        # Auto-generate name if not provided or empty
        name = None
        if data.get('name'):
            provided_name = data.get('name', '').strip()
        else:
            provided_name = ''
        
        if not provided_name:
            if not data.get('display_name'):
                raise serializers.ValidationError({
                    'display_name': (
                        'Display name is required when name is not provided.'
                    )
                })
            
            provider_type = data.get('provider_type', '')
            display_name = data.get('display_name', '')

            # Convert display name to lowercase and replace spaces
            # with underscores
            base_name = re.sub(
                r'[^a-z0-9]+', '_', display_name.lower()
            ).strip('_')

            # Add provider type prefix if not already present
            type_prefix = provider_type.replace('-', '_')
            if not base_name.startswith(type_prefix):
                name = f"{type_prefix}_{base_name}"
            else:
                name = base_name

            # Ensure uniqueness by appending number if needed
            original_name = name
            counter = 1
            while CloudProvider.objects.filter(name=name).exists():
                name = f"{original_name}_{counter}"
                counter += 1
        else:
            # Use provided name, but ensure uniqueness
            name = provided_name
            original_name = name
            counter = 1
            while CloudProvider.objects.filter(name=name).exists():
                name = f"{original_name}_{counter}"
                counter += 1

        # Save with auto-generated or provided name
        save_kwargs = {
            'created_by': self.request.user,
            'updated_by': self.request.user,
            'name': name
        }

        serializer.save(**save_kwargs)

    def perform_update(self, serializer):
        """
        Set updated_by to current user when updating.
        """
        serializer.save(updated_by=self.request.user)

    @extend_schema(
        tags=['cloud-billing'],
        summary="Validate provider credentials",
        description=(
            "Validate the authentication credentials for a cloud provider."
        ),
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

    @extend_schema(
        tags=['cloud-billing'],
        summary="Validate provider configuration",
        description=(
            "Validate provider configuration without saving to database."
        ),
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'provider_type': {'type': 'string'},
                    'config': {'type': 'object'},
                },
                'required': ['provider_type', 'config'],
            }
        },
        responses={200: {'type': 'object'}},
    )
    @action(detail=False, methods=['post'], url_path='validate-config')
    def validate_config(self, request):
        """
        Validate provider configuration without saving.
        """
        provider_type = request.data.get('provider_type')
        config = request.data.get('config')

        if not provider_type:
            return Response({
                'valid': False,
                'message': 'provider_type is required',
                'account_id': '',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if config is None:
            return Response({
                'valid': False,
                'message': 'config is required',
                'account_id': '',
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            logger = logging.getLogger(__name__)
            sanitized_config = mask_sensitive_config(config)
            logger.info(
                f"validate_config called with provider_type={provider_type}, "
                f"config={sanitized_config}"
            )
            provider_service = ProviderService()
            result = provider_service.validate_credentials(
                provider_type,
                config
            )

            return Response({
                'valid': result.get('valid', False),
                'error_code': result.get('error_code'),
                'account_id': result.get('account_id', ''),
            })
        except Exception as e:
            return Response({
                'valid': False,
                'message': str(e),
                'account_id': '',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
