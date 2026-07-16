from __future__ import annotations

from datetime import timezone as dt_timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.utils import timezone
from djangorestframework_camel_case.parser import (
    CamelCaseFormParser,
    CamelCaseJSONParser,
    CamelCaseMultiPartParser,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.models import (
    DocumentAsset,
    DocumentType,
    FeishuConnection,
    Quotation,
    QuoteStatus,
)
from quotation.permissions import user_display_email
from quotation.serializers import build_feishu_file_url
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
from quotation.services.quotation_service import create_version_snapshot
from quotation.services.storage import (
    delete_document,
    document_storage_key,
    write_document,
)
from quotation.services.upload_validation import validate_quotation_upload


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


class FeishuStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        email = user_display_email(request.user)
        connection = _get_connection(email)
        return Response(
            {
                "configured": bool(
                    settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET
                ),
                "connected": bool(
                    connection and connection.get_access_token()
                ),
                "feishu_user_name": (
                    connection.feishu_user_name if connection else None
                ),
                "feishu_open_id": (
                    connection.feishu_open_id if connection else None
                ),
                "expires_at": connection.expires_at if connection else None,
                "preferred_folder_token": (
                    connection.preferred_folder_token if connection else None
                ),
                "preferred_folder_name": (
                    connection.preferred_folder_name if connection else None
                ),
                "fallback_folder_token": settings.FEISHU_TEST_FOLDER_TOKEN
                or None,
                "redirect_uri": settings.FEISHU_OAUTH_REDIRECT_URI,
            }
        )


class FeishuOAuthStartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not settings.FEISHU_APP_ID or not settings.FEISHU_APP_SECRET:
            return Response(
                {"detail": "Feishu credentials are not configured"}, status=400
            )
        state = _encode_oauth_state(
            user_display_email(request.user),
            request.query_params.get("return_to"),
        )
        try:
            url = _client().build_user_oauth_url(state)
        except FeishuAPIError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"authorize_url": url})


class FeishuOAuthCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        if not code or not state:
            return Response({"detail": "code and state required"}, status=400)
        try:
            oauth_state = _decode_oauth_state(state)
            user_email = str(oauth_state["sub"]).lower()
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        User = get_user_model()
        user = User.objects.filter(
            Q(email__iexact=user_email) | Q(username__iexact=user_email)
        ).first()
        if not user:
            return Response({"detail": "OAuth user not found"}, status=400)

        client = _client()
        try:
            bundle = client.exchange_code_for_user_token(code)
            profile = client.get_user_info(bundle.access_token)
        except FeishuAPIError as exc:
            return Response(
                {"detail": f"Feishu OAuth failed: {exc}"}, status=400
            )

        connection = _get_connection(user_email)
        if not connection:
            connection = FeishuConnection(user=user, user_email=user_email)
        else:
            connection.user = user
        connection.set_access_token(bundle.access_token)
        connection.set_refresh_token(bundle.refresh_token)
        connection.token_type = bundle.token_type
        expires = token_expires_at(bundle.expires_in)
        if timezone.is_naive(expires):
            expires = timezone.make_aware(expires, dt_timezone.utc)
        connection.expires_at = expires
        connection.scope = bundle.scope
        connection.feishu_open_id = profile.get("open_id")
        connection.feishu_union_id = profile.get("union_id")
        connection.feishu_user_name = profile.get("name") or profile.get(
            "en_name"
        )
        connection.save()

        frontend = settings.FRONTEND_URL.rstrip("/")
        return HttpResponseRedirect(
            f"{frontend}{_append_feishu_connected(oauth_state.get('return_to'))}"
        )


class FeishuPreferredFolderView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        try:
            connection = _require_connection(user_display_email(request.user))
            folder_token = extract_feishu_token_from_url(
                request.data.get("folder_token") or ""
            )
        except (PermissionError, FeishuAPIError) as exc:
            return Response(
                {"detail": str(exc)},
                status=400 if isinstance(exc, FeishuAPIError) else 401,
            )
        connection.preferred_folder_token = folder_token
        connection.preferred_folder_name = (
            request.data.get("folder_name") or ""
        ).strip() or None
        connection.save()
        return Response(
            {
                "preferred_folder_token": folder_token,
                "preferred_folder_name": connection.preferred_folder_name,
            }
        )


class FeishuFolderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            connection = _require_connection(user_display_email(request.user))
            access_token = _ensure_fresh_user_token(connection)
            folder_token, folder_name, is_root = _resolve_folder_token(
                folder=request.query_params.get("folder"),
                connection=connection,
                access_token=access_token,
            )
            raw_folder = (request.query_params.get("folder") or "").strip()
            if (
                raw_folder
                and raw_folder.lower() not in {"root", "my_space", "__root__"}
                and not is_root
            ):
                try:
                    client = _client()
                    root_meta = client.get_root_folder_meta(access_token)
                    root_token = str(root_meta.get("token") or "")
                    root_list = client.list_folder_files(
                        access_token, root_token
                    )
                    my_tokens = {
                        str(item.get("token") or "")
                        for item in (root_list.get("files") or [])
                        if _is_folder_drive_item(item)
                    }
                    # Only pin shared-space roots (parentId=0), not nested
                    # folders — nested items show via expandable tree.
                    if (
                        folder_token
                        and folder_token not in my_tokens
                        and folder_token != root_token
                    ):
                        meta = client.get_folder_meta(
                            access_token, folder_token
                        )
                        if _is_shared_space_root(
                            meta,
                            root_token=root_token,
                            my_folder_tokens=my_tokens,
                        ):
                            _upsert_shared_bookmark(
                                connection,
                                token=str(meta.get("token") or folder_token),
                                name=str(
                                    meta.get("name") or folder_name or ""
                                ).strip()
                                or folder_name,
                            )
                except FeishuAPIError:
                    pass
            data = _client().list_folder_files(
                access_token,
                folder_token,
                page_token=request.query_params.get("page_token"),
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=401)
        except (FeishuAPIError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=400)

        files = [
            _serialize_drive_file(item)
            for item in (data.get("files") or [])
            if item.get("token")
        ]
        return Response(
            {
                "folder_token": folder_token,
                "folder_name": folder_name,
                "is_root": is_root,
                "files": files,
                "has_more": bool(data.get("has_more")),
                "next_page_token": data.get("next_page_token"),
            }
        )


class FeishuSearchView(APIView):
    """Search docs visible to the connected user (incl. shared docs)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        if not query:
            return Response({"detail": "q is required"}, status=400)
        try:
            offset = int(request.query_params.get("offset") or 0)
        except ValueError:
            offset = 0
        try:
            count = int(request.query_params.get("count") or 50)
        except ValueError:
            count = 50
        try:
            connection = _require_connection(user_display_email(request.user))
            access_token = _ensure_fresh_user_token(connection)
            data = _client().search_documents(
                access_token,
                search_key=query,
                count=count,
                offset=offset,
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=401)
        except FeishuAPIError as exc:
            return Response({"detail": str(exc)}, status=400)

        files = []
        for item in data.get("docs_entities") or []:
            token = item.get("docs_token") or ""
            if not token:
                continue
            doc_type = str(item.get("docs_type") or "file").lower()
            files.append(
                {
                    "token": token,
                    "name": item.get("title") or token,
                    "type": doc_type,
                    "parent_token": None,
                    "url": None,
                    "created_time": None,
                    "modified_time": None,
                    "shortcut_info": None,
                    "open_token": token,
                    "owner_id": item.get("owner_id"),
                }
            )
        return Response(
            {
                "query": query,
                "files": files,
                "has_more": bool(data.get("has_more")),
                "total": data.get("total"),
                "offset": offset,
            }
        )


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


class FeishuDriveTreeView(APIView):
    """
    Feishu Drive style navigation roots:
    - my_folders: children under My Space
    - shared_folders: bookmarks + discovered shared folders
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            connection = _require_connection(user_display_email(request.user))
            access_token = _ensure_fresh_user_token(connection)
            client = _client()
            root_meta = client.get_root_folder_meta(access_token)
            root_token = str(root_meta.get("token") or "")
            if not root_token:
                raise ValueError("无法获取飞书「我的空间」根目录")
            listing = client.list_folder_files(access_token, root_token)
            my_items = [
                _serialize_drive_file(item)
                for item in (listing.get("files") or [])
                if item.get("token")
            ]
            my_folders = [
                {
                    "token": item.get("open_token") or item["token"],
                    "name": item["name"] or item["token"],
                    "type": "folder",
                }
                for item in my_items
                if _is_folder_drive_item(
                    {
                        "type": item.get("type"),
                        "token": item.get("token"),
                        "shortcut_info": item.get("shortcut_info") or {},
                    }
                )
            ]
            my_folder_tokens = {item["token"] for item in my_folders}
            bookmarks = _normalize_bookmarks(
                connection.shared_folder_bookmarks
            )
            discover = []
            if not bookmarks:
                discover = _discover_shared_folders(
                    client=client,
                    access_token=access_token,
                    my_folder_tokens=my_folder_tokens,
                    root_token=root_token,
                )
            shared_folders = _filter_accessible_shared_folders(
                client=client,
                access_token=access_token,
                candidates=bookmarks + discover,
                root_token=root_token,
                my_folder_tokens=my_folder_tokens,
            )
            # Persist pruned roots so nested leftovers leave the sidebar.
            root_tokens = {item["token"] for item in shared_folders}
            pruned = [
                item for item in bookmarks if item["token"] in root_tokens
            ]
            for item in shared_folders:
                if item["token"] not in {b["token"] for b in pruned}:
                    pruned.append(item)
            if pruned != bookmarks:
                connection.shared_folder_bookmarks = pruned[:50]
                connection.save(
                    update_fields=["shared_folder_bookmarks", "updated_at"]
                )
            return Response(
                {
                    "my_root": {
                        "token": root_token,
                        "name": "我的文件夹",
                    },
                    "my_folders": my_folders,
                    "my_files": [
                        item
                        for item in my_items
                        if not _is_folder_drive_item(
                            {
                                "type": item.get("type"),
                                "token": item.get("token"),
                                "shortcut_info": item.get("shortcut_info")
                                or {},
                            }
                        )
                    ],
                    "shared_folders": shared_folders,
                    "can_discover_shared": "search:docs:read"
                    in (connection.scope or ""),
                }
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=401)
        except (FeishuAPIError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=400)

    def post(self, request):
        """Bookmark a shared folder for the Drive sidebar."""
        try:
            connection = _require_connection(user_display_email(request.user))
            access_token = _ensure_fresh_user_token(connection)
            raw = (
                request.data.get("folder_token")
                or request.data.get("folder")
                or ""
            )
            folder_token = extract_feishu_token_from_url(str(raw))
            folder_name = (
                request.data.get("folder_name") or ""
            ).strip() or None
            client = _client()
            try:
                meta = client.get_folder_meta(access_token, folder_token)
                folder_token = str(meta.get("token") or folder_token)
                folder_name = (
                    str(meta.get("name") or "").strip() or folder_name
                )
                root_meta = client.get_root_folder_meta(access_token)
                root_token = str(root_meta.get("token") or "")
                root_list = client.list_folder_files(access_token, root_token)
                my_tokens = {
                    str(item.get("token") or "")
                    for item in (root_list.get("files") or [])
                    if _is_folder_drive_item(item)
                }
                # Prefer pinning shared-space root when user pastes a nest.
                if not _is_shared_space_root(
                    meta,
                    root_token=root_token,
                    my_folder_tokens=my_tokens,
                ):
                    # Keep nested open/pin behavior for deep links; tree
                    # filter will hide non-roots unless user expands parent.
                    pass
            except FeishuAPIError:
                pass
            bookmarks = _upsert_shared_bookmark(
                connection,
                token=folder_token,
                name=folder_name,
            )
            return Response({"shared_folders": bookmarks})
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=401)
        except FeishuAPIError as exc:
            return Response({"detail": str(exc)}, status=400)

    def delete(self, request):
        try:
            connection = _require_connection(user_display_email(request.user))
            token = extract_feishu_token_from_url(
                str(
                    request.data.get("folder_token")
                    or request.query_params.get("folder")
                    or ""
                )
            )
            bookmarks = _remove_shared_bookmark(connection, token)
            return Response({"shared_folders": bookmarks})
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=401)
        except FeishuAPIError as exc:
            return Response({"detail": str(exc)}, status=400)


class FeishuImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, file_token: str):
        connection = _get_connection(user_display_email(request.user))
        if not connection:
            return Response({"detail": "Feishu not connected"}, status=401)
        try:
            access_token = _ensure_fresh_user_token(connection)
            content, mime_type, resolved_name = _client().download_drive_item(
                access_token,
                file_token=file_token,
                file_type=request.query_params.get("file_type"),
                file_name=request.query_params.get("file_name"),
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=401)
        except FeishuAPIError as exc:
            detail = str(exc)
            if (
                exc.code == 99991679
                or "drive:export" in detail
                or "docs:document:export" in detail
            ):
                detail = (
                    "缺少飞书导出权限。请在开放平台开通 "
                    "drive:export:readonly（或 docs:document:export），"
                    "发版后重新点击「连接飞书」授权，再导入在线表格。"
                )
            return Response({"detail": detail}, status=400)

        if not content:
            return Response({"detail": "Downloaded empty file"}, status=400)

        safe_name = (
            resolved_name
            or request.query_params.get("file_name")
            or f"{file_token}.bin"
        )
        quotation_id = request.query_params.get("quotation_id")
        asset_id = str(uuid4())
        storage_key = document_storage_key(asset_id, quotation_id or None)
        write_document(content, storage_key)
        doc_type = _guess_doc_type(safe_name, mime_type)
        feishu_url = request.query_params.get(
            "file_url"
        ) or build_feishu_file_url(file_token)
        try:
            asset = DocumentAsset.objects.create(
                id=asset_id,
                quotation_id=quotation_id or None,
                doc_type=doc_type,
                file_name=safe_name,
                mime_type=mime_type or "application/octet-stream",
                storage_key=storage_key,
                size_bytes=len(content),
                source="feishu",
                feishu_file_token=file_token,
                feishu_url=feishu_url,
                created_by_email=user_display_email(request.user),
            )
        except Exception:
            delete_document(storage_key)
            raise
        return Response(
            {
                "file_token": file_token,
                "file_name": safe_name,
                "mime_type": mime_type,
                "size_bytes": len(content),
                "storage_key": storage_key,
                "document_id": asset.id,
                "doc_type": doc_type,
                "url": feishu_url,
            }
        )


class FeishuFileAccessView(APIView):
    """
    Check whether a Feishu drive file is still accessible.

    When missing, clear stored links on matching DocumentAsset rows.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, file_token: str):
        file_token = str(file_token or "").strip()
        if not file_token:
            return Response({"detail": "file_token required"}, status=400)
        connection = _get_connection(user_display_email(request.user))
        if not connection:
            return Response({"detail": "Feishu not connected"}, status=401)
        quotation_id = (request.query_params.get("quotation_id") or "").strip()
        doc_type = (request.query_params.get("doc_type") or "").strip().lower()
        document_id = (request.query_params.get("document_id") or "").strip()
        if doc_type and doc_type not in {DocumentType.EXCEL, DocumentType.PDF}:
            return Response(
                {"detail": "doc_type must be excel or pdf"}, status=400
            )
        try:
            access_token = _ensure_fresh_user_token(connection)
            client = _client()
            meta = client.batch_query_file_meta(
                access_token,
                file_token,
                doc_type="file",
                with_url=True,
            )
            resolved_token = str(meta.get("doc_token") or file_token)
            if str(meta.get("doc_type") or "").lower() == "file":
                client.download_file(access_token, resolved_token)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=401)
        except FeishuAPIError as exc:
            if _feishu_file_not_found(exc):
                cleared = _clear_feishu_file_links(
                    file_token=file_token,
                    quotation_id=quotation_id or None,
                    doc_type=doc_type or None,
                    document_id=document_id or None,
                )
                return Response({"exists": False, "cleared": cleared > 0})
            # Cannot confirm deletion (e.g. permission/type mismatch).
            return Response(
                {
                    "exists": True,
                    "file_token": file_token,
                    "url": build_feishu_file_url(file_token),
                    "checked": False,
                }
            )

        feishu_url = meta.get("url") or build_feishu_file_url(resolved_token)
        return Response(
            {
                "exists": True,
                "file_token": resolved_token,
                "url": feishu_url,
                "name": meta.get("title"),
            }
        )


class FeishuFileAccessBatchView(APIView):
    """
    Validate multiple Feishu drive files and clear stale stored links.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw_items = request.data.get("items") or []
        if not isinstance(raw_items, list):
            return Response({"detail": "items must be a list"}, status=400)

        items: list[dict[str, str]] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            file_token = str(raw.get("file_token") or "").strip()
            if not file_token:
                continue
            doc_type = str(raw.get("doc_type") or "").strip().lower()
            if doc_type and doc_type not in {
                DocumentType.EXCEL,
                DocumentType.PDF,
            }:
                return Response(
                    {"detail": "doc_type must be excel or pdf"},
                    status=400,
                )
            items.append(
                {
                    "file_token": file_token,
                    "quotation_id": str(raw.get("quotation_id") or "").strip(),
                    "doc_type": doc_type,
                    "document_id": str(raw.get("document_id") or "").strip(),
                }
            )
        if not items:
            return Response({"results": [], "cleared_count": 0})

        connection = _get_connection(user_display_email(request.user))
        if not connection:
            return Response({"detail": "Feishu not connected"}, status=401)

        unique_tokens = list(
            dict.fromkeys(item["file_token"] for item in items)
        )
        existing_tokens: set[str] = set()
        missing_tokens: set[str] = set()
        try:
            access_token = _ensure_fresh_user_token(connection)
            client = _client()
            for chunk in _chunked_file_tokens(unique_tokens):
                metas, failed_list = client.batch_query_files_meta(
                    access_token,
                    chunk,
                    doc_type="file",
                    with_url=False,
                )
                chunk_existing, chunk_missing = _classify_batch_query_results(
                    metas,
                    failed_list,
                    chunk,
                )
                existing_tokens.update(chunk_existing)
                missing_tokens.update(chunk_missing)
                for token in tuple(chunk_existing):
                    try:
                        client.download_file(access_token, token)
                    except FeishuAPIError as exc:
                        if _feishu_file_not_found(exc):
                            existing_tokens.discard(token)
                            missing_tokens.add(token)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=401)
        except FeishuAPIError as exc:
            return Response({"detail": str(exc)}, status=400)

        results = []
        cleared_count = 0
        for item in items:
            file_token = item["file_token"]
            if file_token in missing_tokens:
                cleared = _clear_feishu_file_links(
                    file_token=file_token,
                    quotation_id=item["quotation_id"] or None,
                    doc_type=item["doc_type"] or None,
                    document_id=item["document_id"] or None,
                )
                if cleared:
                    cleared_count += cleared
                results.append(
                    {
                        "file_token": file_token,
                        "exists": False,
                        "cleared": cleared > 0,
                        "quotation_id": item["quotation_id"] or None,
                        "doc_type": item["doc_type"] or None,
                        "document_id": item["document_id"] or None,
                    }
                )
                continue
            results.append(
                {
                    "file_token": file_token,
                    "exists": True,
                    "quotation_id": item["quotation_id"] or None,
                    "doc_type": item["doc_type"] or None,
                    "document_id": item["document_id"] or None,
                }
            )

        return Response({"results": results, "cleared_count": cleared_count})


class FeishuFileContentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, file_token: str):
        connection = _get_connection(user_display_email(request.user))
        if not connection:
            return Response({"detail": "Feishu not connected"}, status=401)
        try:
            access_token = _ensure_fresh_user_token(connection)
            content, mime_type, resolved_name = _client().download_drive_item(
                access_token,
                file_token=file_token,
                file_type=request.query_params.get("file_type"),
                file_name=request.query_params.get("file_name"),
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=401)
        except FeishuAPIError as exc:
            detail = str(exc)
            if (
                exc.code == 99991679
                or "drive:export" in detail
                or "docs:document:export" in detail
            ):
                detail = (
                    "缺少飞书导出权限。请在开放平台开通 "
                    "drive:export:readonly（或 docs:document:export），"
                    "发版后重新点击「连接飞书」授权，再下载在线表格。"
                )
            return Response({"detail": detail}, status=400)

        filename = (
            resolved_name
            or request.query_params.get("file_name")
            or f"{file_token}.bin"
        )
        response = HttpResponse(
            content, content_type=mime_type or "application/octet-stream"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class FeishuUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [
        CamelCaseMultiPartParser,
        CamelCaseFormParser,
        CamelCaseJSONParser,
    ]

    def post(self, request):
        try:
            connection = _require_connection(user_display_email(request.user))
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=401)

        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "file required"}, status=400)
        try:
            validate_quotation_upload(upload)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        content = upload.read()
        if not content:
            return Response({"detail": "Empty file"}, status=400)

        file_name = upload.name or f"upload-{uuid4().hex}.bin"
        conflict_action = (
            str(request.data.get("conflict_action") or "").strip().lower()
        )
        if conflict_action not in {"", "reuse", "rename"}:
            return Response(
                {"detail": "conflict_action must be reuse or rename"},
                status=400,
            )

        try:
            client = _client()
            access_token = _ensure_fresh_user_token(connection)
            folder_token, _, _ = _resolve_folder_token(
                folder=request.data.get("folder"),
                connection=connection,
                access_token=access_token,
            )
            existing = _find_existing_file_in_folder(
                client=client,
                access_token=access_token,
                folder_token=folder_token,
                file_name=file_name,
            )
            reused_existing = False
            renamed_from = None

            if existing is not None and not conflict_action:
                existing_token = str(existing.get("token") or "")
                existing_url = existing.get("url") or (
                    build_feishu_file_url(existing_token)
                    if existing_token
                    else None
                )
                existing_names = _list_folder_file_names(
                    client=client,
                    access_token=access_token,
                    folder_token=folder_token,
                )
                return Response(
                    {
                        "detail": "same file name already exists in folder",
                        "code": "feishu_name_conflict",
                        "folder_token": folder_token,
                        "file_name": file_name,
                        "size_bytes": len(content),
                        "existing": {
                            "file_token": existing_token,
                            "file_name": existing.get("name") or file_name,
                            "url": existing_url,
                            "size_bytes": _item_size_bytes(existing),
                        },
                        "suggested_file_name": _suggest_unique_file_name(
                            file_name, existing_names
                        ),
                        "actions": ["reuse", "rename", "cancel"],
                    },
                    status=409,
                )

            if existing is not None and conflict_action == "reuse":
                reused_existing = True
                data = {
                    "file_token": existing.get("token"),
                    "token": existing.get("token"),
                    "url": existing.get("url"),
                }
            else:
                upload_name = file_name
                if existing is not None and conflict_action == "rename":
                    existing_names = _list_folder_file_names(
                        client=client,
                        access_token=access_token,
                        folder_token=folder_token,
                    )
                    upload_name = _suggest_unique_file_name(
                        file_name, existing_names
                    )
                    renamed_from = file_name
                    file_name = upload_name

                data = client.upload_file(
                    access_token,
                    folder_token=folder_token,
                    file_name=file_name,
                    content=content,
                )
                uploaded_token = str(
                    data.get("file_token") or data.get("token") or ""
                )
                if uploaded_token and not data.get("url"):
                    uploaded_meta = _find_file_by_token_or_name_in_folder(
                        client=client,
                        access_token=access_token,
                        folder_token=folder_token,
                        file_token=uploaded_token,
                        file_name=file_name,
                    )
                    if uploaded_meta and uploaded_meta.get("url"):
                        data["url"] = uploaded_meta.get("url")
        except (FeishuAPIError, ValueError, PermissionError) as exc:
            code = 401 if isinstance(exc, PermissionError) else 400
            return Response({"detail": str(exc)}, status=code)

        file_token = str(data.get("file_token") or data.get("token") or "")
        if not file_token:
            return Response(
                {"detail": f"upload succeeded but file_token missing: {data}"},
                status=400,
            )

        doc_type = _guess_doc_type(file_name, upload.content_type)
        quotation_id = request.data.get("quotation_id") or None
        feishu_url = data.get("url") or build_feishu_file_url(file_token)
        local_storage_key = None
        try:
            with transaction.atomic():
                if reused_existing:
                    matching_assets = DocumentAsset.objects.filter(
                        quotation_id=quotation_id,
                        doc_type=doc_type,
                        source="feishu_upload",
                        feishu_file_token=file_token,
                    )
                    existing_asset = matching_assets.order_by(
                        "-created_at"
                    ).first()
                    if existing_asset:
                        for duplicate in matching_assets.exclude(
                            pk=existing_asset.pk
                        ):
                            delete_document(duplicate.storage_key)
                            duplicate.delete()
                        local_storage_key = document_storage_key(
                            existing_asset.id,
                            quotation_id,
                        )
                        write_document(content, local_storage_key)
                        document_values = {
                            "file_name": file_name,
                            "mime_type": upload.content_type
                            or "application/octet-stream",
                            "storage_key": local_storage_key,
                            "size_bytes": len(content),
                            "feishu_url": feishu_url,
                            "created_by_email": user_display_email(
                                request.user
                            ),
                        }
                        for field, value in document_values.items():
                            setattr(existing_asset, field, value)
                        existing_asset.save(
                            update_fields=[*document_values.keys()]
                        )
                    else:
                        asset_id = str(uuid4())
                        local_storage_key = document_storage_key(
                            asset_id, quotation_id
                        )
                        write_document(content, local_storage_key)
                        DocumentAsset.objects.create(
                            id=asset_id,
                            quotation_id=quotation_id,
                            doc_type=doc_type,
                            source="feishu_upload",
                            feishu_file_token=file_token,
                            file_name=file_name,
                            mime_type=upload.content_type
                            or "application/octet-stream",
                            storage_key=local_storage_key,
                            size_bytes=len(content),
                            feishu_url=feishu_url,
                            created_by_email=user_display_email(request.user),
                        )
                else:
                    asset_id = str(uuid4())
                    local_storage_key = document_storage_key(
                        asset_id, quotation_id
                    )
                    write_document(content, local_storage_key)
                    DocumentAsset.objects.create(
                        id=asset_id,
                        quotation_id=quotation_id,
                        doc_type=doc_type,
                        source="feishu_upload",
                        feishu_file_token=file_token,
                        file_name=file_name,
                        mime_type=upload.content_type
                        or "application/octet-stream",
                        storage_key=local_storage_key,
                        size_bytes=len(content),
                        feishu_url=feishu_url,
                        created_by_email=user_display_email(request.user),
                    )
                if quotation_id:
                    quotation = Quotation.objects.filter(
                        pk=quotation_id
                    ).first()
                    if quotation:
                        if quotation.status != QuoteStatus.UPLOADED:
                            quotation.status = QuoteStatus.UPLOADED
                            quotation.save(
                                update_fields=["status", "updated_at"]
                            )
                        create_version_snapshot(
                            quotation,
                            operator_email=user_display_email(request.user),
                            notes="Uploaded to Feishu",
                        )
        except Exception:  # noqa: BLE001
            if local_storage_key:
                delete_document(local_storage_key)
            if not reused_existing:
                try:
                    client.delete_file(access_token, file_token)
                except Exception:  # noqa: BLE001
                    pass
            return Response(
                {
                    "detail": (
                        "Upload could not be recorded; "
                        "no quotation changes were saved"
                    )
                },
                status=500,
            )

        payload = {
            "file_token": file_token,
            "file_name": file_name,
            "folder_token": folder_token,
            "url": feishu_url,
            "size_bytes": len(content),
            "reused_existing": reused_existing,
        }
        if renamed_from:
            payload["renamed_from"] = renamed_from
        return Response(payload)


class FeishuHealthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            token = _client().get_tenant_access_token()
        except FeishuAPIError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"ok": True, "tenant_token_prefix": token[:8] + "..."})
