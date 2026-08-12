from __future__ import annotations

import logging
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
    RemoteFileCleanup,
    RemoteFileCleanupStatus,
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
from quotation.services.feishu_client import (
    FeishuAPIError,
    FeishuClient,
    FeishuDownloadTooLargeError,
)
from quotation.services.feishu_service import (
    feishu_file_not_found,
    is_folder_drive_item,
    item_size_bytes,
    suggest_unique_file_name,
)
from quotation.services.storage import resolve_document_path

logger = logging.getLogger(__name__)


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
    prefetched = getattr(asset, "_prefetched_objects_cache", {}).get("replicas")
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
                replica.last_synced_at or replica.updated_at or replica.created_at,
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
                f"feishu_{exc.code}" if exc.code is not None else "feishu_health_failed"
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
        access_token = self.access_token()
        target_folder = folder_token or mount.root_folder_token
        files = self._folder_files(
            access_token=access_token,
            folder_token=target_folder,
        )
        existing = next(
            (
                item
                for item in files
                if item.get("name") == file_name
                and item.get("token")
                and not is_folder_drive_item(item)
            ),
            None,
        )
        existing_type = str((existing or {}).get("type") or "").lower()
        if (
            existing is not None
            and existing_type in {"file", "drive#file"}
            and mount.conflict_policy == "reuse"
        ):
            token = str(existing.get("token") or "")
            remote_size = item_size_bytes(existing)
            if remote_size is None or remote_size == len(content):
                try:
                    remote_content, _mime_type = self.client.download_file(
                        access_token,
                        token,
                        max_bytes=len(content),
                    )
                except FeishuDownloadTooLargeError:
                    remote_content = None
                if remote_content is not None and (
                    sha256(remote_content).digest() == sha256(content).digest()
                ):
                    return {
                        "file_token": token,
                        "token": token,
                        "url": str(existing.get("url") or ""),
                        "reused": True,
                    }
        upload_name = file_name
        if existing is not None:
            existing_names = {
                str(item.get("name"))
                for item in files
                if item.get("name") and not is_folder_drive_item(item)
            }
            upload_name = suggest_unique_file_name(
                file_name,
                existing_names,
            )
        return self.client.upload_file(
            access_token,
            folder_token=target_folder,
            file_name=upload_name,
            content=content,
        )

    def _folder_files(
        self,
        *,
        access_token: str,
        folder_token: str,
    ) -> list[dict]:
        files = []
        page_token = None
        for _ in range(20):
            data = self.client.list_folder_files(
                access_token,
                folder_token,
                page_size=200,
                page_token=page_token,
            )
            files.extend(data.get("files") or [])
            if not data.get("has_more"):
                break
            page_token = data.get("next_page_token")
            if not page_token:
                break
        return files

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


def _lock_remote_file_reference(
    remote_file_token: str,
    *,
    connection: StorageConnection,
    owned: bool,
) -> None:
    now = timezone.now()
    cleanup, created = RemoteFileCleanup.objects.get_or_create(
        remote_file_token=remote_file_token,
        defaults={
            "connection": connection,
            "owned": owned,
            "status": RemoteFileCleanupStatus.CANCELLED,
            "processed_at": now,
        },
    )
    if created:
        return
    cleanup = RemoteFileCleanup.objects.select_for_update().get(
        pk=cleanup.pk,
    )
    if cleanup.status == RemoteFileCleanupStatus.COMPLETED and not owned:
        raise FeishuAPIError("Remote file was deleted while it was being reused")
    update_fields = [
        "status",
        "last_error",
        "processed_at",
        "updated_at",
    ]
    if owned and cleanup.connection_id != connection.id:
        cleanup.connection = connection
        update_fields.append("connection")
    if owned and not cleanup.owned:
        cleanup.owned = True
        update_fields.append("owned")
    cleanup.status = RemoteFileCleanupStatus.CANCELLED
    cleanup.last_error = ""
    cleanup.processed_at = now
    cleanup.save(update_fields=update_fields)


def preserve_remote_file_reference(
    remote_file_token: str,
    *,
    connection: StorageConnection | None,
    owned: bool,
) -> None:
    """Serialize a new reference against cleanup of the same token."""
    if not remote_file_token or connection is None:
        return
    with transaction.atomic():
        _lock_remote_file_reference(
            remote_file_token,
            connection=connection,
            owned=owned,
        )


def create_replica(
    *,
    request,
    asset: DocumentAsset,
    route: StorageRoute,
    folder_token: str = "",
) -> DocumentReplica:
    """Create or retry one idempotent managed remote document replica."""
    content = resolve_document_path(asset.storage_key).read_bytes()
    content_hash = asset.content_hash or sha256(content).hexdigest()
    if asset.quotation_version_id:
        version = asset.quotation_version.version_no
    elif asset.quotation_id:
        version = max(asset.quotation.version_current or 1, 1)
    else:
        version = 1
    target_folder = folder_token or route.mount.root_folder_token
    replica, _ = DocumentReplica.objects.get_or_create(
        asset=asset,
        connection=route.connection,
        version=version,
        defaults={
            "mount": route.mount,
            "folder_token": target_folder,
        },
    )
    if (
        replica.sync_status == ReplicaSyncStatus.SYNCED
        and replica.content_hash == content_hash
        and replica.remote_file_token
        and replica.folder_token == target_folder
        and replica.revoked_at is None
    ):
        return replica
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
    replica.folder_token = target_folder
    replica.save(
        update_fields=["folder_token", "sync_status", "updated_at"]
    )
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
        uploaded = route.provider.upload(
            route.mount,
            file_name=asset.file_name,
            content=content,
            folder_token=target_folder,
        )
        token = str(uploaded.get("file_token") or uploaded.get("token") or "")
        if not token:
            raise FeishuAPIError("Replica upload returned no file token")
        url = str(uploaded.get("url") or "")
        now = timezone.now()
        with transaction.atomic():
            uploaded_file_owned = not bool(uploaded.get("reused"))
            previous_token = str(replica.remote_file_token or "")
            previous_owned = bool((replica.metadata or {}).get("remote_file_owned"))
            previous_owner_connection_id = str(
                (replica.metadata or {}).get("remote_file_owner_connection_id")
                or route.connection.id
            )
            _lock_remote_file_reference(
                token,
                connection=route.connection,
                owned=uploaded_file_owned,
            )
            replica.remote_file_token = token
            replica.remote_url = url
            replica.content_hash = content_hash
            replica.sync_status = ReplicaSyncStatus.SYNCED
            replica.last_synced_at = now
            replica.error_code = ""
            replica.error_summary = ""
            remote_file_owned = bool(
                uploaded_file_owned or (token == previous_token and previous_owned)
            )
            metadata = dict(replica.metadata or {})
            metadata["remote_file_owned"] = remote_file_owned
            if uploaded_file_owned:
                metadata["remote_file_owner_connection_id"] = route.connection.id
            elif not remote_file_owned:
                metadata.pop("remote_file_owner_connection_id", None)
            replica.metadata = metadata
            replica.save()
            if previous_token and previous_token != token and previous_owned:
                delete_owned_replicas_after_commit(
                    [
                        SimpleNamespace(
                            connection_id=previous_owner_connection_id,
                            remote_file_token=previous_token,
                            metadata={
                                "remote_file_owned": True,
                                "remote_file_owner_connection_id": (
                                    previous_owner_connection_id
                                ),
                            },
                        )
                    ]
                )
            job.status = SyncJobStatus.SUCCESS
            job.result_json = {"replica_id": replica.id}
            job.save(update_fields=["status", "result_json", "updated_at"])
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
            f"feishu_{error_code}" if error_code is not None else "replica_sync_failed"
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
    remote_file_owned: bool = False,
    remote_file_owner_connection: StorageConnection | None = None,
) -> DocumentReplica:
    """Register an upload already completed by the compatibility endpoint."""
    version = max(asset.quotation.version_current or 1, 1) if asset.quotation_id else 1
    with transaction.atomic():
        owner_connection = remote_file_owner_connection or route.connection
        _lock_remote_file_reference(
            remote_file_token,
            connection=owner_connection,
            owned=remote_file_owned,
        )
        replica = (
            DocumentReplica.objects.select_for_update()
            .filter(
                asset=asset,
                connection=route.connection,
                version=version,
            )
            .first()
        )
        if replica is None:
            replica = DocumentReplica(
                asset=asset,
                connection=route.connection,
                version=version,
            )
        previous_token = str(replica.remote_file_token or "")
        metadata = dict(replica.metadata or {})
        previous_owned = bool(metadata.get("remote_file_owned"))
        current_file_owned = bool(
            remote_file_owned
            or (remote_file_token == previous_token and previous_owned)
        )
        previous_owner_connection_id = str(
            metadata.get("remote_file_owner_connection_id") or route.connection.id
        )
        metadata["remote_file_owned"] = current_file_owned
        if remote_file_owned:
            metadata["remote_file_owner_connection_id"] = owner_connection.id
        elif not current_file_owned:
            metadata.pop("remote_file_owner_connection_id", None)
        replica.mount = route.mount
        replica.remote_file_token = remote_file_token
        replica.remote_url = remote_url
        replica.folder_token = folder_token
        replica.sync_status = ReplicaSyncStatus.SYNCED
        replica.last_synced_at = timezone.now()
        replica.error_code = ""
        replica.error_summary = ""
        replica.metadata = metadata
        replica.save()
        if previous_token and previous_token != remote_file_token and previous_owned:
            delete_owned_replicas_after_commit(
                [
                    SimpleNamespace(
                        connection_id=previous_owner_connection_id,
                        remote_file_token=previous_token,
                        metadata={
                            "remote_file_owned": True,
                            "remote_file_owner_connection_id": (
                                previous_owner_connection_id
                            ),
                        },
                    )
                ]
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
    replica.save(update_fields=["sync_status", "revoked_at", "updated_at"])
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


def delete_owned_replicas_after_commit(replicas) -> None:
    """Persist and enqueue cleanup intents for owned remote files."""
    replicas = tuple(replicas)
    cleanup_ids = []
    seen_remote_files = set()
    for replica in replicas:
        remote_token = str(replica.remote_file_token or "")
        metadata = dict(getattr(replica, "metadata", {}) or {})
        reference_owned = bool(metadata.get("remote_file_owned"))
        reference_connection_id = getattr(replica, "connection_id", None)
        owner_connection_id = (
            metadata.get("remote_file_owner_connection_id") or reference_connection_id
        )
        if not remote_token or remote_token in seen_remote_files:
            continue
        cleanup = RemoteFileCleanup.objects.filter(
            remote_file_token=remote_token,
        ).first()
        if cleanup is None:
            if not reference_owned or not owner_connection_id:
                continue
            cleanup, _created = RemoteFileCleanup.objects.get_or_create(
                remote_file_token=remote_token,
                defaults={
                    "connection_id": owner_connection_id,
                    "owned": True,
                },
            )
        cleanup = RemoteFileCleanup.objects.select_for_update().get(
            pk=cleanup.pk,
        )
        if not cleanup.owned and not reference_owned:
            continue
        update_fields = [
            "status",
            "last_error",
            "next_dispatch_at",
            "processed_at",
            "updated_at",
        ]
        if reference_owned and not cleanup.owned:
            cleanup.owned = True
            update_fields.append("owned")
            if owner_connection_id:
                cleanup.connection_id = owner_connection_id
                update_fields.append("connection")
        cleanup.status = RemoteFileCleanupStatus.PENDING
        cleanup.last_error = ""
        cleanup.next_dispatch_at = timezone.now()
        cleanup.processed_at = None
        cleanup.save(update_fields=update_fields)
        seen_remote_files.add(remote_token)
        cleanup_ids.append(cleanup.id)

    def enqueue_cleanup() -> None:
        from quotation.tasks import delete_owned_remote_file_task

        for cleanup_id in cleanup_ids:
            dispatch_started_at = timezone.now()
            claimed = RemoteFileCleanup.objects.filter(
                pk=cleanup_id,
                status=RemoteFileCleanupStatus.PENDING,
                next_dispatch_at__lte=dispatch_started_at,
            ).update(next_dispatch_at=(dispatch_started_at + timedelta(minutes=5)))
            if not claimed:
                continue
            try:
                delete_owned_remote_file_task.apply_async(
                    args=[cleanup_id],
                    queue="quotation_sync",
                )
            except Exception:
                RemoteFileCleanup.objects.filter(
                    pk=cleanup_id,
                    status=RemoteFileCleanupStatus.PENDING,
                ).update(next_dispatch_at=dispatch_started_at)
                logger.exception(
                    "quotation_remote_file_cleanup_enqueue_failed",
                    extra={"remote_file_cleanup_id": cleanup_id},
                )

    transaction.on_commit(enqueue_cleanup, robust=True)


def delete_remote_file_if_unreferenced(
    cleanup_id: str,
) -> str:
    """Process one durable cleanup while serializing token registration."""
    pending_error = None
    result = "pending"
    with transaction.atomic():
        cleanup = (
            RemoteFileCleanup.objects.select_for_update()
            .select_related("connection")
            .get(pk=cleanup_id)
        )
        if cleanup.status != RemoteFileCleanupStatus.PENDING:
            return cleanup.status
        if not cleanup.owned:
            cleanup.status = RemoteFileCleanupStatus.CANCELLED
            cleanup.processed_at = timezone.now()
            cleanup.save(update_fields=["status", "processed_at", "updated_at"])
            return "unowned"
        surviving_replica = (
            DocumentReplica.objects.filter(
                remote_file_token=cleanup.remote_file_token,
                revoked_at__isnull=True,
            )
            .order_by("created_at", "id")
            .first()
        )
        legacy_reference_exists = DocumentAsset.objects.filter(
            feishu_file_token=cleanup.remote_file_token,
        ).exists()
        if surviving_replica is not None or legacy_reference_exists:
            if surviving_replica is not None:
                metadata = dict(surviving_replica.metadata or {})
                metadata["remote_file_owned"] = True
                metadata["remote_file_owner_connection_id"] = cleanup.connection_id
                DocumentReplica.objects.filter(
                    pk=surviving_replica.pk,
                ).update(metadata=metadata)
            cleanup.status = RemoteFileCleanupStatus.CANCELLED
            cleanup.processed_at = timezone.now()
            cleanup.save(update_fields=["status", "processed_at", "updated_at"])
            return "referenced"
        cleanup.attempts += 1
        reference = SimpleNamespace(
            remote_file_token=cleanup.remote_file_token,
        )
        try:
            FeishuStorageProvider(cleanup.connection).delete(reference)
        except FeishuAPIError as exc:
            if feishu_file_not_found(exc):
                result = "missing"
            else:
                pending_error = exc
        except Exception as exc:
            pending_error = exc
        if pending_error is None:
            cleanup.status = RemoteFileCleanupStatus.COMPLETED
            cleanup.last_error = ""
            cleanup.processed_at = timezone.now()
        else:
            cleanup.status = RemoteFileCleanupStatus.PENDING
            cleanup.last_error = type(pending_error).__name__[:255]
            cleanup.next_dispatch_at = timezone.now() + timedelta(
                minutes=5,
            )
        cleanup.save(
            update_fields=[
                "status",
                "attempts",
                "last_error",
                "next_dispatch_at",
                "processed_at",
                "updated_at",
            ]
        )
    if pending_error is not None:
        raise pending_error
    return result if result == "missing" else "deleted"
