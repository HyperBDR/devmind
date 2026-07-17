from __future__ import annotations

from uuid import uuid4

from django.db import transaction
from djangorestframework_camel_case.parser import (
    CamelCaseFormParser,
    CamelCaseJSONParser,
    CamelCaseMultiPartParser,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.models import DocumentAsset, Quotation, QuoteStatus
from quotation.permissions import user_display_email
from quotation.serializers import build_feishu_file_url
from quotation.services.feishu_client import FeishuAPIError
from quotation.services.quotation_service import create_version_snapshot
from quotation.services.storage import (
    delete_document,
    document_storage_key,
    write_document,
)
from quotation.services.upload_validation import validate_quotation_upload

from . import common

class FeishuUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [
        CamelCaseMultiPartParser,
        CamelCaseFormParser,
        CamelCaseJSONParser,
    ]

    def post(self, request):
        try:
            connection = common._require_connection(user_display_email(request.user))
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
            client = common._client()
            access_token = common._ensure_fresh_user_token(connection)
            folder_token, _, _ = common._resolve_folder_token(
                folder=request.data.get("folder"),
                connection=connection,
                access_token=access_token,
            )
            existing = common._find_existing_file_in_folder(
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
                existing_names = common._list_folder_file_names(
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
                            "size_bytes": common._item_size_bytes(existing),
                        },
                        "suggested_file_name": common._suggest_unique_file_name(
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
                    existing_names = common._list_folder_file_names(
                        client=client,
                        access_token=access_token,
                        folder_token=folder_token,
                    )
                    upload_name = common._suggest_unique_file_name(
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
                    uploaded_meta = common._find_file_by_token_or_name_in_folder(
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

        doc_type = common._guess_doc_type(file_name, upload.content_type)
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
