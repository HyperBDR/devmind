from rest_framework import serializers

from .models import CollectionTask, DataSource, Host, License, Tenant


class DataSourceSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )

    class Meta:
        model = DataSource
        fields = [
            "id",
            "name",
            "api_url",
            "username",
            "password",
            "is_active",
            "api_timeout",
            "api_retry_count",
            "api_retry_delay",
            "collect_interval",
            "last_collected_at",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        payload = super().to_representation(instance)
        # Password is stored as plaintext; return it as-is for read operations
        payload["password"] = instance.password or ""
        return payload


class TenantSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="source_tenant_id", read_only=True)
    data_source_id = serializers.IntegerField(read_only=True)
    host_count = serializers.IntegerField(read_only=True)
    license_total = serializers.IntegerField(read_only=True)
    license_used = serializers.IntegerField(read_only=True)
    license_remaining = serializers.IntegerField(read_only=True)
    data_source_name = serializers.CharField(source="data_source.name", read_only=True)

    class Meta:
        model = Tenant
        fields = [
            "id",
            "data_source_id",
            "data_source_name",
            "name",
            "description",
            "status",
            "agent_enabled",
            "trialed",
            "migration_way",
            "host_count",
            "license_total",
            "license_used",
            "license_remaining",
            "last_collected_at",
            "created_at",
            "updated_at",
        ]


class LicenseSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(source="tenant.source_tenant_id", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    data_source_id = serializers.IntegerField(read_only=True)
    data_source_name = serializers.CharField(source="data_source.name", read_only=True)
    usage_ratio = serializers.SerializerMethodField()

    class Meta:
        model = License
        fields = [
            "id",
            "data_source_id",
            "data_source_name",
            "tenant_id",
            "tenant_name",
            "total_amount",
            "total_used",
            "total_unused",
            "scene",
            "start_at",
            "expire_at",
            "usage_ratio",
            "last_collected_at",
            "created_at",
            "updated_at",
        ]

    def get_usage_ratio(self, obj):
        if not obj.total_amount:
            return 0
        return round((obj.total_used / obj.total_amount) * 100, 2)


class HostSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="source_host_id", read_only=True)
    tenant_id = serializers.CharField(source="tenant.source_tenant_id", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    data_source_id = serializers.IntegerField(read_only=True)
    data_source_name = serializers.CharField(source="data_source.name", read_only=True)

    class Meta:
        model = Host
        fields = [
            "id",
            "data_source_id",
            "data_source_name",
            "tenant_id",
            "tenant_name",
            "name",
            "status",
            "boot_status",
            "health_status",
            "os_type",
            "host_type",
            "cpu_num",
            "ram_size",
            "license_valid",
            "error_message",
            "last_collected_at",
            "created_at",
            "updated_at",
        ]


class CollectionTaskSerializer(serializers.ModelSerializer):
    data_source_id = serializers.IntegerField(read_only=True)
    data_source_name = serializers.CharField(source="data_source.name", read_only=True)

    class Meta:
        model = CollectionTask
        fields = [
            "id",
            "data_source_id",
            "data_source_name",
            "status",
            "celery_task_id",
            "trigger_mode",
            "start_time",
            "end_time",
            "duration_seconds",
            "total_tenants",
            "total_licenses",
            "total_hosts",
            "error_message",
            "created_at",
            "updated_at",
        ]
