"""
Views for global configuration management.

Provides REST API endpoints for CRUD operations on global configurations.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import GlobalConfig
from ..serializers import (
    GlobalConfigSerializer,
    GlobalConfigListSerializer,
    GlobalConfigCreateSerializer,
    GlobalConfigUpdateSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=['config'],
        summary="List all configurations",
        description=(
            "Retrieve a list of all global configurations. "
            "Supports filtering by category and is_active status."
        ),
    ),
    retrieve=extend_schema(
        tags=['config'],
        summary="Retrieve a configuration",
        description=(
            "Get detailed information about a specific configuration by ID."
        ),
    ),
    create=extend_schema(
        tags=['config'],
        summary="Create a configuration",
        description="Create a new global configuration entry.",
    ),
    update=extend_schema(
        tags=['config'],
        summary="Update a configuration",
        description="Update an existing global configuration entry.",
    ),
    partial_update=extend_schema(
        tags=['config'],
        summary="Partially update a configuration",
        description="Partially update an existing global configuration entry.",
    ),
    destroy=extend_schema(
        tags=['config'],
        summary="Delete a configuration",
        description="Delete a global configuration entry.",
    ),
)
class GlobalConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing global configurations.

    Provides standard CRUD operations:
    - GET /api/v1/config/ - List all configurations
    - GET /api/v1/config/{id}/ - Get a specific configuration
    - POST /api/v1/config/ - Create a new configuration
    - PUT /api/v1/config/{id}/ - Update a configuration
    - PATCH /api/v1/config/{id}/ - Partially update a configuration
    - DELETE /api/v1/config/{id}/ - Delete a configuration
    """

    queryset = GlobalConfig.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """
        Return appropriate serializer class based on action.
        """
        if self.action == 'list':
            return GlobalConfigListSerializer
        elif self.action == 'create':
            return GlobalConfigCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return GlobalConfigUpdateSerializer
        return GlobalConfigSerializer

    def get_queryset(self):
        """
        Optionally filter by category and is_active.
        """
        queryset = GlobalConfig.objects.all()
        category = self.request.query_params.get('category', None)
        is_active = self.request.query_params.get('is_active', None)

        if category:
            queryset = queryset.filter(category=category)
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)

        return queryset.order_by('category', 'key')

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


class GlobalConfigByKeyView(APIView):
    """
    Retrieve or update a configuration by key.

    GET /api/v1/config/key/{key}/ - Get configuration by key
    PUT /api/v1/config/key/{key}/ - Update configuration by key
    PATCH /api/v1/config/key/{key}/ - Partially update configuration by key
    DELETE /api/v1/config/key/{key}/ - Delete configuration by key
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['config'],
        summary="Get configuration by key",
        description="Retrieve a configuration entry by its key.",
        responses={200: GlobalConfigSerializer, 404: None},
    )
    def get(self, request, key):
        """
        Get configuration by key.
        """
        config = get_object_or_404(GlobalConfig, key=key)
        serializer = GlobalConfigSerializer(config)
        return Response(serializer.data)

    @extend_schema(
        tags=['config'],
        summary="Update configuration by key",
        description="Update a configuration entry by its key.",
        request=GlobalConfigUpdateSerializer,
        responses={200: GlobalConfigSerializer, 404: None},
    )
    def put(self, request, key):
        """
        Update configuration by key.
        """
        config = get_object_or_404(GlobalConfig, key=key)
        serializer = GlobalConfigUpdateSerializer(
            config,
            data=request.data
        )
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            response_serializer = GlobalConfigSerializer(config)
            return Response(response_serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        tags=['config'],
        summary="Partially update configuration by key",
        description="Partially update a configuration entry by its key.",
        request=GlobalConfigUpdateSerializer,
        responses={200: GlobalConfigSerializer, 404: None},
    )
    def patch(self, request, key):
        """
        Partially update configuration by key.
        """
        config = get_object_or_404(GlobalConfig, key=key)
        serializer = GlobalConfigUpdateSerializer(
            config,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            response_serializer = GlobalConfigSerializer(config)
            return Response(response_serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        tags=['config'],
        summary="Delete configuration by key",
        description="Delete a configuration entry by its key.",
        responses={204: None, 404: None},
    )
    def delete(self, request, key):
        """
        Delete configuration by key.
        """
        config = get_object_or_404(GlobalConfig, key=key)
        config.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GlobalConfigByCategoryView(APIView):
    """
    List configurations by category.

    GET /api/v1/config/category/{category}/ - Get all configurations
    in a category
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['config'],
        summary="List configurations by category",
        description=(
            "Retrieve all configuration entries in a specific category."
        ),
        responses={200: GlobalConfigListSerializer(many=True)},
    )
    def get(self, request, category):
        """
        Get all configurations in a category.
        """
        configs = GlobalConfig.objects.filter(
            category=category,
            is_active=True
        ).order_by('key')
        serializer = GlobalConfigListSerializer(configs, many=True)
        return Response(serializer.data)
