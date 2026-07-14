from django.contrib import admin

from .models import (
    DataOpsGlobalConfig,
    FeishuBitableCollectionConfig,
    SourceRecordChange,
    SyncCursor,
    SyncJob,
    SyncTableStatus,
)


@admin.register(SourceRecordChange)
class SourceRecordChangeAdmin(admin.ModelAdmin):
    list_display = (
        "source_key",
        "table_key",
        "source_record_id",
        "change_type",
        "detected_at",
    )
    list_filter = ("change_type", "source_key", "table_key")
    search_fields = ("source_record_id", "source_key", "table_key")
    readonly_fields = (
        "source_key",
        "table_key",
        "model_name",
        "source_record_id",
        "change_type",
        "changed_fields",
        "source_changed_fields",
        "before_values",
        "after_values",
        "source_modified_time",
        "detected_at",
    )


@admin.register(DataOpsGlobalConfig)
class DataOpsGlobalConfigAdmin(admin.ModelAdmin):
    list_display = (
        "singleton_key",
        "feishu_app_id",
        "has_feishu_app_secret",
        "feishu_date_timezone",
        "active_sync_job_timeout_hours",
        "updated_at",
    )
    readonly_fields = ("singleton_key", "created_at", "updated_at")
    search_fields = ("feishu_app_id", "feishu_date_timezone")

    def has_feishu_app_secret(self, obj):
        return bool(obj.feishu_app_secret)

    has_feishu_app_secret.boolean = True


@admin.register(FeishuBitableCollectionConfig)
class FeishuBitableCollectionConfigAdmin(admin.ModelAdmin):
    list_display = (
        "source_key",
        "table_key",
        "table_name",
        "is_enabled",
        "sync_frequency",
        "last_preflight_at",
        "last_manual_trigger_at",
        "updated_at",
    )
    list_filter = ("is_enabled", "sync_frequency")
    search_fields = ("source_key", "table_key", "table_name", "table_id")


@admin.register(SyncTableStatus)
class SyncTableStatusAdmin(admin.ModelAdmin):
    list_display = (
        "source_key",
        "table_key",
        "status",
        "issue_code",
        "record_count",
        "last_checked_at",
    )
    list_filter = ("status", "issue_code")
    search_fields = ("source_key", "table_key", "message")


@admin.register(SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    list_display = (
        "target",
        "source_key",
        "table_key",
        "status",
        "records_synced",
        "started_at",
        "finished_at",
    )
    list_filter = ("status", "source_key")
    search_fields = ("source_key", "table_key", "error_message")

    def target(self, obj):
        target = obj.source_key or "full"
        if obj.table_key:
            target = f"{target}/{obj.table_key}"
        return target


@admin.register(SyncCursor)
class SyncCursorAdmin(admin.ModelAdmin):
    list_display = (
        "source_key",
        "table_key",
        "last_sync_at",
        "last_success_at",
        "record_count",
    )
    search_fields = ("source_key", "table_key")
