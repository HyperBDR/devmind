"""Serializers for external proxy admin APIs."""
from urllib.parse import urlparse

from rest_framework import serializers

from .models import ExternalSite
from .url_safety import is_blocked_host


class ExternalSiteSerializer(serializers.ModelSerializer):
    # EncryptedJSONField is backed by a TextField on the model, so DRF
    # would otherwise generate a CharField and reject dict/list input.
    # Declare the API shape as JSON to keep the public contract stable.
    token_fetch_headers = serializers.JSONField(
        required=False,
        write_only=True,
    )
    token_fetch_body = serializers.JSONField(
        required=False,
        write_only=True,
    )

    class Meta:
        model = ExternalSite
        fields = [
            "id",
            "name",
            "slug",
            "path_prefix",
            "access_mode",
            "target_host",
            "target_scheme",
            "verify_tls",
            "external_url",
            "description",
            "required_feature",
            "auth_type",
            "static_token",
            "token_fetch_url",
            "token_fetch_method",
            "token_fetch_headers",
            "token_fetch_body",
            "cached_token_expires_at",
            "hmac_secret",
            "is_active",
            "order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "path_prefix",
            "cached_token_expires_at",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "static_token": {"write_only": True},
            "hmac_secret": {"write_only": True},
        }

    def validate_slug(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Slug is required.")
        return value

    def validate_target_host(self, value):
        return (value or "").strip()

    def _validate_http_url(self, value, field_name):
        value = (value or "").strip()
        if not value:
            return value
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise serializers.ValidationError(
                f"{field_name} must be a valid http or https URL."
            )
        if is_blocked_host(parsed.hostname or ""):
            raise serializers.ValidationError(
                f"{field_name} must not point at an internal or "
                "loopback address."
            )
        return value

    def validate_external_url(self, value):
        return self._validate_http_url(value, "External URL")

    def validate_token_fetch_url(self, value):
        return self._validate_http_url(value, "Token fetch URL")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        access_mode = attrs.get(
            "access_mode",
            getattr(
                self.instance,
                "access_mode",
                ExternalSite.ACCESS_MODE_PROXY,
            ),
        )
        target_host = attrs.get(
            "target_host",
            getattr(self.instance, "target_host", ""),
        )
        external_url = attrs.get(
            "external_url",
            getattr(self.instance, "external_url", ""),
        )

        if access_mode == ExternalSite.ACCESS_MODE_PROXY and not target_host:
            raise serializers.ValidationError(
                {"target_host": "Target host is required for proxy mode."}
            )
        if access_mode != ExternalSite.ACCESS_MODE_PROXY and not external_url:
            raise serializers.ValidationError(
                {
                    "external_url": (
                        "External URL is required for this access mode."
                    )
                }
            )
        return attrs

    def update(self, instance, validated_data):
        preserved_fields = [
            "static_token",
            "hmac_secret",
            "token_fetch_headers",
            "token_fetch_body",
        ]
        for field in preserved_fields:
            value = validated_data.get(field)
            if value in ("", None, {}):
                validated_data.pop(field, None)
        return super().update(instance, validated_data)
