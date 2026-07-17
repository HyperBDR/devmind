from __future__ import annotations

from datetime import timezone as dt_timezone

from django.conf import settings
from django.utils import timezone

from quotation.models import (
    DocumentAsset,
    FeishuConnection,
    Quotation,
    QuoteStatus,
)
from quotation.services.feishu_client import (
    FeishuAPIError,
    FeishuClient,
    extract_feishu_token_from_url,
    token_expires_at,
)
from quotation.services.feishu_service import (
    chunk_file_tokens as _chunked_file_tokens,
)
from quotation.services.feishu_service import (
    classify_batch_query_results as _classify_batch_query_results,
)
from quotation.services.feishu_service import (
    feishu_file_not_found as _feishu_file_not_found,
)
from quotation.services.feishu_service import guess_doc_type as _guess_doc_type
from quotation.services.feishu_service import (
    is_folder_drive_item as _is_folder_drive_item,
)
from quotation.services.feishu_service import (
    item_size_bytes as _item_size_bytes,
)
from quotation.services.feishu_service import (
    normalize_bookmarks as _normalize_bookmarks,
)
from quotation.services.feishu_service import (
    serialize_drive_file as _serialize_drive_file,
)
from quotation.services.feishu_service import (
    suggest_unique_file_name as _suggest_unique_file_name,
)

def _client() -> FeishuClient:
    return FeishuClient()


DEFAULT_FEISHU_OAUTH_RETURN_TO = "/quotation/list"


def _sanitize_oauth_return_to(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw or any(char in raw for char in ("\r", "\n")):
        return DEFAULT_FEISHU_OAUTH_RETURN_TO
    parsed = urlsplit(raw)
    if parsed.scheme or parsed.netloc:
        return DEFAULT_FEISHU_OAUTH_RETURN_TO
    if parsed.path != "/quotation" and not parsed.path.startswith(
        "/quotation/"
    ):
        return DEFAULT_FEISHU_OAUTH_RETURN_TO
    return urlunsplit(("", "", parsed.path, parsed.query, parsed.fragment))


def _append_feishu_connected(return_to: str | None) -> str:
    parsed = urlsplit(_sanitize_oauth_return_to(return_to))
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if key != "feishu"]
    query.append(("feishu", "connected"))
    return urlunsplit(("", "", parsed.path, urlencode(query), parsed.fragment))


def _encode_oauth_state(user_email: str, return_to: str | None = None) -> str:
    return jwt.encode(
        {
            "sub": user_email,
            "purpose": "feishu_oauth",
            "nonce": str(uuid4()),
            "return_to": _sanitize_oauth_return_to(return_to),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def _decode_oauth_state(state: str) -> dict:
    try:
        payload = jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise ValueError("invalid OAuth state") from exc
    if payload.get("purpose") != "feishu_oauth" or not payload.get("sub"):
        raise ValueError("invalid OAuth state")
    payload["return_to"] = _sanitize_oauth_return_to(payload.get("return_to"))
    return payload


def _get_connection(user_email: str) -> FeishuConnection | None:
    return FeishuConnection.objects.filter(
        user_email__iexact=user_email
    ).first()


def _ensure_fresh_user_token(connection: FeishuConnection) -> str:
    now = timezone.now()
    access_token = connection.get_access_token()
    refresh_token = connection.get_refresh_token()
    if connection.expires_at and connection.expires_at > now and access_token:
        return access_token
    if not refresh_token:
        raise PermissionError("Feishu authorization expired, please reconnect")
    bundle = _client().refresh_user_token(refresh_token)
    connection.set_access_token(bundle.access_token)
    connection.set_refresh_token(bundle.refresh_token or refresh_token)
    expires = token_expires_at(bundle.expires_in)
    if timezone.is_naive(expires):
        expires = timezone.make_aware(expires, dt_timezone.utc)
    connection.expires_at = expires
    connection.scope = bundle.scope or connection.scope
    connection.save()
    return connection.get_access_token()


def _clear_feishu_file_links(
    *,
    file_token: str,
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
    qs = DocumentAsset.objects.filter(feishu_file_token=token)
    if document_id:
        qs = qs.filter(pk=document_id)
    cleared = qs.update(feishu_file_token=None, feishu_url=None)
    if cleared and quotation_id:
        has_live_feishu_file = (
            DocumentAsset.objects.filter(
                quotation_id=quotation_id,
                source="feishu_upload",
                feishu_file_token__isnull=False,
            )
            .exclude(feishu_file_token="")
            .exists()
        )
        if not has_live_feishu_file:
            Quotation.objects.filter(
                pk=quotation_id,
                status=QuoteStatus.UPLOADED,
            ).update(status=QuoteStatus.GENERATED)
    if cleared or not quotation_id or not doc_type:
        return cleared
    return (
        DocumentAsset.objects.filter(
            quotation_id=quotation_id,
            doc_type=doc_type,
            source="feishu_upload",
            feishu_file_token=token,
        ).update(feishu_file_token=None, feishu_url=None)
        or cleared
    )


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
            if (
                item.get("token") == file_token
                or item.get("name") == file_name
            ):
                return item
        if not data.get("has_more"):
            return None
        page_token = data.get("next_page_token")
        if not page_token:
            return None
    return None


def _require_connection(user_email: str) -> FeishuConnection:
    connection = _get_connection(user_email)
    if not connection or not connection.get_access_token():
        raise PermissionError(
            "Feishu not connected, call /feishu/oauth/start first"
        )
    return connection


def _resolve_folder_token(
    *,
    folder: str | None,
    connection: FeishuConnection,
    access_token: str,
    allow_root_fallback: bool = True,
) -> tuple[str, str | None, bool]:
    client = _client()
    raw = (folder or "").strip()
    if raw.lower() in {"root", "my_space", "__root__"}:
        meta = client.get_root_folder_meta(access_token)
        root_token = str(meta.get("token") or "")
        if not root_token:
            raise ValueError("无法获取飞书「我的空间」根目录")
        return root_token, "我的空间", True

    if raw:
        folder_token = extract_feishu_token_from_url(raw)
        folder_name = None
        try:
            meta = client.get_folder_meta(access_token, folder_token)
            folder_name = str(meta.get("name") or "").strip() or None
            folder_token = str(meta.get("token") or folder_token)
        except FeishuAPIError:
            folder_name = None
        return folder_token, folder_name, False

    if connection.preferred_folder_token:
        return (
            connection.preferred_folder_token,
            connection.preferred_folder_name,
            False,
        )

    if not allow_root_fallback:
        raise ValueError("请先选择飞书目录，或在请求中传入 folder")

    meta = client.get_root_folder_meta(access_token)
    root_token = str(meta.get("token") or "")
    if not root_token:
        if settings.FEISHU_TEST_FOLDER_TOKEN:
            return settings.FEISHU_TEST_FOLDER_TOKEN, "fallback", False
        raise ValueError("无法获取飞书「我的空间」根目录")
    return root_token, "我的空间", True


def _is_shared_space_root(
    meta: dict,
    *,
    root_token: str,
    my_folder_tokens: set[str],
) -> bool:
    """
    Feishu shared-space roots use parentId=0 (same as My Space).

    Exclude My Space root and direct My Folders children.
    """
    token = str(meta.get("token") or "").strip()
    if not token or token == root_token or token in my_folder_tokens:
        return False
    parent_id = str(meta.get("parentId") or meta.get("parent_id") or "0")
    return parent_id in {"0", ""}


def _filter_accessible_shared_folders(
    *,
    client: FeishuClient,
    access_token: str,
    candidates: list[dict],
    root_token: str,
    my_folder_tokens: set[str],
) -> list[dict]:
    """
    Keep shared folders the current user can actually open.

    Feishu does not expose a reliable "all shared roots" listing for every
    tenant, and visible shared folders can be nested under another user's
    folder. For upload folder picking, accessibility matters more than
    whether the folder is a top-level shared-space root.
    """
    enriched: list[dict] = []
    seen: set[str] = set()
    for item in candidates:
        token = str(item.get("token") or "").strip()
        if not token or token in seen:
            continue
        if token == root_token or token in my_folder_tokens:
            continue
        try:
            meta = client.get_folder_meta(access_token, token)
        except FeishuAPIError:
            continue
        resolved_token = str(meta.get("token") or token)
        if (
            not resolved_token
            or resolved_token == root_token
            or resolved_token in my_folder_tokens
        ):
            continue
        seen.add(resolved_token)
        enriched.append(
            {
                "token": resolved_token,
                "name": str(meta.get("name") or item.get("name") or token),
                "type": "folder",
                "_id": str(meta.get("id") or ""),
                "_parent_id": str(
                    meta.get("parentId") or meta.get("parent_id") or ""
                ),
            }
        )

    candidate_ids = {item["_id"] for item in enriched if item.get("_id")}
    folders: list[dict] = []
    for item in enriched:
        parent_id = item.get("_parent_id") or ""
        if parent_id and parent_id in candidate_ids:
            continue
        folders.append(
            {
                "token": item["token"],
                "name": item["name"],
                "type": "folder",
            }
        )
    return folders


def _upsert_shared_bookmark(
    connection: FeishuConnection,
    *,
    token: str,
    name: str | None,
) -> list[dict]:
    bookmarks = _normalize_bookmarks(connection.shared_folder_bookmarks)
    token = str(token or "").strip()
    if not token:
        return bookmarks
    display = (name or "").strip() or token
    updated = False
    for item in bookmarks:
        if item["token"] == token:
            item["name"] = display
            updated = True
            break
    if not updated:
        bookmarks.insert(
            0, {"token": token, "name": display, "type": "folder"}
        )
    connection.shared_folder_bookmarks = bookmarks[:50]
    connection.save(update_fields=["shared_folder_bookmarks", "updated_at"])
    return bookmarks


def _remove_shared_bookmark(
    connection: FeishuConnection,
    token: str,
) -> list[dict]:
    token = str(token or "").strip()
    bookmarks = [
        item
        for item in _normalize_bookmarks(connection.shared_folder_bookmarks)
        if item["token"] != token
    ]
    connection.shared_folder_bookmarks = bookmarks
    connection.save(update_fields=["shared_folder_bookmarks", "updated_at"])
    return bookmarks


def _discover_shared_folders(
    *,
    client: FeishuClient,
    access_token: str,
    my_folder_tokens: set[str],
    root_token: str,
) -> list[dict]:
    """
    Best-effort discovery of shared roots via Search v2.

    Requires search:docs:read. Fail soft if scope is missing.
    Returns visible shared folders that the current user can open.
    """
    discovered: dict[str, dict] = {}
    queries = [
        "文件夹",
        "folder",
        "共享",
        "t",
        "a",
        "e",
        "o",
        "*",
        "-",
        "_",
        "1",
    ]
    for query in queries:
        try:
            items = client.search_folders(
                access_token, query=query, page_size=20
            )
        except FeishuAPIError:
            break
        for item in items:
            token = str(item.get("token") or "").strip()
            if not token or token == root_token or token in my_folder_tokens:
                continue
            discovered[token] = {
                "token": token,
                "name": item.get("name") or token,
                "type": "folder",
            }
        if len(discovered) >= 30:
            break
    return _filter_accessible_shared_folders(
        client=client,
        access_token=access_token,
        candidates=list(discovered.values()),
        root_token=root_token,
        my_folder_tokens=my_folder_tokens,
    )
