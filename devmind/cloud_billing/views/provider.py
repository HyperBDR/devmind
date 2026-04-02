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


PROVIDER_CONFIG_SCHEMAS = {
    "aws": {
        "provider_type": "aws",
        "display_name": "AWS",
        "description": (
            "Use AWS Cost Explorer to collect monthly billing data."
        ),
        "required_fields": [
            {
                "name": "AWS_ACCESS_KEY_ID",
                "backend_name": "api_key",
                "label": "Access Key ID",
                "type": "string",
            },
            {
                "name": "AWS_SECRET_ACCESS_KEY",
                "backend_name": "api_secret",
                "label": "Secret Access Key",
                "type": "password",
            },
            {
                "name": "AWS_REGION",
                "backend_name": "region",
                "label": "Region",
                "type": "string",
                "default": "cn-north-1",
            },
        ],
        "optional_fields": [],
    },
    "huawei": {
        "provider_type": "huawei",
        "display_name": "Huawei Cloud (China)",
        "description": (
            "Use Huawei Cloud BSS API to collect monthly billing data."
        ),
        "required_fields": [
            {
                "name": "HUAWEI_ACCESS_KEY_ID",
                "backend_name": "api_key",
                "label": "Access Key ID",
                "type": "string",
            },
            {
                "name": "HUAWEI_SECRET_ACCESS_KEY",
                "backend_name": "api_secret",
                "label": "Secret Access Key",
                "type": "password",
            },
            {
                "name": "HUAWEI_REGION",
                "backend_name": "region",
                "label": "Region",
                "type": "string",
                "default": "cn-north-1",
            },
        ],
        "optional_fields": [
            {
                "name": "HUAWEI_PROJECT_ID",
                "backend_name": "project_id",
                "label": "Project ID",
                "type": "string",
            },
        ],
    },
    "huawei-intl": {
        "provider_type": "huawei-intl",
        "display_name": "Huawei Cloud (International)",
        "description": (
            "Use Huawei Cloud international BSS API to "
            "collect monthly billing data."
        ),
        "required_fields": [
            {
                "name": "HUAWEI_ACCESS_KEY_ID",
                "backend_name": "api_key",
                "label": "Access Key ID",
                "type": "string",
            },
            {
                "name": "HUAWEI_SECRET_ACCESS_KEY",
                "backend_name": "api_secret",
                "label": "Secret Access Key",
                "type": "password",
            },
            {
                "name": "HUAWEI_REGION",
                "backend_name": "region",
                "label": "Region",
                "type": "string",
            },
        ],
        "optional_fields": [
            {
                "name": "HUAWEI_PROJECT_ID",
                "backend_name": "project_id",
                "label": "Project ID",
                "type": "string",
            },
        ],
    },
    "alibaba": {
        "provider_type": "alibaba",
        "display_name": "Alibaba Cloud",
        "description": (
            "Use Alibaba Cloud BSS OpenAPI to collect monthly billing data."
        ),
        "required_fields": [
            {
                "name": "ALIBABA_ACCESS_KEY_ID",
                "backend_name": "api_key",
                "label": "Access Key ID",
                "type": "string",
            },
            {
                "name": "ALIBABA_ACCESS_KEY_SECRET",
                "backend_name": "api_secret",
                "label": "Access Key Secret",
                "type": "password",
            },
            {
                "name": "ALIBABA_REGION",
                "backend_name": "region",
                "label": "Region",
                "type": "string",
                "default": "cn-hangzhou",
            },
        ],
        "optional_fields": [],
    },
    "azure": {
        "provider_type": "azure",
        "display_name": "Azure",
        "description": (
            "Use Azure Consumption API to collect monthly billing data."
        ),
        "required_fields": [
            {
                "name": "AZURE_TENANT_ID",
                "backend_name": "tenant_id",
                "label": "Tenant ID",
                "type": "string",
            },
            {
                "name": "AZURE_CLIENT_ID",
                "backend_name": "client_id",
                "label": "Client ID",
                "type": "string",
            },
            {
                "name": "AZURE_CLIENT_SECRET",
                "backend_name": "client_secret",
                "label": "Client Secret",
                "type": "password",
            },
            {
                "name": "AZURE_SUBSCRIPTION_ID",
                "backend_name": "subscription_id",
                "label": "Subscription ID",
                "type": "string",
            },
        ],
        "optional_fields": [],
    },
    "tencentcloud": {
        "provider_type": "tencentcloud",
        "display_name": "Tencent Cloud",
        "description": (
            "Use Tencent Cloud Billing API to collect monthly billing data."
        ),
        "required_fields": [
            {
                "name": "TENCENT_ACCESS_KEY_ID",
                "backend_name": "access_key_id",
                "label": "Access Key ID",
                "type": "string",
            },
            {
                "name": "TENCENT_ACCESS_KEY_SECRET",
                "backend_name": "access_key_secret",
                "label": "Access Key Secret",
                "type": "password",
            },
            {
                "name": "TENCENT_APP_ID",
                "backend_name": "app_id",
                "label": "App ID",
                "type": "string",
            },
        ],
        "optional_fields": [
            {
                "name": "TENCENT_REGION",
                "backend_name": "region",
                "label": "Region",
                "type": "string",
                "default": "ap-guangzhou",
            },
            {
                "name": "TENCENT_ENDPOINT",
                "backend_name": "endpoint",
                "label": "Endpoint",
                "type": "string",
                "default": "billing.tencentcloudapi.com",
            },
            {
                "name": "TENCENT_TIMEOUT",
                "backend_name": "timeout",
                "label": "Timeout",
                "type": "integer",
                "default": 30,
            },
            {
                "name": "TENCENT_MAX_RETRIES",
                "backend_name": "max_retries",
                "label": "Max Retries",
                "type": "integer",
                "default": 3,
            },
        ],
    },
    "volcengine": {
        "provider_type": "volcengine",
        "display_name": "Volcengine",
        "description": (
            "Use Volcengine Billing OpenAPI to collect monthly bill data."
        ),
        "required_fields": [
            {
                "name": "VOLCENGINE_ACCESS_KEY_ID",
                "backend_name": "api_key",
                "label": "Access Key ID",
                "type": "string",
            },
            {
                "name": "VOLCENGINE_SECRET_ACCESS_KEY",
                "backend_name": "api_secret",
                "label": "Secret Access Key",
                "type": "password",
            },
        ],
        "optional_fields": [
            {
                "name": "VOLCENGINE_REGION",
                "backend_name": "region",
                "label": "Region",
                "type": "string",
                "default": "cn-north-1",
            },
            {
                "name": "VOLCENGINE_ENDPOINT",
                "backend_name": "endpoint",
                "label": "Endpoint",
                "type": "string",
                "default": "https://billing.volcengineapi.com",
            },
            {
                "name": "VOLCENGINE_PAYER_ID",
                "backend_name": "payer_id",
                "label": "Payer ID",
                "type": "string",
            },
            {
                "name": "VOLCENGINE_SERVICE",
                "backend_name": "service",
                "label": "Service",
                "type": "string",
                "default": "billing",
            },
            {
                "name": "VOLCENGINE_VERSION",
                "backend_name": "version",
                "label": "Version",
                "type": "string",
                "default": "2022-01-01",
            },
        ],
    },
    "baidu": {
        "provider_type": "baidu",
        "display_name": "Baidu AI Cloud",
        "description": (
            "Use Baidu Cloud Finance OpenAPI to collect monthly billing "
            "data and account balance."
        ),
        "required_fields": [
            {
                "name": "BAIDU_ACCESS_KEY_ID",
                "backend_name": "api_key",
                "label": "Access Key ID",
                "type": "string",
            },
            {
                "name": "BAIDU_SECRET_ACCESS_KEY",
                "backend_name": "api_secret",
                "label": "Secret Access Key",
                "type": "password",
            },
        ],
        "optional_fields": [
            {
                "name": "BAIDU_TIMEOUT",
                "backend_name": "timeout",
                "label": "Timeout",
                "type": "integer",
                "default": 30,
            },
            {
                "name": "BAIDU_MAX_RETRIES",
                "backend_name": "max_retries",
                "label": "Max Retries",
                "type": "integer",
                "default": 3,
            },
        ],
    },
    "zhipu": {
        "provider_type": "zhipu",
        "display_name": "Zhipu AI",
        "description": (
            "Use Zhipu BigModel web finance endpoints to collect monthly "
            "billing data and account balance."
        ),
        "required_fields": [
            {
                "name": "ZHIPU_USERNAME",
                "backend_name": "username",
                "label": "Username",
                "type": "string",
            },
            {
                "name": "ZHIPU_PASSWORD",
                "backend_name": "password",
                "label": "Password",
                "type": "password",
            },
        ],
        "optional_fields": [
            {
                "name": "ZHIPU_USER_TYPE",
                "backend_name": "user_type",
                "label": "User Type",
                "type": "string",
                "default": "PERSONAL",
            },
            {
                "name": "ZHIPU_TIMEOUT",
                "backend_name": "timeout",
                "label": "Timeout",
                "type": "integer",
                "default": 30,
            },
            {
                "name": "ZHIPU_MAX_RETRIES",
                "backend_name": "max_retries",
                "label": "Max Retries",
                "type": "integer",
                "default": 3,
            },
        ],
    },
}


@extend_schema_view(
    list=extend_schema(
        tags=["cloud-billing"],
        summary="List all cloud providers",
        description="Retrieve a list of all cloud provider configurations.",
    ),
    retrieve=extend_schema(
        tags=["cloud-billing"],
        summary="Retrieve a cloud provider",
        description=(
            "Get detailed information about a specific cloud provider."
        ),
    ),
    create=extend_schema(
        tags=["cloud-billing"],
        summary="Create a cloud provider",
        description="Create a new cloud provider configuration.",
    ),
    update=extend_schema(
        tags=["cloud-billing"],
        summary="Update a cloud provider",
        description="Update an existing cloud provider configuration.",
    ),
    partial_update=extend_schema(
        tags=["cloud-billing"],
        summary="Partially update a cloud provider",
        description=(
            "Partially update an existing cloud provider configuration."
        ),
    ),
    destroy=extend_schema(
        tags=["cloud-billing"],
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
        if self.action == "list":
            return CloudProviderListSerializer
        return CloudProviderSerializer

    def get_queryset(self):
        """
        Optionally filter by provider_type and is_active.
        """
        queryset = CloudProvider.objects.all()
        provider_type = self.request.query_params.get("provider_type", None)
        is_active = self.request.query_params.get("is_active", None)

        if provider_type:
            queryset = queryset.filter(provider_type=provider_type)
        if is_active is not None:
            is_active_bool = is_active.lower() == "true"
            queryset = queryset.filter(is_active=is_active_bool)

        return queryset.order_by("name")

    def perform_create(self, serializer):
        """
        Set created_by and updated_by to current user when creating.
        Auto-generate name if not provided.
        """
        data = serializer.validated_data

        # Auto-generate name if not provided or empty
        name = None
        if data.get("name"):
            provided_name = data.get("name", "").strip()
        else:
            provided_name = ""

        if not provided_name:
            if not data.get("display_name"):
                raise serializers.ValidationError(
                    {
                        "display_name": (
                            "Display name is required when "
                            "name is not provided."
                        )
                    }
                )

            provider_type = data.get("provider_type", "")
            display_name = data.get("display_name", "")

            # Convert display name to lowercase and replace spaces
            # with underscores
            base_name = re.sub(r"[^a-z0-9]+", "_", display_name.lower()).strip(
                "_"
            )

            # Add provider type prefix if not already present
            type_prefix = provider_type.replace("-", "_")
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
            "created_by": self.request.user,
            "updated_by": self.request.user,
            "name": name,
        }

        serializer.save(**save_kwargs)

    def perform_update(self, serializer):
        """
        Set updated_by to current user when updating.
        """
        serializer.save(updated_by=self.request.user)

    @extend_schema(
        tags=["cloud-billing"],
        summary="Validate provider credentials",
        description=(
            "Validate the authentication credentials for a cloud provider."
        ),
        responses={200: {"type": "object"}},
    )
    @action(detail=True, methods=["post"])
    def validate(self, request, pk=None):
        """
        Validate provider credentials.
        """
        provider = self.get_object()

        try:
            provider_service = ProviderService()
            result = provider_service.validate_credentials(
                provider.provider_type, provider.config
            )

            if result.get("valid"):
                return Response(
                    {
                        "valid": True,
                        "message": "Credentials are valid",
                        "account_id": result.get("account_id", ""),
                    }
                )
            else:
                error_msg = result.get(
                    "message", "Credentials validation failed"
                )
                return Response(
                    {
                        "valid": False,
                        "message": error_msg,
                        "account_id": "",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            return Response(
                {
                    "valid": False,
                    "message": str(e),
                    "account_id": "",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        tags=["cloud-billing"],
        summary="Get cloud provider config schemas",
        description=(
            "Return form schemas for supported cloud provider billing drivers."
        ),
        responses={200: {"type": "object"}},
    )
    @action(detail=False, methods=["get"], url_path="config-schemas")
    def config_schemas(self, request):
        provider_type = request.query_params.get("provider_type")
        if provider_type:
            schema = PROVIDER_CONFIG_SCHEMAS.get(provider_type)
            if not schema:
                return Response(
                    {"detail": "Unknown provider_type."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response({"provider": schema})
        return Response(
            {
                "providers": [
                    PROVIDER_CONFIG_SCHEMAS[key]
                    for key in sorted(PROVIDER_CONFIG_SCHEMAS.keys())
                ]
            }
        )

    @extend_schema(
        tags=["cloud-billing"],
        summary="List provider tags",
        description=(
            "Return a de-duplicated list of all cloud provider tags for tag "
            "selection UIs."
        ),
        responses={200: {"type": "object"}},
    )
    @action(detail=False, methods=["get"], url_path="tags")
    def tags(self, request):
        tag_set = set()
        for provider in CloudProvider.objects.only("tags"):
            for tag in provider.tags or []:
                normalized = str(tag or "").strip()
                if normalized:
                    tag_set.add(normalized)

        return Response({"tags": sorted(tag_set, key=lambda value: (value.lower(), value))})

    @extend_schema(
        tags=["cloud-billing"],
        summary="Validate provider configuration",
        description=(
            "Validate provider configuration without saving to database."
        ),
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "provider_type": {"type": "string"},
                    "config": {"type": "object"},
                },
                "required": ["provider_type", "config"],
            }
        },
        responses={200: {"type": "object"}},
    )
    @action(detail=False, methods=["post"], url_path="validate-config")
    def validate_config(self, request):
        """
        Validate provider configuration without saving.
        """
        provider_type = request.data.get("provider_type")
        config = request.data.get("config")

        if not provider_type:
            return Response(
                {
                    "valid": False,
                    "message": "provider_type is required",
                    "account_id": "",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if config is None:
            return Response(
                {
                    "valid": False,
                    "message": "config is required",
                    "account_id": "",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            logger = logging.getLogger(__name__)
            sanitized_config = mask_sensitive_config(config)
            logger.info(
                f"validate_config called with provider_type={provider_type}, "
                f"config={sanitized_config}"
            )
            provider_service = ProviderService()
            result = provider_service.validate_credentials(
                provider_type, config
            )

            response_data = {
                "valid": result.get("valid", False),
                "error_code": result.get("error_code"),
                "account_id": result.get("account_id", ""),
            }
            if result.get("message"):
                response_data["message"] = result["message"]
            return Response(response_data)
        except Exception as e:
            return Response(
                {
                    "valid": False,
                    "message": str(e),
                    "account_id": "",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
