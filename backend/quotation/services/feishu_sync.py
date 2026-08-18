from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
from hashlib import sha256
from typing import Any

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from quotation.models import (
    DocumentAsset,
    StorageConnectionStatus,
    StorageMount,
    StorageMountPurpose,
    SyncJob,
    SyncJobStatus,
    SyncJobType,
)
from quotation.permissions import is_quotation_admin, user_display_email

ACTIVE_SYNC_STATUSES = {
    SyncJobStatus.PENDING,
    SyncJobStatus.QUEUED,
    SyncJobStatus.RUNNING,
    SyncJobStatus.RETRYING,
}


@dataclass(frozen=True)
class FeishuSyncTarget:
    """One backend-authorized Feishu folder synchronization target."""

    folder_token: str
    folder_name: str = ""
    connection_id: str | None = None
    mount_id: str | None = None


def is_sync_admin(user) -> bool:
    if user is None:
        return True
    if is_quotation_admin(user):
        return True
    try:
        from quotation.permissions import is_quotation_platform_admin
    except ImportError:
        return False
    return is_quotation_platform_admin(user)


def _active_granted_folder_tokens(user) -> set[str]:
    """Read folder grants when the permission dependency is installed."""
    try:
        permission_model = apps.get_model(
            "quotation",
            "QuotationViewPermission",
        )
    except LookupError:
        return set()
    now = timezone.now()
    return set(
        permission_model.objects.filter(
            user=user,
            is_active=True,
            target_type="folder",
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .exclude(folder_token="")
        .values_list("folder_token", flat=True)
    )


def _owned_folder_tokens(user) -> set[str]:
    """Return folders already represented by documents owned by the user."""
    if user is None:
        return set()
    email = user_display_email(user)
    return set(
        DocumentAsset.objects.filter(source="feishu")
        .filter(
            Q(created_by_email__iexact=email)
            | Q(quotation__created_by_email__iexact=email)
        )
        .exclude(feishu_folder_token__isnull=True)
        .exclude(feishu_folder_token="")
        .values_list("feishu_folder_token", flat=True)
    )


def _owns_legacy_feishu_asset(user) -> bool:
    """Detect pre-router imports that do not store their source folder."""
    if user is None:
        return False
    email = user_display_email(user)
    return (
        DocumentAsset.objects.filter(source="feishu")
        .filter(
            Q(created_by_email__iexact=email)
            | Q(quotation__created_by_email__iexact=email)
        )
        .filter(
            Q(feishu_folder_token__isnull=True) | Q(feishu_folder_token="")
        )
        .exists()
    )


def authorized_sync_targets(actor) -> list[FeishuSyncTarget]:
    """Resolve synchronization roots without trusting frontend input."""
    if settings.QUOTATION_STORAGE_ROUTER_ENABLED:
        mounts = StorageMount.objects.select_related("connection").filter(
            enabled=True,
            purpose=StorageMountPurpose.QUOTATION_ARCHIVE,
            connection__status=StorageConnectionStatus.ACTIVE,
        )
        if mounts.exists():
            if is_sync_admin(actor):
                return [
                    FeishuSyncTarget(
                        folder_token=mount.root_folder_token,
                        folder_name=mount.root_folder_name,
                        connection_id=mount.connection_id,
                        mount_id=mount.id,
                    )
                    for mount in mounts.order_by("id")
                ]
            allowed_tokens = _active_granted_folder_tokens(actor)
            allowed_tokens.update(_owned_folder_tokens(actor))
            if not allowed_tokens:
                return []
            default_mount = mounts.order_by("-is_default", "id").first()
            if default_mount is None:
                return []
            return [
                FeishuSyncTarget(
                    folder_token=token,
                    connection_id=default_mount.connection_id,
                    mount_id=default_mount.id,
                )
                for token in sorted(allowed_tokens)
            ]

    root_token = str(
        settings.QUOTATION_FEISHU_ARCHIVE_FOLDER_TOKEN or ""
    ).strip()
    if not root_token:
        return []
    if is_sync_admin(actor):
        return [FeishuSyncTarget(folder_token=root_token)]
    allowed_tokens = _active_granted_folder_tokens(actor)
    allowed_tokens.update(_owned_folder_tokens(actor))
    if not allowed_tokens and _owns_legacy_feishu_asset(actor):
        allowed_tokens.add(root_token)
    return [
        FeishuSyncTarget(folder_token=token)
        for token in sorted(allowed_tokens)
    ]


def sync_scope_key(actor, targets: list[FeishuSyncTarget]) -> str:
    """Build a stable, non-sensitive deduplication key."""
    actor_key = str(getattr(actor, "pk", "system") or "system")
    target_key = ",".join(
        sorted(
            f"{target.connection_id or 'compat'}:{target.folder_token}"
            for target in targets
        )
    )
    digest = sha256(target_key.encode("utf-8")).hexdigest()[:24]
    return f"feishu:{actor_key}:{digest}"


def sync_state_id(connection_id: str | None, folder_token: str) -> str:
    """Return one deterministic state ID for a provider folder."""
    scope = f"{connection_id or 'compat'}:{folder_token}"
    digest = sha256(scope.encode("utf-8")).hexdigest()
    return f"fs-{digest[:33]}"


def _recent_login_job(actor, scope_key: str):
    cooldown = max(
        int(
            getattr(
                settings,
                "QUOTATION_FEISHU_LOGIN_SYNC_COOLDOWN_SECONDS",
                300,
            )
        ),
        0,
    )
    if not cooldown:
        return None
    cutoff = timezone.now() - timedelta(seconds=cooldown)
    return (
        SyncJob.objects.filter(
            actor=actor,
            job_type=SyncJobType.PULL,
            scope_key=scope_key,
            created_at__gte=cutoff,
        )
        .order_by("-created_at", "-id")
        .first()
    )


def enqueue_feishu_sync(
    *,
    actor,
    trigger: str,
    force: bool = False,
    request_id: str = "",
    trace_id: str = "",
) -> tuple[SyncJob | None, bool]:
    """Create or reuse one durable synchronization job."""
    targets = authorized_sync_targets(actor)
    if not targets:
        return None, False
    scope_key = sync_scope_key(actor, targets)
    active = (
        SyncJob.objects.filter(
            actor=actor,
            job_type=SyncJobType.PULL,
            scope_key=scope_key,
            status__in=ACTIVE_SYNC_STATUSES,
        )
        .order_by("-created_at", "-id")
        .first()
    )
    if active is not None:
        return active, True
    if trigger == "login" and not force:
        recent = _recent_login_job(actor, scope_key)
        if recent is not None:
            return recent, True

    lock_key = f"quotation:feishu:enqueue:{scope_key}"
    if not cache.add(lock_key, True, timeout=30):
        active = (
            SyncJob.objects.filter(
                actor=actor,
                job_type=SyncJobType.PULL,
                scope_key=scope_key,
                status__in=ACTIVE_SYNC_STATUSES,
            )
            .order_by("-created_at", "-id")
            .first()
        )
        return active, active is not None

    try:
        with transaction.atomic():
            connection_ids = {
                target.connection_id
                for target in targets
                if target.connection_id
            }
            job = SyncJob.objects.create(
                job_type=SyncJobType.PULL,
                status=SyncJobStatus.PENDING,
                actor=actor,
                scope_key=scope_key,
                request_id=request_id,
                trace_id=trace_id,
                storage_connection_id=(
                    next(iter(connection_ids))
                    if len(connection_ids) == 1
                    else None
                ),
                payload_json={
                    "action": "feishu_archive_folder_sync",
                    "audit_source": (
                        "user" if trigger == "manual" else trigger
                    ),
                    "trigger": trigger,
                    "targets": [asdict(target) for target in targets],
                    "operator_email": (
                        user_display_email(actor) if actor is not None else ""
                    ),
                },
            )
        from quotation.tasks import sync_feishu_folder_task

        try:
            task = sync_feishu_folder_task.apply_async(
                args=[job.id, getattr(actor, "id", None)],
                queue="quotation_sync",
            )
        except Exception as exc:
            job.status = SyncJobStatus.FAILED
            job.stage = "enqueue_failed"
            job.error_code = "enqueue_failed"
            job.error_message = type(exc).__name__
            job.finished_at = timezone.now()
            job.save(
                update_fields=[
                    "status",
                    "stage",
                    "error_code",
                    "error_message",
                    "finished_at",
                    "updated_at",
                ]
            )
            raise
        job.status = SyncJobStatus.QUEUED
        job.stage = "queued"
        job.celery_task_id = task.id
        job.save(
            update_fields=[
                "status",
                "stage",
                "celery_task_id",
                "updated_at",
            ]
        )
        return job, False
    finally:
        cache.delete(lock_key)


def file_metadata(
    item: dict[str, Any],
    *,
    folder_token: str,
    folder_path: list[dict[str, str]],
) -> dict[str, Any]:
    """Normalize the remote fields used for difference detection."""
    return {
        "file_token": str(item.get("token") or "").strip(),
        "file_name": str(item.get("name") or "").strip(),
        "file_type": str(item.get("type") or "").strip().lower(),
        "folder_token": folder_token,
        "folder_path": folder_path,
        "size_bytes": int(item.get("size") or 0),
        "modified_time": str(item.get("modified_time") or "").strip(),
        "url": str(item.get("url") or "").strip(),
    }


def metadata_fingerprint(metadata: dict[str, Any]) -> str:
    """Return a stable signature without storing remote content."""
    values = (
        metadata.get("file_token"),
        metadata.get("folder_token"),
        metadata.get("file_name"),
        metadata.get("file_type"),
        metadata.get("size_bytes"),
        metadata.get("modified_time"),
    )
    encoded = "\x1f".join(str(value or "") for value in values)
    return sha256(encoded.encode("utf-8")).hexdigest()


def parse_dispatch_lock_key(
    *,
    asset_id: str,
    content_hash: str,
    parser_version: str,
) -> str:
    """Build a short cache key for idempotent parser dispatch."""
    payload = "\x1f".join((asset_id, content_hash, parser_version))
    digest = sha256(payload.encode("utf-8")).hexdigest()
    return f"quotation:feishu:parse-dispatch:{digest}"
