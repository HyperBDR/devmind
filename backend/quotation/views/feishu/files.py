from __future__ import annotations

from uuid import uuid4

from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.models import DocumentAsset, DocumentType
from quotation.permissions import user_display_email
from quotation.serializers import build_feishu_file_url
from quotation.services.feishu_client import FeishuAPIError
from quotation.services.storage import (
    delete_document,
    document_storage_key,
    write_document,
)

from . import common

class FeishuImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, file_token: str):
        connection = common._get_connection(user_display_email(request.user))
        if not connection:
            return Response({"detail": "Feishu not connected"}, status=401)
        try:
            access_token = common._ensure_fresh_user_token(connection)
            content, mime_type, resolved_name = common._client().download_drive_item(
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
        doc_type = common._guess_doc_type(safe_name, mime_type)
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
        connection = common._get_connection(user_display_email(request.user))
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
            access_token = common._ensure_fresh_user_token(connection)
            client = common._client()
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
            if common._feishu_file_not_found(exc):
                cleared = common._clear_feishu_file_links(
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

        connection = common._get_connection(user_display_email(request.user))
        if not connection:
            return Response({"detail": "Feishu not connected"}, status=401)

        unique_tokens = list(
            dict.fromkeys(item["file_token"] for item in items)
        )
        existing_tokens: set[str] = set()
        missing_tokens: set[str] = set()
        try:
            access_token = common._ensure_fresh_user_token(connection)
            client = common._client()
            for chunk in common._chunked_file_tokens(unique_tokens):
                metas, failed_list = client.batch_query_files_meta(
                    access_token,
                    chunk,
                    doc_type="file",
                    with_url=False,
                )
                chunk_existing, chunk_missing = common._classify_batch_query_results(
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
                        if common._feishu_file_not_found(exc):
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
                cleared = common._clear_feishu_file_links(
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
        connection = common._get_connection(user_display_email(request.user))
        if not connection:
            return Response({"detail": "Feishu not connected"}, status=401)
        try:
            access_token = common._ensure_fresh_user_token(connection)
            content, mime_type, resolved_name = common._client().download_drive_item(
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
