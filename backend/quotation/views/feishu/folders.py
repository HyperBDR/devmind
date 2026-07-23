from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.access import forbidden_response
from quotation.services.feishu_client import (
    FeishuAPIError,
)

from . import common

class FeishuFolderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            client, access_token, root_folder_token = (
                common._system_drive_context()
            )
            folder_token = common._managed_folder_token(
                client=client,
                access_token=access_token,
                requested_token=(
                    request.query_params.get("folder_token")
                    or root_folder_token
                ),
            )
            data = client.list_folder_files(
                access_token,
                folder_token,
                page_token=request.query_params.get("page_token"),
            )
        except PermissionError:
            return forbidden_response()
        except FeishuAPIError as exc:
            return common._feishu_error_response(
                exc, operation="folder listing"
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        files = [
            common._serialize_drive_file(item)
            for item in (data.get("files") or [])
            if item.get("token")
            and str(item.get("type") or "").lower()
            in {"folder", "drive#folder"}
        ]
        return Response(
            {
                "folder_token": folder_token,
                "folder_name": (
                    common.ARCHIVE_FOLDER_LABEL
                    if folder_token == root_folder_token
                    else request.query_params.get("folder_name") or "Folder"
                ),
                "root_folder_token": root_folder_token,
                "is_root": folder_token == root_folder_token,
                "files": files,
                "has_more": bool(data.get("has_more")),
                "next_page_token": data.get("next_page_token"),
            }
        )


class FeishuSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "query": (request.query_params.get("q") or "").strip(),
                "files": [],
                "has_more": False,
                "total": 0,
                "offset": 0,
            }
        )


class FeishuDriveTreeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            _, _, folder_token = common._system_drive_context()
            return Response(
                {
                    "my_root": {
                        "token": folder_token,
                        "name": common.ARCHIVE_FOLDER_LABEL,
                    },
                    "my_folders": [],
                    "my_files": [],
                    "shared_folders": [],
                    "can_discover_shared": False,
                }
            )
        except (FeishuAPIError, ValueError) as exc:
            if isinstance(exc, FeishuAPIError):
                return common._feishu_error_response(
                    exc, operation="drive tree"
                )
            return Response({"detail": str(exc)}, status=400)

    def post(self, request):
        return Response({"detail": "Folder picker is disabled"}, status=400)

    def delete(self, request):
        return Response({"detail": "Folder picker is disabled"}, status=400)
