from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.permissions import user_display_email
from quotation.services.feishu_client import (
    FeishuAPIError,
    extract_feishu_token_from_url,
)

from . import common

class FeishuFolderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            connection = common._require_connection(user_display_email(request.user))
            access_token = common._ensure_fresh_user_token(connection)
            folder_token, folder_name, is_root = common._resolve_folder_token(
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
                    client = common._client()
                    root_meta = client.get_root_folder_meta(access_token)
                    root_token = str(root_meta.get("token") or "")
                    root_list = client.list_folder_files(
                        access_token, root_token
                    )
                    my_tokens = {
                        str(item.get("token") or "")
                        for item in (root_list.get("files") or [])
                        if common._is_folder_drive_item(item)
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
                        if common._is_shared_space_root(
                            meta,
                            root_token=root_token,
                            my_folder_tokens=my_tokens,
                        ):
                            common._upsert_shared_bookmark(
                                connection,
                                token=str(meta.get("token") or folder_token),
                                name=str(
                                    meta.get("name") or folder_name or ""
                                ).strip()
                                or folder_name,
                            )
                except FeishuAPIError:
                    pass
            data = common._client().list_folder_files(
                access_token,
                folder_token,
                page_token=request.query_params.get("page_token"),
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=401)
        except (FeishuAPIError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=400)

        files = [
            common._serialize_drive_file(item)
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
            connection = common._require_connection(user_display_email(request.user))
            access_token = common._ensure_fresh_user_token(connection)
            data = common._client().search_documents(
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


class FeishuDriveTreeView(APIView):
    """
    Feishu Drive style navigation roots:
    - my_folders: children under My Space
    - shared_folders: bookmarks + discovered shared folders
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            connection = common._require_connection(user_display_email(request.user))
            access_token = common._ensure_fresh_user_token(connection)
            client = common._client()
            root_meta = client.get_root_folder_meta(access_token)
            root_token = str(root_meta.get("token") or "")
            if not root_token:
                raise ValueError("无法获取飞书「我的空间」根目录")
            listing = client.list_folder_files(access_token, root_token)
            my_items = [
                common._serialize_drive_file(item)
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
                if common._is_folder_drive_item(
                    {
                        "type": item.get("type"),
                        "token": item.get("token"),
                        "shortcut_info": item.get("shortcut_info") or {},
                    }
                )
            ]
            my_folder_tokens = {item["token"] for item in my_folders}
            bookmarks = common._normalize_bookmarks(
                connection.shared_folder_bookmarks
            )
            discover = []
            if not bookmarks:
                discover = common._discover_shared_folders(
                    client=client,
                    access_token=access_token,
                    my_folder_tokens=my_folder_tokens,
                    root_token=root_token,
                )
            shared_folders = common._filter_accessible_shared_folders(
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
                        if not common._is_folder_drive_item(
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
            connection = common._require_connection(user_display_email(request.user))
            access_token = common._ensure_fresh_user_token(connection)
            raw = (
                request.data.get("folder_token")
                or request.data.get("folder")
                or ""
            )
            folder_token = extract_feishu_token_from_url(str(raw))
            folder_name = (
                request.data.get("folder_name") or ""
            ).strip() or None
            client = common._client()
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
                    if common._is_folder_drive_item(item)
                }
                # Prefer pinning shared-space root when user pastes a nest.
                if not common._is_shared_space_root(
                    meta,
                    root_token=root_token,
                    my_folder_tokens=my_tokens,
                ):
                    # Keep nested open/pin behavior for deep links; tree
                    # filter will hide non-roots unless user expands parent.
                    pass
            except FeishuAPIError:
                pass
            bookmarks = common._upsert_shared_bookmark(
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
            connection = common._require_connection(user_display_email(request.user))
            token = extract_feishu_token_from_url(
                str(
                    request.data.get("folder_token")
                    or request.query_params.get("folder")
                    or ""
                )
            )
            bookmarks = common._remove_shared_bookmark(connection, token)
            return Response({"shared_folders": bookmarks})
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=401)
        except FeishuAPIError as exc:
            return Response({"detail": str(exc)}, status=400)
