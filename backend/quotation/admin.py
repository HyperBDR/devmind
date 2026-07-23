from django.contrib import admin

from quotation.audit import record_audit_event
from quotation.models import (
    AuditEvent,
    DocumentAsset,
    DocumentParseResult,
    DocumentReplica,
    FeishuConnection,
    Quotation,
    QuotationItem,
    QuotationVersion,
    StorageConnection,
    StorageMount,
    SyncJob,
    UserQuotationCatalog,
)
from quotation.services.feishu_client import FeishuAPIError
from quotation.services.storage_control import (
    FeishuStorageProvider,
    StorageRoute,
    create_replica,
    revoke_replica,
)

admin.site.register(Quotation)
admin.site.register(QuotationItem)
admin.site.register(QuotationVersion)
admin.site.register(DocumentAsset)
admin.site.register(DocumentParseResult)
admin.site.register(FeishuConnection)
admin.site.register(UserQuotationCatalog)


@admin.register(StorageConnection)
class StorageConnectionAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "provider",
        "external_tenant_id",
        "auth_mode",
        "status",
        "is_default",
        "last_health_checked_at",
    )
    list_filter = ("provider", "auth_mode", "status", "is_default")
    search_fields = ("display_name", "external_tenant_id", "app_id")
    exclude = ("access_token", "refresh_token")
    actions = ("check_connection_health", "disable_connections")

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change:
            previous_status = StorageConnection.objects.filter(
                pk=obj.pk
            ).values_list("status", flat=True).first()
        super().save_model(request, obj, form, change)
        if not change:
            event_name = "storage.connection_created"
            action = "connection_created"
        elif {"app_secret", "app_id"}.intersection(form.changed_data):
            event_name = "storage.connection_credential_rotated"
            action = "credential_rotated"
        elif previous_status != "disabled" and obj.status == "disabled":
            event_name = "storage.connection_disabled"
            action = "connection_disabled"
        else:
            event_name = "storage.connection_updated"
            action = "connection_updated"
        record_audit_event(
            request=request,
            module="storage",
            action=action,
            event_name=event_name,
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="storage_connection",
            target_id=obj.id,
            target_label=obj.display_name,
            storage_connection_id=obj.id,
            changes={"fields": list(form.changed_data)},
        )

    @admin.action(description="Check selected connection health")
    def check_connection_health(self, request, queryset):
        for connection in queryset:
            mount = connection.mounts.filter(enabled=True).first()
            if mount is None:
                continue
            result = AuditEvent.RESULT_SUCCEEDED
            error_code = ""
            try:
                FeishuStorageProvider(connection).health_check(mount)
            except FeishuAPIError as exc:
                result = AuditEvent.RESULT_FAILED
                error_code = (
                    f"feishu_{exc.code}"
                    if exc.code is not None
                    else "feishu_health_failed"
                )
            record_audit_event(
                request=request,
                module="storage",
                action="health_checked",
                event_name="storage.connection_health_checked",
                result=result,
                target_type="storage_connection",
                target_id=connection.id,
                target_label=connection.display_name,
                storage_connection_id=connection.id,
                error_code=error_code,
            )

    @admin.action(description="Disable selected connections")
    def disable_connections(self, request, queryset):
        for connection in queryset.exclude(status="disabled"):
            connection.status = "disabled"
            connection.save(update_fields=["status", "updated_at"])
            record_audit_event(
                request=request,
                module="storage",
                action="connection_disabled",
                event_name="storage.connection_disabled",
                result=AuditEvent.RESULT_SUCCEEDED,
                target_type="storage_connection",
                target_id=connection.id,
                target_label=connection.display_name,
                storage_connection_id=connection.id,
            )


@admin.register(StorageMount)
class StorageMountAdmin(admin.ModelAdmin):
    list_display = (
        "root_folder_name",
        "connection",
        "scope_key",
        "purpose",
        "document_type",
        "enabled",
        "is_default",
    )
    list_filter = ("purpose", "document_type", "enabled", "is_default")
    search_fields = ("root_folder_name", "root_folder_token", "scope_key")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_audit_event(
            request=request,
            module="storage",
            action="mount_updated" if change else "mount_created",
            event_name=(
                "storage.mount_updated" if change else "storage.mount_created"
            ),
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="storage_mount",
            target_id=obj.id,
            target_label=obj.root_folder_name,
            storage_connection_id=obj.connection_id,
            changes={"fields": list(form.changed_data)},
        )

    def delete_model(self, request, obj):
        target_id = obj.id
        target_label = obj.root_folder_name
        connection_id = obj.connection_id
        super().delete_model(request, obj)
        record_audit_event(
            request=request,
            module="storage",
            action="mount_deleted",
            event_name="storage.mount_deleted",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="storage_mount",
            target_id=target_id,
            target_label=target_label,
            storage_connection_id=connection_id,
        )


@admin.register(DocumentReplica)
class DocumentReplicaAdmin(admin.ModelAdmin):
    list_display = (
        "asset",
        "connection",
        "version",
        "sync_status",
        "last_synced_at",
    )
    list_filter = ("sync_status", "connection")
    readonly_fields = (
        "remote_file_token",
        "remote_url",
        "content_hash",
        "last_synced_at",
        "error_code",
        "error_summary",
        "revoked_at",
    )
    actions = ("retry_replicas", "revoke_replicas")

    @admin.action(description="Retry selected replicas")
    def retry_replicas(self, request, queryset):
        replicas = queryset.select_related(
            "asset__quotation",
            "connection",
            "mount",
        )
        for replica in replicas:
            route = StorageRoute(
                connection=replica.connection,
                mount=replica.mount,
                provider=FeishuStorageProvider(replica.connection),
            )
            create_replica(
                request=request,
                asset=replica.asset,
                route=route,
            )

    @admin.action(description="Revoke selected replicas")
    def revoke_replicas(self, request, queryset):
        replicas = queryset.select_related("asset", "connection")
        for replica in replicas.exclude(sync_status="revoked"):
            revoke_replica(request=request, replica=replica)


admin.site.register(SyncJob)
