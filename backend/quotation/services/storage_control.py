from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
from types import SimpleNamespace

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone

from quotation.audit import AUDIT_CONTEXT, record_audit_event
from quotation.models import (
    AuditEvent,
    DocumentAsset,
    DocumentReplica,
    ReplicaSyncStatus,
    StorageAuthMode,
    StorageConnection,
    StorageConnectionStatus,
    StorageMount,
    StorageMountPurpose,
    SyncJob,
    SyncJobStatus,
    SyncJobType,
)
from quotation.services.feishu_client import FeishuAPIError, FeishuClient
from quotation.services.storage import resolve_document_path


@dataclass(frozen=True)
class StorageRoute:
    connection: StorageConnection
    mount: StorageMount
    provider: "FeishuStorageProvider"


@dataclass(frozen=True)
class RemoteDocumentReference:
    token: str
    url: str
    folder_token: str
    replica: DocumentReplica | None = None


def active_replica_for_asset(
    asset: DocumentAsset,
) -> DocumentReplica | None:
    """Return the newest usable remote replica for one document asset."""
    prefetched = getattr(asset, "_prefetched_objects_cache", {}).get(
        "replicas"
    )
    if prefetched is not None:
        candidates = [
            replica
            for replica in prefetched
            if replica.sync_status == ReplicaSyncStatus.SYNCED
            and replica.remote_file_token
            and replica.revoked_at is None
        ]
        return max(
            candidates,
            key=lambda replica: (
                replica.version,
                replica.last_synced_at
                or replica.updated_at
                or replica.created_at,
                replica.created_at,
                replica.id,
            ),
            default=None,
        )

    return (
        asset.replicas.filter(
            sync_status=ReplicaSyncStatus.SYNCED,
            revoked_at__isnull=True,
        )
        .exclude(remote_file_token="")
        .order_by("-version", "-last_synced_at", "-created_at", "-id")
        .first()
    )


def remote_document_reference(
    asset: DocumentAsset,
) -> RemoteDocumentReference:
    """Return the current Feishu reference from replica or legacy fields."""
    replica = active_replica_for_asset(asset)
    if replica is not None:
        return RemoteDocumentReference(
            token=str(replica.remote_file_token or "").strip(),
            url=str(replica.remote_url or "").strip(),
            folder_token=str(replica.folder_token or "").strip(),
            replica=replica,
        )
    return RemoteDocumentReference(
        token=str(asset.feishu_file_token or "").strip(),
        url=str(asset.feishu_url or "").strip(),
        folder_token=str(asset.feishu_folder_token or "").strip(),
    )


class FeishuStorageProvider:
    """Provider adapter that keeps Feishu credentials out of business views."""

    def __init__(self, connection: StorageConnection):
        if connection.provider != "feishu":
            raise ValueError("Unsupported storage provider")
        self.connection = connection
        client_settings = SimpleNamespace(
            feishu_app_id=connection.app_id,
            feishu_app_secret=connection.get_app_secret(),
            feishu_base_url=settings.FEISHU_BASE_URL,
            feishu_oauth_redirect_uri=settings.FEISHU_OAUTH_REDIRECT_URI,
            feishu_oauth_scopes=settings.FEISHU_OAUTH_SCOPES,
        )
        self.client = FeishuClient(
            settings=client_settings,
            storage_connection_id=connection.id,
        )

    def access_token(self) -> str:
        if self.connection.auth_mode == StorageAuthMode.TENANT_APP:
            return self.client.get_tenant_access_token()
        token = self.connection.get_access_token()
        expires_at = self.connection.token_expires_at
        refresh_token = self.connection.get_refresh_token()
        should_refresh = bool(
            refresh_token
            and expires_at
            and expires_at <= timezone.now() + timedelta(minutes=1)
        )
        if should_refresh:
            try:
                bundle = self.client.refresh_user_token(refresh_token)
            except FeishuAPIError as exc:
                context = AUDIT_CONTEXT.get()
                request = SimpleNamespace(
                    user=None,
                    META={
                        "HTTP_X_REQUEST_ID": context.get("request_id", ""),
                        "HTTP_X_TRACE_ID": context.get("trace_id", ""),
                        "HTTP_X_QUOTATION_AUDIT_SOURCE": "automatic",
                    },
                )
                record_audit_event(
                    request=request,
                    module="feishu",
                    action="refresh",
                    event_name="feishu.oauth.refresh_failed",
                    result=AuditEvent.RESULT_FAILED,
                    actor_type=AuditEvent.ACTOR_TASK,
                    target_type="storage_connection",
                    target_id=self.connection.id,
                    storage_connection_id=self.connection.id,
                    error_code=(
                        f"feishu_{exc.code}"
                        if exc.code is not None
                        else "credential_refresh_failed"
                    ),
                )
                raise
            self.connection.access_token = bundle.access_token
            self.connection.refresh_token = bundle.refresh_token
            self.connection.token_expires_at = timezone.now() + timedelta(
                seconds=bundle.expires_in
            )
            self.connection.save(
                update_fields=[
                    "access_token",
                    "refresh_token",
                    "token_expires_at",
                    "updated_at",
                ]
            )
            token = bundle.access_token
        if token:
            return token
        raise FeishuAPIError("Managed account access token is unavailable")

    def health_check(self, mount: StorageMount) -> dict:
        checked_at = timezone.now()
        try:
            data = self.client.get_folder_meta(
                self.access_token(),
                mount.root_folder_token,
            )
        except FeishuAPIError as exc:
            error_code = (
                f"feishu_{exc.code}"
                if exc.code is not None
                else "feishu_health_failed"
            )
            self.connection.status = StorageConnectionStatus.ERROR
            self.connection.last_health_checked_at = checked_at
            self.connection.last_health_error_code = error_code
            self.connection.save(
                update_fields=[
                    "status",
                    "last_health_checked_at",
                    "last_health_error_code",
                    "updated_at",
                ]
            )
            raise
        self.connection.status = StorageConnectionStatus.ACTIVE
        self.connection.last_health_checked_at = checked_at
        self.connection.last_health_error_code = ""
        self.connection.save(
            update_fields=[
                "status",
                "last_health_checked_at",
                "last_health_error_code",
                "updated_at",
            ]
        )
        return data

    def upload(
        self,
        mount: StorageMount,
        *,
        file_name: str,
        content: bytes,
        folder_token: str = "",
    ) -> dict:
        return self.client.upload_file(
            self.access_token(),
            folder_token=folder_token or mount.root_folder_token,
            file_name=file_name,
            content=content,
        )

    def download(self, replica: DocumentReplica) -> tuple[bytes, str | None]:
        return self.client.download_file(
            self.access_token(),
            replica.remote_file_token,
        )

    def delete(self, replica: DocumentReplica) -> None:
        self.client.delete_file(
            self.access_token(),
            replica.remote_file_token,
        )

    def exists(self, replica: DocumentReplica) -> bool:
        try:
            self.client.batch_query_file_meta(
                self.access_token(),
                replica.remote_file_token,
            )
        except FeishuAPIError:
            return False
        return True


class StorageRouter:
    """Resolve a backend-owned storage route by scope and document type."""

    def resolve(
        self,
        *,
        scope_key: str = "",
        purpose: str = StorageMountPurpose.QUOTATION_ARCHIVE,
        document_type: str = "",
    ) -> StorageRoute:
        queryset = StorageMount.objects.select_related("connection").filter(
            enabled=True,
            purpose=purpose,
            connection__status=StorageConnectionStatus.ACTIVE,
        )
        if scope_key:
            scoped = queryset.filter(scope_key=scope_key)
            if scoped.exists():
                queryset = scoped
            else:
                queryset = queryset.filter(scope_key="")
        else:
            queryset = queryset.filter(scope_key="")
        if document_type:
            typed = queryset.filter(document_type=document_type)
            if typed.exists():
                queryset = typed
            else:
                queryset = queryset.filter(document_type="")
        else:
            queryset = queryset.filter(document_type="")
        mount = queryset.order_by("-is_default", "id").first()
        if mount is None:
            raise LookupError("No enabled storage mount matches this route")
        return StorageRoute(
            connection=mount.connection,
            mount=mount,
            provider=FeishuStorageProvider(mount.connection),
        )


def configured_drive_context():
    """Return a database route, or None while compatibility mode is active."""
    if not settings.QUOTATION_STORAGE_ROUTER_ENABLED:
        return None
    try:
        route = StorageRouter().resolve()
        return (
            route.provider.client,
            route.provider.access_token(),
            route.mount.root_folder_token,
            route.connection,
            route.mount,
        )
    except (DatabaseError, LookupError):
        return None


def _sync_context(request) -> dict[str, str]:
    context = AUDIT_CONTEXT.get()
    return {
        "request_id": getattr(request, "audit_request_id", "")
        or context.get("request_id", ""),
        "trace_id": getattr(request, "audit_trace_id", "")
        or context.get("trace_id", ""),
    }


def create_replica(
    *,
    request,
    asset: DocumentAsset,
    route: StorageRoute,
) -> DocumentReplica:
    """Create or retry one idempotent managed remote document replica."""
    version = (
        max(asset.quotation.version_current or 1, 1)
        if asset.quotation_id
        else 1
    )
    replica, _ = DocumentReplica.objects.get_or_create(
        asset=asset,
        connection=route.connection,
        version=version,
        defaults={
            "mount": route.mount,
            "folder_token": route.mount.root_folder_token,
        },
    )
    context = _sync_context(request)
    job = SyncJob.objects.create(
        job_type=SyncJobType.UPLOAD,
        status=SyncJobStatus.RUNNING,
        quotation=asset.quotation,
        asset=asset,
        replica=replica,
        storage_connection=route.connection,
        actor=getattr(request, "user", None),
        request_id=context["request_id"],
        trace_id=context["trace_id"],
    )
    replica.sync_status = ReplicaSyncStatus.SYNCING
    replica.save(update_fields=["sync_status", "updated_at"])
    record_audit_event(
        request=request,
        module="replica",
        action="sync_started",
        event_name="document.replica_sync_started",
        result=AuditEvent.RESULT_SUCCEEDED,
        target_type="document_replica",
        target_id=replica.id,
        document_id=asset.id,
        storage_connection_id=route.connection.id,
        target_organization_id=route.connection.external_tenant_id,
        sync_job_id=job.id,
    )
    try:
        content = resolve_document_path(asset.storage_key).read_bytes()
        uploaded = route.provider.upload(
            route.mount,
            file_name=asset.file_name,
            content=content,
        )
        token = str(uploaded.get("file_token") or uploaded.get("token") or "")
        if not token:
            raise FeishuAPIError("Replica upload returned no file token")
        url = str(uploaded.get("url") or "")
        now = timezone.now()
        with transaction.atomic():
            replica.remote_file_token = token
            replica.remote_url = url
            replica.content_hash = sha256(content).hexdigest()
            replica.sync_status = ReplicaSyncStatus.SYNCED
            replica.last_synced_at = now
            replica.error_code = ""
            replica.error_summary = ""
            replica.save()
            job.status = SyncJobStatus.SUCCESS
            job.result_json = {"replica_id": replica.id}
            job.save(
                update_fields=["status", "result_json", "updated_at"]
            )
        record_audit_event(
            request=request,
            module="replica",
            action="sync_succeeded",
            event_name="document.replica_sync_succeeded",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="document_replica",
            target_id=replica.id,
            document_id=asset.id,
            storage_connection_id=route.connection.id,
            target_organization_id=route.connection.external_tenant_id,
            sync_job_id=job.id,
        )
    except Exception as exc:
        error_code = getattr(exc, "code", None)
        stable_code = (
            f"feishu_{error_code}"
            if error_code is not None
            else "replica_sync_failed"
        )
        replica.sync_status = ReplicaSyncStatus.FAILED
        replica.error_code = stable_code
        replica.error_summary = "Remote replica synchronization failed"
        replica.save(
            update_fields=[
                "sync_status",
                "error_code",
                "error_summary",
                "updated_at",
            ]
        )
        job.status = SyncJobStatus.FAILED
        job.error_code = stable_code
        job.error_message = "Remote replica synchronization failed"
        job.save(
            update_fields=[
                "status",
                "error_code",
                "error_message",
                "updated_at",
            ]
        )
        record_audit_event(
            request=request,
            module="replica",
            action="sync_failed",
            event_name="document.replica_sync_failed",
            result=AuditEvent.RESULT_FAILED,
            target_type="document_replica",
            target_id=replica.id,
            document_id=asset.id,
            storage_connection_id=route.connection.id,
            target_organization_id=route.connection.external_tenant_id,
            sync_job_id=job.id,
            error_code=stable_code,
        )
        raise
    return replica


def register_uploaded_replica(
    *,
    request,
    asset: DocumentAsset,
    route: StorageRoute,
    remote_file_token: str,
    remote_url: str,
    folder_token: str,
) -> DocumentReplica:
    """Register an upload already completed by the compatibility endpoint."""
    version = (
        max(asset.quotation.version_current or 1, 1)
        if asset.quotation_id
        else 1
    )
    replica, _ = DocumentReplica.objects.update_or_create(
        asset=asset,
        connection=route.connection,
        version=version,
        defaults={
            "mount": route.mount,
            "remote_file_token": remote_file_token,
            "remote_url": remote_url,
            "folder_token": folder_token,
            "sync_status": ReplicaSyncStatus.SYNCED,
            "last_synced_at": timezone.now(),
            "error_code": "",
            "error_summary": "",
        },
    )
    context = _sync_context(request)
    job = SyncJob.objects.create(
        job_type=SyncJobType.UPLOAD,
        status=SyncJobStatus.SUCCESS,
        quotation=asset.quotation if asset.quotation_id else None,
        asset=asset,
        replica=replica,
        storage_connection=route.connection,
        actor=getattr(request, "user", None),
        request_id=context["request_id"],
        trace_id=context["trace_id"],
        result_json={"replica_id": replica.id},
    )
    record_audit_event(
        request=request,
        module="replica",
        action="sync_succeeded",
        event_name="document.replica_sync_succeeded",
        result=AuditEvent.RESULT_SUCCEEDED,
        target_type="document_replica",
        target_id=replica.id,
        document_id=asset.id,
        storage_connection_id=route.connection.id,
        target_organization_id=route.connection.external_tenant_id,
        sync_job_id=job.id,
    )
    return replica


def revoke_replica(*, request, replica: DocumentReplica) -> DocumentReplica:
    """Delete a remote replica and retain its terminal revoked state."""
    provider = FeishuStorageProvider(replica.connection)
    if replica.remote_file_token:
        provider.delete(replica)
    replica.sync_status = ReplicaSyncStatus.REVOKED
    replica.revoked_at = timezone.now()
    replica.save(
        update_fields=["sync_status", "revoked_at", "updated_at"]
    )
    record_audit_event(
        request=request,
        module="replica",
        action="revoked",
        event_name="document.replica_revoked",
        result=AuditEvent.RESULT_SUCCEEDED,
        target_type="document_replica",
        target_id=replica.id,
        document_id=replica.asset_id,
        storage_connection_id=replica.connection_id,
        target_organization_id=replica.connection.external_tenant_id,
    )
    return replica
