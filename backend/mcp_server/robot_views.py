"""Administrator APIs for issuing and revoking MCP robot credentials."""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.access import get_effective_feature_keys
from invoice.permissions import has_invoice_access
from mcp_server.models import McpRobotCredential
from quotation.permissions import (
    get_quotation_platform_role,
    is_quotation_platform_admin,
)

ROBOT_SCOPES = ("quotation:read", "invoice:read")
DEFAULT_EXPIRY_DAYS = 90
MAX_EXPIRY_DAYS = 365


def _digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class IsMcpRobotAdmin(BasePermission):
    """Allow the administrators who manage the access page."""

    def has_permission(self, request, view):
        return is_quotation_platform_admin(request.user)


class RobotCredentialCreateSerializer(serializers.Serializer):
    """Validate a robot's principal, read-only modules, and lifetime."""

    name = serializers.CharField(max_length=120, trim_whitespace=True)
    user_id = serializers.IntegerField(min_value=1)
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=ROBOT_SCOPES),
        required=False,
        allow_empty=False,
    )
    expires_in_days = serializers.IntegerField(
        default=DEFAULT_EXPIRY_DAYS,
        min_value=1,
        max_value=MAX_EXPIRY_DAYS,
    )

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("A name is required.")
        return value.strip()

    def validate_scopes(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "Duplicate scopes are not allowed."
            )
        return value

    def validate(self, attrs):
        user = get_user_model().objects.filter(
            pk=attrs["user_id"],
            is_active=True,
        ).first()
        if user is None:
            raise serializers.ValidationError(
                {"user_id": "Select an active DevMind account."}
            )

        available_scopes = []
        if (
            "quotation_management" in get_effective_feature_keys(user)
            and get_quotation_platform_role(user)
        ):
            available_scopes.append("quotation:read")
        if has_invoice_access(user):
            available_scopes.append("invoice:read")
        if not available_scopes:
            raise serializers.ValidationError(
                {"user_id": "The selected account has no MCP read access."}
            )

        requested = attrs.get("scopes")
        if requested is None:
            attrs["scopes"] = available_scopes
        elif not set(requested).issubset(available_scopes):
            raise serializers.ValidationError(
                {"scopes": "The selected account lacks a requested access."}
            )
        attrs["user"] = user
        return attrs


def _credential_data(credential):
    return {
        "id": str(credential.pk),
        "name": credential.name,
        "user_id": credential.user_id,
        "username": credential.user.get_username(),
        "scopes": credential.scopes,
        "created_at": credential.created_at,
        "expires_at": credential.expires_at,
        "last_used_at": credential.last_used_at,
        "revoked_at": credential.revoked_at,
    }


class McpRobotCredentialListView(APIView):
    """List robot credentials or issue a new secret shown only once."""

    permission_classes = [IsMcpRobotAdmin]

    def get(self, request):
        credentials = McpRobotCredential.objects.select_related(
            "user"
        ).all()
        return Response(
            {"results": [_credential_data(item) for item in credentials]}
        )

    def post(self, request):
        serializer = RobotCredentialCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        raw_token = f"dmrobot_{secrets.token_urlsafe(36)}"
        credential = McpRobotCredential.objects.create(
            name=values["name"],
            user=values["user"],
            token_hash=_digest(raw_token),
            scopes=values["scopes"],
            resource=settings.MCP_OAUTH_RESOURCE_URL.rstrip("/"),
            issuer=settings.MCP_OAUTH_ISSUER_URL,
            created_by=request.user,
            expires_at=timezone.now()
            + timedelta(days=values["expires_in_days"]),
        )
        return Response(
            {**_credential_data(credential), "token": raw_token},
            status=status.HTTP_201_CREATED,
        )


class McpRobotCredentialDetailView(APIView):
    """Revoke a robot credential without exposing its secret again."""

    permission_classes = [IsMcpRobotAdmin]

    def delete(self, request, credential_id):
        credential = McpRobotCredential.objects.filter(
            pk=credential_id,
            revoked_at__isnull=True,
        ).first()
        if credential is None:
            return Response(
                {"detail": "Robot credential not found or already revoked."},
                status=status.HTTP_404_NOT_FOUND,
            )
        credential.revoked_at = timezone.now()
        credential.save(update_fields=["revoked_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
