"""Restricted configuration and connection-scoped read-only history."""

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import APIException

from agione_ops.models import (
    CallFact,
    ConnectionGrant,
    DatasetVersion,
    SourceConnection,
    SyncRun,
    VersionCall,
)
from agione_ops.permissions import connections_for, has_action


class ConfigurationAdmin(admin.ModelAdmin):
    """A configuration permission never grants business-data access."""

    actions = None

    def has_module_permission(self, request):
        return request.user.is_staff and has_action(
            request.user, "manage_connections"
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)


@admin.register(SourceConnection)
class SourceConnectionAdmin(ConfigurationAdmin):
    """Configure synthetic sources without exposing credential ciphertext."""

    list_display = ("name", "platform", "principal_kind", "enabled")
    fields = (
        "name",
        "platform",
        "principal_kind",
        "source_kind",
        "endpoint",
        "expected_tenant_id",
        "enabled",
        "synthetic_fixture",
    )

    def get_readonly_fields(self, request, obj=None):
        return (
            ("platform", "principal_kind", "source_kind", "expected_tenant_id")
            if obj is not None
            else ()
        )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.save()


@admin.register(ConnectionGrant)
class ConnectionGrantAdmin(ConfigurationAdmin):
    """Explicit connection assignments remain revision aware."""

    list_display = ("connection", "user", "can_view", "can_sync", "revision")
    fields = ("connection", "user", "can_view", "can_sync")

    def get_readonly_fields(self, request, obj=None):
        return ("connection", "user") if obj is not None else ()


class ReadOnlyHistoryAdmin(admin.ModelAdmin):
    """Read-only artifact forms remain scoped even for superusers."""

    actions = None
    action = "view_business"
    connection_lookup = "connection_id__in"

    def has_module_permission(self, request):
        return request.user.is_staff and has_action(request.user, self.action)

    def has_view_permission(self, request, obj=None):
        if not self.has_module_permission(request):
            return False
        return (
            obj is None
            or self.get_queryset(request).filter(pk=obj.pk).exists()
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        return {}

    def save_model(self, request, obj, form, change):
        raise PermissionDenied("AGIOne history is read-only.")

    def delete_model(self, request, obj):
        raise PermissionDenied("AGIOne history is read-only.")

    def delete_queryset(self, request, queryset):
        raise PermissionDenied("AGIOne history is read-only.")

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.opts.fields)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        try:
            connections = connections_for(request.user, self.action)
        except APIException:
            return queryset.none()
        queryset = queryset.filter(
            **{self.connection_lookup: connections.values("pk")}
        )
        if self.action == "run_sync":
            queryset = queryset.filter(initiated_by=request.user)
        return queryset


@admin.register(SyncRun)
class SyncRunAdmin(ReadOnlyHistoryAdmin):
    action = "run_sync"
    list_display = ("id", "connection", "status", "phase", "created_at")


@admin.register(DatasetVersion)
class DatasetVersionAdmin(ReadOnlyHistoryAdmin):
    list_display = ("id", "connection", "published_at")


@admin.register(CallFact)
class CallFactAdmin(ReadOnlyHistoryAdmin):
    list_display = (
        "upstream_record_id",
        "connection",
        "occurred_at",
        "status",
    )


@admin.register(VersionCall)
class VersionCallAdmin(ReadOnlyHistoryAdmin):
    connection_lookup = "version__connection_id__in"
