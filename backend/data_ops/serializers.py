from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework import serializers

from .models import (
    Contract,
    DataOpsGlobalConfig,
    FeishuBitableCollectionConfig,
    SalesRecord,
    SyncCursor,
    SyncJob,
    SyncTableStatus,
)
from .services.feishu.client import build_bitable_table_url


class DataOpsGlobalConfigSerializer(serializers.ModelSerializer):
    feishu_app_secret = serializers.CharField(
        allow_blank=True,
        required=False,
        write_only=True,
    )
    has_feishu_app_secret = serializers.SerializerMethodField()

    class Meta:
        model = DataOpsGlobalConfig
        fields = [
            "feishu_app_id",
            "feishu_app_secret",
            "has_feishu_app_secret",
            "feishu_date_timezone",
            "active_sync_job_timeout_hours",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "has_feishu_app_secret",
            "created_at",
            "updated_at",
        ]

    def get_has_feishu_app_secret(self, obj):
        return bool(obj.feishu_app_secret)

    def validate_feishu_date_timezone(self, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise serializers.ValidationError(
                "Use a valid IANA timezone name."
            ) from exc
        return value

    def validate_active_sync_job_timeout_hours(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "Timeout must be at least 1 hour."
            )
        return value

    def update(self, instance, validated_data):
        secret = validated_data.pop("feishu_app_secret", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if secret:
            instance.set_feishu_app_secret(secret)
        instance.save()
        return instance


class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = [
            "id",
            "contract_number",
            "customer_name",
            "signing_entity",
            "channel_type",
            "enduser_customer",
            "order_platform",
            "sales_person",
            "region",
            "currency",
            "total_amount",
            "product_category",
            "signing_type",
            "signing_date",
            "service_start",
            "service_end",
            "status",
            "filing_type",
            "contract_sub_type",
            "expiry_status",
            "source_record_id",
            "synced_at",
        ]


class SalesRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesRecord
        fields = [
            "id",
            "project_name",
            "po_number",
            "region",
            "product_type",
            "total_amount_usd",
            "allocation_date",
            "expiry_date",
            "order_type",
            "status",
            "sales_person",
            "source_record_id",
            "synced_at",
        ]


class SyncTableStatusSerializer(serializers.ModelSerializer):
    table_url = serializers.SerializerMethodField()

    class Meta:
        model = SyncTableStatus
        fields = [
            "source_key",
            "table_key",
            "table_name",
            "table_url",
            "status",
            "issue_code",
            "message",
            "resolution_hint",
            "expected_fields",
            "missing_fields",
            "expected_min_records",
            "expected_record_floor",
            "record_count",
            "last_checked_at",
            "last_success_at",
        ]

    def get_table_url(self, obj):
        return build_bitable_table_url(obj.app_token, obj.table_id)


class SyncCursorSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncCursor
        fields = [
            "source_key",
            "table_key",
            "table_name",
            "last_sync_at",
            "last_success_at",
            "record_count",
        ]


class SyncJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncJob
        fields = [
            "id",
            "source_key",
            "table_key",
            "status",
            "started_at",
            "finished_at",
            "records_synced",
            "error_message",
            "celery_task_id",
            "results",
        ]


class SyncTriggerSerializer(serializers.Serializer):
    force = serializers.BooleanField(default=True)


class FeishuBitableCollectionConfigSerializer(serializers.ModelSerializer):
    sync_status = serializers.SerializerMethodField()
    issue_code = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()
    resolution_hint = serializers.SerializerMethodField()
    record_count = serializers.SerializerMethodField()
    last_checked_at = serializers.SerializerMethodField()
    last_success_at = serializers.SerializerMethodField()
    table_url = serializers.SerializerMethodField()

    class Meta:
        model = FeishuBitableCollectionConfig
        fields = [
            "id",
            "source_key",
            "table_key",
            "source_name",
            "table_name",
            "table_url",
            "app_token",
            "table_id",
            "is_enabled",
            "sync_frequency",
            "required_permissions",
            "expected_min_records",
            "last_preflight_at",
            "last_manual_trigger_at",
            "last_scheduled_at",
            "sync_status",
            "issue_code",
            "message",
            "resolution_hint",
            "record_count",
            "last_checked_at",
            "last_success_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "source_key",
            "table_key",
            "last_preflight_at",
            "last_manual_trigger_at",
            "last_scheduled_at",
            "created_at",
            "updated_at",
            "sync_status",
            "issue_code",
            "message",
            "resolution_hint",
            "record_count",
            "last_checked_at",
            "last_success_at",
            "table_url",
        ]

    def _status(self, obj):
        cache = getattr(self, "_status_cache", None)
        if cache is None:
            cache = {
                (item.source_key, item.table_key): item
                for item in SyncTableStatus.objects.all()
            }
            self._status_cache = cache
        return cache.get((obj.source_key, obj.table_key))

    def get_sync_status(self, obj):
        status = self._status(obj)
        return status.status if status else "pending"

    def get_issue_code(self, obj):
        status = self._status(obj)
        return status.issue_code if status else ""

    def get_message(self, obj):
        status = self._status(obj)
        return status.message if status else ""

    def get_resolution_hint(self, obj):
        status = self._status(obj)
        return status.resolution_hint if status else ""

    def get_record_count(self, obj):
        status = self._status(obj)
        return status.record_count if status else 0

    def get_last_checked_at(self, obj):
        status = self._status(obj)
        return status.last_checked_at if status else None

    def get_last_success_at(self, obj):
        status = self._status(obj)
        return status.last_success_at if status else None

    def get_table_url(self, obj):
        return build_bitable_table_url(obj.app_token, obj.table_id)
