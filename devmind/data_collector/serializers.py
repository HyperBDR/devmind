"""
Serializers for data_collector API. UUID in responses; optimistic lock.
"""
from rest_framework import serializers
from rest_framework.exceptions import APIException

from .models import CollectorConfig, RawDataAttachment, RawDataRecord


class Conflict(APIException):
    """409 Conflict for version mismatch on config update."""

    status_code = 409


def _default_runtime_state():
    return {
        "first_collect_at": None,
        "last_collect_start_at": None,
        "last_collect_end_at": None,
        "last_success_collect_at": None,
        "last_validate_at": None,
        "last_cleanup_at": None,
    }


class CollectorConfigSerializer(serializers.ModelSerializer):
    """
    Full serializer for CollectorConfig. Exposes uuid; value has runtime_state.
    On update, client must send current version for optimistic lock.
    """

    class Meta:
        model = CollectorConfig
        fields = [
            "uuid",
            "user",
            "platform",
            "key",
            "value",
            "is_enabled",
            "version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["uuid", "user", "created_at", "updated_at"]

    def update(self, instance, validated_data):
        version_sent = validated_data.pop("version", None)
        if version_sent is not None and version_sent != instance.version:
            raise Conflict(
                detail=("Config was modified (version mismatch).")
            )
        if "value" in validated_data:
            incoming = validated_data["value"]
            current = instance.value or {}
            merged = {**current, **incoming}
            rt = current.get("runtime_state") or _default_runtime_state()
            merged["runtime_state"] = rt
            current_auth = current.get("auth") or {}
            incoming_auth = incoming.get("auth")
            ok_auth = (
                isinstance(incoming_auth, dict)
                and isinstance(current_auth, dict)
            )
            if ok_auth:
                merged_auth = {**current_auth, **incoming_auth}
                for key in ("password", "api_token"):
                    if not (merged_auth.get(key) or "").strip():
                        merged_auth[key] = current_auth.get(key) or ""
                merged["auth"] = merged_auth
            validated_data["value"] = merged
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.version += 1
        instance.save()
        return instance

    def validate_value(self, data):
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                {"value": ["value must be a JSON object."]}
            )
        runtime = data.get("runtime_state")
        if runtime is not None and not isinstance(runtime, dict):
            raise serializers.ValidationError(
                {"value": ["value.runtime_state must be a JSON object."]}
            )
        if runtime is None:
            data = {**data, "runtime_state": _default_runtime_state()}
        else:
            for key in _default_runtime_state():
                if key not in runtime:
                    runtime[key] = None
        return data


class CollectorConfigListSerializer(serializers.ModelSerializer):
    """
    List view: uuid, platform, key, is_enabled, version, updated_at.
    """

    class Meta:
        model = CollectorConfig
        fields = [
            "uuid",
            "platform",
            "key",
            "is_enabled",
            "version",
            "updated_at",
        ]


def _record_display_title(raw_data, source_unique_id, platform):
    """
    Extract a human-readable title from raw_data for list display.
    Jira: issue.fields.summary; others: fallback to source_unique_id.
    """
    if not raw_data:
        return source_unique_id or ""
    if platform == "jira":
        issue = raw_data.get("issue") or {}
        fields = issue.get("fields") or {}
        summary = fields.get("summary")
        if summary:
            return summary
    return source_unique_id or ""


class RawDataRecordListSerializer(serializers.ModelSerializer):
    """
    List view for RawDataRecord: uuid, platform, source_unique_id,
    display_title, filter_metadata, attachment_count.
    """

    display_title = serializers.SerializerMethodField()
    attachment_count = serializers.SerializerMethodField()

    class Meta:
        model = RawDataRecord
        fields = [
            "uuid",
            "platform",
            "source_unique_id",
            "display_title",
            "filter_metadata",
            "attachment_count",
            "data_hash",
            "is_deleted",
            "source_created_at",
            "source_updated_at",
            "first_collected_at",
            "last_collected_at",
            "created_at",
            "updated_at",
        ]

    def get_display_title(self, obj):
        raw = getattr(obj, "raw_data", None) or {}
        sid = getattr(obj, "source_unique_id", None) or ""
        plat = getattr(obj, "platform", None) or ""
        return _record_display_title(raw, sid, plat)

    def get_attachment_count(self, obj):
        raw_data = getattr(obj, "raw_data", None) or {}
        attachments = raw_data.get("attachments")
        if isinstance(attachments, list):
            return len(attachments)
        return 0


class RawDataRecordDetailSerializer(serializers.ModelSerializer):
    """
    Detail view: full raw_data and nested attachments (uuid, file_name, url).
    """

    attachments = serializers.SerializerMethodField()

    class Meta:
        model = RawDataRecord
        fields = [
            "uuid",
            "user",
            "platform",
            "source_unique_id",
            "raw_data",
            "filter_metadata",
            "data_hash",
            "is_deleted",
            "source_created_at",
            "source_updated_at",
            "first_collected_at",
            "last_collected_at",
            "created_at",
            "updated_at",
            "attachments",
        ]

    def get_attachments(self, obj):
        def row(a):
            return {
                "uuid": str(a.uuid),
                "file_name": a.file_name,
                "file_url": a.file_url,
                "file_type": a.file_type or "",
                "file_size": a.file_size or 0,
                "source_created_at": a.source_created_at,
                "created_at": a.created_at,
            }
        return [row(a) for a in obj.attachments.all()]


class RawDataAttachmentSerializer(serializers.ModelSerializer):
    """
    Attachment list/detail: uuid, file_name, file_url, file_type, file_size.
    """

    class Meta:
        model = RawDataAttachment
        fields = [
            "uuid",
            "file_name",
            "file_url",
            "file_type",
            "file_size",
            "file_md5",
            "source_created_at",
            "source_updated_at",
            "created_at",
            "updated_at",
        ]
