"""Strict local-first API contracts; credentials are write-only."""

import json
from datetime import datetime, timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from agione_ops.models import SourceConnection


class StrictSerializer(serializers.Serializer):
    """Reject unsupported fields instead of silently widening the contract."""

    def to_internal_value(self, data):
        if isinstance(data, dict):
            writable = {
                name
                for name, field in self.fields.items()
                if not field.read_only
            }
            if set(data) - writable:
                raise serializers.ValidationError(
                    {
                        "non_field_errors": [
                            "Unsupported or read-only fields were supplied."
                        ],
                    }
                )
        return super().to_internal_value(data)


class EmptySerializer(StrictSerializer):
    """An explicit action does not accept source data or credentials."""


class ConnectionSerializer(StrictSerializer, serializers.ModelSerializer):
    """Configuration metadata with no plaintext or ciphertext response."""

    credentials = serializers.DictField(
        child=serializers.CharField(trim_whitespace=False),
        write_only=True,
        required=False,
        allow_empty=False,
    )
    has_credentials = serializers.SerializerMethodField()
    ready_for_live = serializers.SerializerMethodField()
    expected_tenant_id = serializers.CharField(max_length=160)
    synthetic_fixture = serializers.ChoiceField(
        choices=["basic"],
        default="basic",
    )

    class Meta:
        model = SourceConnection
        fields = [
            "id",
            "name",
            "platform",
            "principal_kind",
            "source_kind",
            "endpoint",
            "expected_tenant_id",
            "synthetic_fixture",
            "enabled",
            "credentials",
            "has_credentials",
            "ready_for_live",
            "verified_at",
            "credential_version",
            "config_version",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "has_credentials",
            "ready_for_live",
            "verified_at",
            "credential_version",
            "config_version",
            "created_at",
        ]

    def get_has_credentials(self, obj):
        return bool(obj.credential_ciphertext)

    def get_ready_for_live(self, obj):
        return bool(obj.source_kind == "native" and obj.enabled and
                    obj.endpoint and obj.credential_ciphertext)

    def validate_credentials(self, value):
        if len(json.dumps(value).encode("utf-8")) > 16384:
            raise serializers.ValidationError(
                "Credential payload is too large."
            )
        return value

    def validate(self, attrs):
        if attrs.get("source_kind") == "demo_snapshot" or (
            self.instance
            and self.instance.source_kind == "demo_snapshot"
            and any(key in attrs for key in ("endpoint", "credentials"))
        ):
            raise serializers.ValidationError(
                "Demo snapshots require the explicit local binding command."
            )
        if self.instance:
            stable = (
                "platform",
                "principal_kind",
                "source_kind",
                "expected_tenant_id",
            )
            if any(
                key in attrs and attrs[key] != getattr(self.instance, key)
                for key in stable
            ):
                raise serializers.ValidationError(
                    "Connection identity is immutable; create a new connection."
                )
        return attrs

    def create(self, validated_data):
        credentials = validated_data.pop("credentials", None)
        connection = SourceConnection(**validated_data)
        if credentials is not None:
            connection.set_credentials(credentials)
        connection.save()
        return connection

    def update(self, instance, validated_data):
        credentials = validated_data.pop("credentials", None)
        reverify = credentials is not None or any(
            field in validated_data
            and validated_data[field] != getattr(instance, field)
            for field in ("endpoint", "synthetic_fixture")
        )
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if credentials is not None:
            instance.set_credentials(credentials)
        if reverify:
            instance.verified_at = None
            instance.verified_tenant_id = ""
        instance.save()
        return instance


class GrantSerializer(StrictSerializer):
    """Whole-connection grants are explicit and separate from actions."""

    can_view = serializers.BooleanField()
    can_sync = serializers.BooleanField()


class AwareDateTimeField(serializers.DateTimeField):
    """DRF must not implicitly attach a timezone to a naive input."""

    def to_internal_value(self, value):
        parsed = value if isinstance(value, datetime) else None
        if isinstance(value, str):
            try:
                parsed = parse_datetime(value)
            except ValueError:
                parsed = None
        if parsed is None or timezone.is_naive(parsed):
            self.fail("invalid", format="ISO-8601 with timezone")
        if parsed.microsecond:
            raise serializers.ValidationError(
                "Only whole-second boundaries are supported."
            )
        return super().to_internal_value(value)


class SyncWindowSerializer(StrictSerializer):
    """An explicit half-open window, never a hardcoded demo date range."""

    start = AwareDateTimeField()
    end_exclusive = AwareDateTimeField()
    timezone = serializers.ChoiceField(
        choices=["Asia/Shanghai"],
        default="Asia/Shanghai",
    )

    def validate(self, attrs):
        duration = attrs["end_exclusive"] - attrs["start"]
        if not timedelta(0) < duration <= timedelta(days=31):
            raise serializers.ValidationError(
                "The window must be positive and at most 31 days."
            )
        if attrs["end_exclusive"] > timezone.now():
            raise serializers.ValidationError(
                "Future windows are not allowed."
            )
        return attrs


class SyncRequestSerializer(StrictSerializer):
    """The first local slice supports current-period synchronization only."""

    window = SyncWindowSerializer()
    kind = serializers.ChoiceField(choices=["current"], default="current")


class DashboardQuerySerializer(StrictSerializer):
    """Pin a whole-connection dataset without arbitrary customer filters."""

    data_version = serializers.UUIDField(required=False)
    window = SyncWindowSerializer(required=False)
