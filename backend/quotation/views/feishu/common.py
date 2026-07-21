from __future__ import annotations

from collections import deque

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework.response import Response

from quotation.models import (
    DocumentAsset,
    DocumentReplica,
    Quotation,
    QuoteStatus,
    ReplicaSyncStatus,
)
from quotation.services.feishu_client import (
    FeishuAPIError,
    FeishuClient,
    extract_feishu_token_from_url,
)
from quotation.services.feishu_service import (
    chunk_file_tokens as _chunked_file_tokens,
)
from quotation.services.storage_control import (
    StorageRouter,
    configured_drive_context,
)
from quotation.services.feishu_service import (
    classify_batch_query_results as _classify_batch_query_results,
)
from quotation.services.feishu_service import (
    feishu_file_not_found as _feishu_file_not_found,
)
from quotation.services.feishu_service import guess_doc_type as _guess_doc_type
from quotation.services.feishu_service import (
    folder_token_for_item as _folder_token_for_item,
)
from quotation.services.feishu_service import (
    is_folder_drive_item as _is_folder_drive_item,
)
from quotation.services.feishu_service import (
    item_size_bytes as _item_size_bytes,
)
from quotation.services.feishu_service import (
    serialize_drive_file as _serialize_drive_file,
)
from quotation.services.feishu_service import (
    suggest_unique_file_name as _suggest_unique_file_name,
)


def _client() -> FeishuClient:
    return FeishuClient()


ARCHIVE_FOLDER_LABEL = "Configured archive folder"


def _archive_folder_raw() -> str:
    return (
        getattr(settings, "QUOTATION_FEISHU_ARCHIVE_FOLDER_TOKEN", "")
        or getattr(settings, "QUOTATION_FEISHU_ARCHIVE_FOLDER_URL", "")
        or getattr(settings, "FEISHU_TEST_FOLDER_TOKEN", "")
        or ""
    ).strip()


def _has_archive_folder() -> bool:
    return bool(_archive_folder_raw())


def _archive_folder_token() -> str:
    if settings.QUOTATION_STORAGE_ROUTER_ENABLED:
        try:
            return StorageRouter().resolve().mount.root_folder_token
        except (LookupError, ValueError):
            pass
    raw = _archive_folder_raw()
    if not raw:
        raise FeishuAPIError(
            "Quotation Feishu archive folder is not configured"
        )
    return extract_feishu_token_from_url(raw)


def _system_access_token(client: FeishuClient | None = None) -> str:
    resolved_client = client or _client()
    token_getter = getattr(resolved_client, "get_tenant_access_token", None)
    if callable(token_getter):
        return token_getter()
    return ""


def _system_drive_context() -> tuple[FeishuClient, str, str]:
    configured = configured_drive_context()
    if configured is not None:
        client, access_token, root_folder_token, _, _ = configured
        return client, access_token, root_folder_token
    client = _client()
    return client, _system_access_token(client), _archive_folder_token()


def _system_drive_context_details():
    """Return the legacy tuple plus optional control-plane entities."""
    configured = configured_drive_context()
    if configured is not None:
        return configured
    client = _client()
    return (
        client,
        _system_access_token(client),
        _archive_folder_token(),
        None,
        None,
    )


def _feishu_error_response(
    exc: FeishuAPIError,
    *,
    operation: str,
) -> Response:
    """Map upstream failures without exposing Feishu response details."""
    if _feishu_file_not_found(exc):
        return Response({"detail": "Feishu resource not found"}, status=404)
    return Response({"detail": f"Feishu {operation} failed"}, status=502)


def _managed_folder_token(
    *,
    client: FeishuClient,
    access_token: str,
    requested_token: str | None,
) -> str:
    """Resolve a folder only when it belongs to the archive subtree."""
    root_token = _archive_folder_token()
    target_token = str(requested_token or root_token).strip()
    if target_token == root_token:
        return root_token

    pending = deque([root_token])
    visited: set[str] = set()
    while pending and len(visited) < 2000:
        folder_token = pending.popleft()
        if folder_token in visited:
            continue
        visited.add(folder_token)
        page_token = None
        visited_pages: set[str] = set()
        for _ in range(20):
            data = client.list_folder_files(
                access_token,
                folder_token,
                page_size=200,
                page_token=page_token,
            )
            for item in data.get("files") or []:
                item_type = str(item.get("type") or "").lower()
                if item_type not in {"folder", "drive#folder"}:
                    continue
                child_token = _folder_token_for_item(item).strip()
                if not child_token:
                    continue
                if child_token == target_token:
                    return target_token
                if child_token not in visited:
                    pending.append(child_token)
            if not data.get("has_more"):
                break
            page_token = str(data.get("next_page_token") or "").strip()
            if not page_token or page_token in visited_pages:
                break
            visited_pages.add(page_token)

    raise PermissionError("folder is outside the configured archive root")


def _clear_feishu_file_links(
    *,
    file_token: str,
    base_qs,
    quotation_id: str | None = None,
    doc_type: str | None = None,
    document_id: str | None = None,
) -> int:
    """
    Drop stale Feishu links so serializers stop exposing open buttons.
    """
    token = str(file_token or "").strip()
    if not token:
        return 0
    qs = base_qs.filter(
        Q(feishu_file_token=token) | Q(replicas__remote_file_token=token)
    )
    if document_id:
        qs = qs.filter(pk=document_id)
    asset_ids = list(qs.values_list("id", flat=True).distinct())
    cleared = _mark_feishu_reference_missing(asset_ids, token)
    if cleared and quotation_id:
        if not base_qs.filter(quotation_id=quotation_id).exists():
            return cleared
        live_qs = base_qs
        has_live_feishu_file = (
            live_qs.filter(
                quotation_id=quotation_id,
                source="feishu_upload",
            )
            .filter(_active_feishu_reference_filter())
            .distinct()
            .exists()
        )
        if not has_live_feishu_file:
            Quotation.objects.filter(
                pk=quotation_id,
                status=QuoteStatus.UPLOADED,
            ).update(status=QuoteStatus.GENERATED)
    if cleared or not quotation_id or not doc_type:
        return cleared
    fallback_qs = base_qs.filter(
        Q(feishu_file_token=token) | Q(replicas__remote_file_token=token),
        quotation_id=quotation_id,
        doc_type=doc_type,
        source="feishu_upload",
    )
    fallback_ids = list(fallback_qs.values_list("id", flat=True).distinct())
    return _mark_feishu_reference_missing(fallback_ids, token) or cleared


def _active_feishu_reference_filter() -> Q:
    return (
        Q(feishu_file_token__isnull=False)
        & ~Q(feishu_file_token="")
    ) | (
        Q(replicas__sync_status=ReplicaSyncStatus.SYNCED)
        & Q(replicas__revoked_at__isnull=True)
        & ~Q(replicas__remote_file_token="")
    )


def _mark_feishu_reference_missing(
    asset_ids: list[str],
    token: str,
) -> int:
    if not asset_ids:
        return 0
    cleared = DocumentAsset.objects.filter(id__in=asset_ids).update(
        feishu_file_token=None,
        feishu_url=None,
    )
    DocumentReplica.objects.filter(
        asset_id__in=asset_ids,
        remote_file_token=token,
        revoked_at__isnull=True,
    ).update(
        sync_status=ReplicaSyncStatus.REVOKED,
        revoked_at=timezone.now(),
        error_code="remote_not_found",
        error_summary="Remote file was not found",
    )
    return cleared


def _list_folder_file_names(
    *,
    client: FeishuClient,
    access_token: str,
    folder_token: str,
) -> set[str]:
    names: set[str] = set()
    page_token = None
    for _ in range(20):
        data = client.list_folder_files(
            access_token,
            folder_token,
            page_size=200,
            page_token=page_token,
        )
        for item in data.get("files") or []:
            if _is_folder_drive_item(item):
                continue
            name = item.get("name")
            if name:
                names.add(str(name))
        if not data.get("has_more"):
            break
        page_token = data.get("next_page_token")
        if not page_token:
            break
    return names


def _find_existing_file_in_folder(
    *,
    client: FeishuClient,
    access_token: str,
    folder_token: str,
    file_name: str,
) -> dict | None:
    page_token = None
    for _ in range(20):
        data = client.list_folder_files(
            access_token,
            folder_token,
            page_size=200,
            page_token=page_token,
        )
        for item in data.get("files") or []:
            if _is_folder_drive_item(item):
                continue
            if item.get("name") == file_name and item.get("token"):
                return item
        if not data.get("has_more"):
            return None
        page_token = data.get("next_page_token")
        if not page_token:
            return None
    return None


def _find_file_by_token_or_name_in_folder(
    *,
    client: FeishuClient,
    access_token: str,
    folder_token: str,
    file_token: str,
    file_name: str,
) -> dict | None:
    page_token = None
    for _ in range(20):
        data = client.list_folder_files(
            access_token,
            folder_token,
            page_size=200,
            page_token=page_token,
        )
        for item in data.get("files") or []:
            if _is_folder_drive_item(item):
                continue
            if item.get("token") == file_token:
                return item
        if not data.get("has_more"):
            return None
        page_token = data.get("next_page_token")
        if not page_token:
            return None
    return None
