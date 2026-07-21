from __future__ import annotations

from uuid import uuid4

from django.conf import settings
from django.db import transaction
from djangorestframework_camel_case.parser import (
    CamelCaseFormParser,
    CamelCaseJSONParser,
    CamelCaseMultiPartParser,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.access import (
    DocumentAction,
    filter_accessible_documents,
    get_accessible_quotation,
)
from quotation.audit import set_request_audit_target
from quotation.models import DocumentAsset, QuoteStatus
from quotation.permissions import user_display_email
from quotation.serializers import build_feishu_file_url
from quotation.services.feishu_client import FeishuAPIError
from quotation.services.quotation_service import create_version_snapshot
from quotation.services.storage import (
    delete_document,
    document_storage_key,
    write_document,
)
from quotation.services.storage_control import (
    StorageRouter,
    register_uploaded_replica,
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
        set_request_audit_target(request, target_label=file_name)
        conflict_action = (
            str(request.data.get("conflict_action") or "").strip().lower()
        )
        if conflict_action not in {"", "reuse", "rename"}:
            return Response(
                {"detail": "conflict_action must be reuse or rename"},
                status=400,
            )

        quotation_id = request.data.get("quotation_id") or None
        quotation = None
        if quotation_id:
            quotation, denied = get_accessible_quotation(
                request.user, quotation_id, DocumentAction.UPLOAD
            )
            if denied:
                return denied
            set_request_audit_target(
                request,
                target_label=quotation.quote_no,
            )

        try:
            client, access_token, root_folder_token = (
                common._system_drive_context()
            )
            requested_folder = (
                request.data.get("folder_token") or request.data.get("folder")
            )
            folder_token = common._managed_folder_token(
                client=client,
                access_token=access_token,
                requested_token=requested_folder or root_folder_token,
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
                            "file_token": existing.get("token"),
                            "file_name": existing.get("name") or file_name,
                            "size_bytes": common._item_size_bytes(existing),
                            "url": existing.get("url"),
                        },
                        "suggested_file_name": (
                            common._suggest_unique_file_name(
                                file_name, existing_names
                            )
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
                    uploaded_meta = (
                        common._find_file_by_token_or_name_in_folder(
                            client=client,
                            access_token=access_token,
                            folder_token=folder_token,
                            file_token=uploaded_token,
                            file_name=file_name,
                        )
                    )
                    if uploaded_meta and uploaded_meta.get("url"):
                        data["url"] = uploaded_meta.get("url")
        except PermissionError:
            return Response({"detail": "Forbidden"}, status=403)
        except FeishuAPIError as exc:
            return common._feishu_error_response(exc, operation="upload")
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        file_token = str(data.get("file_token") or data.get("token") or "")
        if not file_token:
            return Response(
                {"detail": f"upload succeeded but file_token missing: {data}"},
                status=400,
            )

        doc_type = common._guess_doc_type(file_name, upload.content_type)
        feishu_url = data.get("url") or build_feishu_file_url(file_token)
        local_storage_key = None
        recorded_asset_id = None
        try:
            with transaction.atomic():
                if reused_existing:
                    matching_assets = filter_accessible_documents(
                        request.user,
                        DocumentAsset.objects.filter(
                            quotation_id=quotation_id,
                            doc_type=doc_type,
                            source="feishu_upload",
                            feishu_file_token=file_token,
                        ).select_related("quotation"),
                    )
                    existing_asset = matching_assets.order_by(
                        "-created_at"
                    ).first()
                    if existing_asset:
                        recorded_asset_id = existing_asset.id
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
                        recorded_asset_id = asset_id
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
                    recorded_asset_id = asset_id
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
            "document_id": recorded_asset_id,
            "file_name": file_name,
            "folder_token": folder_token,
            "file_token": file_token,
            "url": feishu_url,
            "size_bytes": len(content),
            "reused_existing": reused_existing,
            "direct_access_allowed": True,
        }
        if renamed_from:
            payload["renamed_from"] = renamed_from
        if (
            settings.QUOTATION_DOCUMENT_REPLICA_ENABLED
            and recorded_asset_id
        ):
            try:
                asset = DocumentAsset.objects.select_related(
                    "quotation"
                ).get(pk=recorded_asset_id)
                route = StorageRouter().resolve(document_type=doc_type)
                replica = register_uploaded_replica(
                    request=request,
                    asset=asset,
                    route=route,
                    remote_file_token=file_token,
                    remote_url=feishu_url,
                    folder_token=folder_token,
                )
                payload["replica_id"] = replica.id
                payload["storage_connection_id"] = replica.connection_id
            except (LookupError, ValueError):
                payload["replica_pending"] = True
        return Response(payload)
