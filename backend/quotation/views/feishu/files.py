from __future__ import annotations

from collections import deque
from hashlib import sha256
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from quotation.access import (
    DocumentAction,
    filter_accessible_documents,
    forbidden_response,
    get_accessible_document,
    get_accessible_quotation,
)
from quotation.audit import set_request_audit_target
from quotation.models import (
    DocumentAsset,
    DocumentParseStatus,
    DocumentType,
    FeishuFileSnapshot,
    FeishuSyncDifference,
    FeishuSyncDifferenceStatus,
    FeishuSyncDifferenceType,
    FeishuSyncState,
    FeishuSyncStatus,
    StorageConnection,
    SyncJob,
    SyncJobStatus,
    SyncJobType,
)
from quotation.permissions import user_display_email
from quotation.serializers import (
    build_feishu_file_url,
    trusted_feishu_file_url,
)
from quotation.services.document_parsing.excel_parser import (
    QuotationExcelParseError,
)
from quotation.services.document_parsing.pdf_parser import (
    QuotationPdfParseError,
)
from quotation.services.document_parsing.service import (
    QuotationDocumentParseError,
    parse_and_create_quotation,
    parser_version_for_asset,
)
from quotation.services.feishu_client import FeishuAPIError
from quotation.services.feishu_service import folder_token_for_item
from quotation.services.feishu_sync import (
    ACTIVE_SYNC_STATUSES,
    authorized_sync_targets,
    enqueue_feishu_sync,
    file_metadata,
    is_sync_admin,
    metadata_fingerprint,
    parse_dispatch_lock_key,
    sync_state_id,
)
from quotation.services.storage import (
    delete_document,
    document_storage_key,
    write_document,
)
from quotation.services.storage_control import (
    FeishuStorageProvider,
    RemoteDocumentReference,
    StorageRouter,
    preserve_remote_file_reference,
    remote_document_reference,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import common


def _drive_context_for_reference(
    reference: RemoteDocumentReference,
):
    """Return the Feishu client context for one remote document reference."""
    if reference.replica is not None:
        provider = FeishuStorageProvider(reference.replica.connection)
        return provider.client, provider.access_token()
    client, access_token, _ = common._system_drive_context()
    return client, access_token


def _latest_parse_result(asset: DocumentAsset):
    prefetched = getattr(asset, "_prefetched_objects_cache", {}).get(
        "parse_results"
    )
    if prefetched is not None:
        return max(
            prefetched,
            key=lambda item: (item.created_at, item.id),
            default=None,
        )
    return asset.parse_results.order_by("-created_at", "-id").first()


def _existing_asset_priority(asset: DocumentAsset):
    result = _latest_parse_result(asset)
    status = result.status if result else ""
    status_rank = {
        "not_quotation": 6,
        "confirmed": 5,
        "ready": 4,
        "review_required": 3,
        "running": 2,
        "failed": 1,
    }.get(status, 0)
    if asset.quotation_id:
        status_rank = max(status_rank, 5)
    return (status_rank, asset.created_at, asset.id)


class FeishuImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, file_token: str):
        quotation_id = request.query_params.get("quotation_id")
        if quotation_id:
            quotation, denied = get_accessible_quotation(
                request.user, quotation_id, DocumentAction.IMPORT
            )
            if denied:
                return denied
            set_request_audit_target(
                request,
                target_label=quotation.quote_no,
            )

        try:
            (
                client,
                access_token,
                root_folder_token,
                storage_connection,
                _storage_mount,
            ) = common._system_drive_context_details()
            requested_folder = request.data.get(
                "folder_token"
            ) or request.query_params.get("folder_token")
            folder_token = common._managed_folder_token(
                client=client,
                access_token=access_token,
                requested_token=requested_folder or root_folder_token,
            )
            file_item = common._find_file_by_token_or_name_in_folder(
                client=client,
                access_token=access_token,
                folder_token=folder_token,
                file_token=file_token,
                file_name=request.query_params.get("file_name") or "",
            )
            if not file_item:
                return Response(
                    {"detail": "file is not in the configured Feishu folder"},
                    status=404,
                )
            if str(file_item.get("type") or "").lower() == "shortcut":
                return Response(
                    {"detail": "Feishu shortcuts cannot be imported"},
                    status=400,
                )
            existing_asset = DocumentAsset.objects.filter(
                source="feishu",
                feishu_file_token=file_token,
            ).first()
            if existing_asset is not None:
                if (
                    quotation_id
                    and existing_asset.quotation_id
                    and existing_asset.quotation_id != quotation_id
                ):
                    return Response(
                        {"detail": "Feishu file was already imported"},
                        status=409,
                    )
                if quotation_id and not existing_asset.quotation_id:
                    existing_asset.quotation_id = quotation_id
                    existing_asset.save(update_fields=["quotation"])
                return Response(
                    {
                        "file_name": existing_asset.file_name,
                        "mime_type": existing_asset.mime_type,
                        "size_bytes": existing_asset.size_bytes,
                        "storage_key": existing_asset.storage_key,
                        "document_id": existing_asset.id,
                        "doc_type": existing_asset.doc_type,
                        "url": existing_asset.feishu_url,
                        "direct_access_allowed": True,
                        "reused": True,
                    }
                )
            content, mime_type, resolved_name = client.download_drive_item(
                access_token,
                file_token=file_token,
                file_type=request.query_params.get("file_type"),
                file_name=request.query_params.get("file_name")
                or file_item.get("name"),
            )
        except PermissionError:
            return forbidden_response()
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
                    "发版后重启后端服务，再导入在线表格。"
                )
            if detail != str(exc):
                return Response({"detail": detail}, status=502)
            return common._feishu_error_response(exc, operation="import")

        if not content:
            return Response({"detail": "Downloaded empty file"}, status=400)
        if len(content) > settings.QUOTATION_MAX_UPLOAD_BYTES:
            return Response(
                {"detail": "Downloaded file exceeds quotation size limit"},
                status=413,
            )

        safe_name = (
            resolved_name
            or request.query_params.get("file_name")
            or f"{file_token}.bin"
        )
        asset_id = str(uuid4())
        storage_key = document_storage_key(asset_id, quotation_id or None)
        write_document(content, storage_key)
        doc_type = common._guess_doc_type(safe_name, mime_type)
        feishu_url = file_item.get("url") or build_feishu_file_url(file_token)
        try:
            with transaction.atomic():
                preserve_remote_file_reference(
                    file_token,
                    connection=storage_connection,
                    owned=False,
                )
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
                "file_name": safe_name,
                "mime_type": mime_type,
                "size_bytes": len(content),
                "storage_key": storage_key,
                "document_id": asset.id,
                "doc_type": doc_type,
                "url": feishu_url,
                "direct_access_allowed": True,
            }
        )


class FeishuFolderSyncView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if bool(request.data.get("async")):
            job, reused = enqueue_feishu_sync(
                actor=request.user,
                trigger="manual",
                force=True,
                request_id=getattr(request, "audit_request_id", ""),
                trace_id=getattr(request, "audit_trace_id", ""),
            )
            if job is None:
                return Response(
                    {"detail": "no authorized Feishu folders"},
                    status=403,
                )
            return Response(
                {
                    "created_count": 0,
                    "skipped_count": 0,
                    "parsed_count": 0,
                    "created_quotation_count": 0,
                    "updated_quotation_count": 0,
                    "queued_parse_count": 0,
                    "errors": [],
                    "folders": [],
                    "file_locations": [],
                    "created_document_ids": [],
                    "parsed_document_ids": [],
                    "created_quotation_ids": [],
                    "updated_quotation_ids": [],
                    "sync_job_id": job.id,
                    "sync_status": job.status,
                    "storage_connection_id": job.storage_connection_id,
                    "reused": reused,
                },
                status=202,
            )

        targets = [
            vars(target).copy()
            for target in authorized_sync_targets(request.user)
        ]
        if not targets:
            return Response(
                {"detail": "no authorized Feishu folders"},
                status=403,
            )

        lock_key = "quotation:feishu:archive-folder-sync"
        if not cache.add(lock_key, True, timeout=900):
            return Response(
                {"detail": "archive folder sync already running"},
                status=409,
            )
        connection = None
        if settings.QUOTATION_STORAGE_ROUTER_ENABLED:
            try:
                connection = StorageRouter().resolve().connection
            except LookupError:
                pass
        job = SyncJob.objects.create(
            job_type=SyncJobType.PULL,
            status=SyncJobStatus.PENDING,
            actor=request.user,
            storage_connection=connection,
            request_id=getattr(request, "audit_request_id", ""),
            trace_id=getattr(request, "audit_trace_id", ""),
            payload_json={
                "action": "feishu_archive_folder_sync",
                "audit_source": request.META.get(
                    "HTTP_X_QUOTATION_AUDIT_SOURCE",
                    "user",
                ),
                "operator_email": user_display_email(request.user),
                "targets": targets,
            },
        )
        job.status = SyncJobStatus.RUNNING
        job.stage = "discovering"
        job.save(update_fields=["status", "stage", "updated_at"])
        try:
            response = self._sync(
                request,
                sync_job=job,
                targets=targets,
            )
            succeeded = response.status_code < 400
            job.status = (
                SyncJobStatus.SUCCESS if succeeded else SyncJobStatus.FAILED
            )
            if succeeded:
                job.result_json = {
                    "created_count": response.data.get("created_count", 0),
                    "skipped_count": response.data.get("skipped_count", 0),
                    "parsed_count": response.data.get("parsed_count", 0),
                    "created_quotation_count": response.data.get(
                        "created_quotation_count", 0
                    ),
                    "updated_quotation_count": response.data.get(
                        "updated_quotation_count", 0
                    ),
                    "error_count": len(response.data.get("errors") or []),
                }
            else:
                job.error_code = f"http_{response.status_code}"
                job.error_message = str(
                    response.data.get("detail") or "folder sync failed"
                )[:500]
            job.finished_at = timezone.now()
            job.save(
                update_fields=[
                    "status",
                    "result_json",
                    "error_message",
                    "error_code",
                    "finished_at",
                    "updated_at",
                ]
            )
            if isinstance(getattr(response, "data", None), dict):
                response.data["sync_job_id"] = job.id
                response.data["storage_connection_id"] = (
                    job.storage_connection_id
                )
            return response
        except Exception as exc:
            job.status = SyncJobStatus.FAILED
            job.error_code = "folder_sync_failed"
            job.error_message = f"{type(exc).__name__}: folder sync failed"
            job.finished_at = timezone.now()
            job.save(
                update_fields=[
                    "status",
                    "error_code",
                    "error_message",
                    "finished_at",
                    "updated_at",
                ]
            )
            raise
        finally:
            cache.delete(lock_key)

    def _sync(
        self,
        request,
        *,
        enqueue_parsing: bool = False,
        sync_job: SyncJob | None = None,
        targets: list[dict] | None = None,
    ):
        target_list = [item for item in (targets or []) if item]
        if len(target_list) > 1:
            combined = {
                "created_count": 0,
                "skipped_count": 0,
                "errors": [],
                "folders": [],
                "file_locations": [],
                "created_document_ids": [],
                "parsed_count": 0,
                "created_quotation_count": 0,
                "updated_quotation_count": 0,
                "queued_parse_count": 0,
                "parsed_document_ids": [],
                "created_quotation_ids": [],
                "updated_quotation_ids": [],
            }
            count_fields = {
                "created_count",
                "skipped_count",
                "parsed_count",
                "created_quotation_count",
                "updated_quotation_count",
                "queued_parse_count",
            }
            list_fields = set(combined) - count_fields
            successful_targets = 0
            failure_status = None
            for target in target_list:
                response = self._sync(
                    request,
                    enqueue_parsing=enqueue_parsing,
                    sync_job=sync_job,
                    targets=[target],
                )
                if response.status_code >= 400:
                    failure_status = failure_status or response.status_code
                    combined["errors"].append(
                        {
                            "folder": target.get("folder_name") or "",
                            "detail": response.data.get("detail")
                            or "folder sync failed",
                        }
                    )
                    continue
                successful_targets += 1
                for field in count_fields:
                    combined[field] += int(response.data.get(field) or 0)
                for field in list_fields:
                    combined[field].extend(response.data.get(field) or [])
            return Response(
                combined,
                status=(
                    failure_status
                    if not successful_targets and failure_status
                    else 200
                ),
            )

        target = target_list[0] if target_list else {}
        try:
            connection_id = target.get("connection_id")
            if connection_id:
                storage_connection = StorageConnection.objects.get(
                    pk=connection_id
                )
                provider = FeishuStorageProvider(storage_connection)
                client = provider.client
                access_token = provider.access_token()
                root_folder_token = str(target.get("folder_token") or "")
            else:
                (
                    client,
                    access_token,
                    configured_root,
                    storage_connection,
                    _storage_mount,
                ) = common._system_drive_context_details()
                root_folder_token = str(
                    target.get("folder_token") or configured_root
                )
        except FeishuAPIError as exc:
            return common._feishu_error_response(exc, operation="folder sync")

        requested_by = (
            request.user
            if getattr(request.user, "is_authenticated", False)
            else None
        )
        state = (
            FeishuSyncState.objects.filter(
                storage_connection=storage_connection,
                root_folder_token=root_folder_token,
            )
            .order_by("id")
            .first()
        )
        if state is None:
            state, _created = FeishuSyncState.objects.get_or_create(
                id=sync_state_id(
                    getattr(storage_connection, "id", None),
                    root_folder_token,
                ),
                defaults={
                    "storage_connection": storage_connection,
                    "requested_by": requested_by,
                    "root_folder_token": root_folder_token,
                },
            )
        elif (
            requested_by is not None
            and state.requested_by_id != requested_by.id
        ):
            state.requested_by = requested_by
        state.status = FeishuSyncStatus.SYNCING
        state.latest_feishu_check_at = timezone.now()
        state.error_code = ""
        state.error_message = ""
        state_update_fields = [
            "status",
            "latest_feishu_check_at",
            "error_code",
            "error_message",
            "updated_at",
        ]
        if requested_by is not None:
            state_update_fields.append("requested_by")
        state.save(update_fields=state_update_fields)

        root_folder_name = str(
            target.get("folder_name") or common.ARCHIVE_FOLDER_LABEL
        )
        if hasattr(client, "get_folder_meta"):
            try:
                root_meta = client.get_folder_meta(
                    access_token, root_folder_token
                )
                root_folder_name = str(
                    root_meta.get("name") or root_folder_name
                ).strip()
            except FeishuAPIError:
                pass
        if root_folder_name != state.root_folder_name:
            state.root_folder_name = root_folder_name
            state.save(update_fields=["root_folder_name", "updated_at"])

        created = 0
        skipped = 0
        parsed = 0
        created_quotations = 0
        updated_quotations = 0
        queued_parses = 0
        errors: list[dict] = []
        file_locations: list[dict[str, str]] = []
        created_document_ids: list[str] = []
        parsed_document_ids: list[str] = []
        created_quotation_ids: list[str] = []
        updated_quotation_ids: list[str] = []
        email = user_display_email(request.user) if requested_by else ""
        seen_tokens: set[str] = set()
        scan_complete = True
        pending_folders = deque([root_folder_token])
        visited_folders: set[str] = set()
        folders = {
            root_folder_token: {
                "token": root_folder_token,
                "name": root_folder_name,
                "parent_token": None,
            }
        }
        folder_paths = {
            root_folder_token: [
                {"token": root_folder_token, "name": root_folder_name}
            ]
        }

        def auto_parse_asset(asset: DocumentAsset) -> None:
            nonlocal parsed, created_quotations, queued_parses
            nonlocal updated_quotations
            if asset.doc_type not in {DocumentType.EXCEL, DocumentType.PDF}:
                return
            if asset.file_name.lower().startswith("~$"):
                return
            if enqueue_parsing:
                latest = _latest_parse_result(asset)
                if (
                    latest is not None
                    and latest.parser_version
                    == parser_version_for_asset(asset)
                    and (
                        not asset.content_hash
                        or latest.content_hash == asset.content_hash
                    )
                    and (
                        latest.status == DocumentParseStatus.NOT_QUOTATION
                        or (
                            asset.quotation_id
                            and latest.status == DocumentParseStatus.CONFIRMED
                        )
                    )
                ):
                    if latest.status == DocumentParseStatus.CONFIRMED:
                        parsed += 1
                        parsed_document_ids.append(asset.id)
                    return
                from quotation.tasks import parse_document_task

                queue = f"quotation_{asset.doc_type}"
                dispatch_key = parse_dispatch_lock_key(
                    asset_id=asset.id,
                    content_hash=asset.content_hash or "",
                    parser_version=parser_version_for_asset(asset),
                )
                if not cache.add(dispatch_key, True, timeout=600):
                    return
                try:
                    parse_document_task.apply_async(
                        args=[asset.id, getattr(request.user, "id", None)],
                        queue=queue,
                    )
                except Exception:
                    cache.delete(dispatch_key)
                    raise
                queued_parses += 1
                return
            try:
                result, reused = parse_and_create_quotation(
                    asset,
                    actor=request.user,
                )
            except IntegrityError:
                errors.append(
                    {
                        "file": asset.file_name,
                        "detail": "quote_no already exists",
                    }
                )
                return
            except (
                QuotationDocumentParseError,
                QuotationExcelParseError,
                QuotationPdfParseError,
                ValueError,
            ) as exc:
                errors.append(
                    {
                        "file": asset.file_name,
                        "detail": str(exc)[:500] or "parse failed",
                    }
                )
                return
            if result.status == DocumentParseStatus.NOT_QUOTATION:
                return
            if not result.quotation_id:
                errors.append(
                    {
                        "file": asset.file_name,
                        "detail": result.error_message
                        or "automatic parse validation failed",
                    }
                )
                return
            parsed += 1
            parsed_document_ids.append(asset.id)
            if not reused:
                created_quotations += 1
                created_quotation_ids.append(result.quotation_id)
            elif getattr(result, "_quotation_version_created", False):
                updated_quotations += 1
                updated_quotation_ids.append(result.quotation_id)

        def snapshot_metadata(snapshot: FeishuFileSnapshot) -> dict:
            return {
                "file_name": snapshot.file_name,
                "file_type": snapshot.file_type,
                "folder_token": snapshot.folder_token,
                "folder_path": snapshot.folder_path,
                "size_bytes": snapshot.size_bytes,
                "modified_time": snapshot.modified_time,
            }

        def record_difference(
            *,
            snapshot: FeishuFileSnapshot,
            difference_type: str,
            previous: dict,
            current: dict,
            status: str = FeishuSyncDifferenceStatus.APPLIED,
            error_message: str = "",
        ) -> None:
            lookup = {
                "sync_job": sync_job,
                "file_token": snapshot.remote_file_token,
                "difference_type": difference_type,
            }
            defaults = {
                "state": state,
                "snapshot": snapshot,
                "status": status,
                "previous_metadata": previous,
                "current_metadata": current,
                "error_message": error_message[:500],
                "resolved_at": (
                    timezone.now()
                    if status == FeishuSyncDifferenceStatus.APPLIED
                    else None
                ),
            }
            if sync_job is None:
                FeishuSyncDifference.objects.create(**lookup, **defaults)
                return
            FeishuSyncDifference.objects.update_or_create(
                **lookup,
                defaults=defaults,
            )

        def record_state_error(exc: FeishuAPIError) -> None:
            detail = str(exc).lower()
            if (
                exc.code in {99991663, 99991668, 99991672, 99991679}
                or "permission" in detail
                or "forbidden" in detail
            ):
                state.status = FeishuSyncStatus.PERMISSION
                state.error_code = "permission"
            elif (
                "not found" in detail
                or "does not exist" in detail
                or "missing" in detail
            ):
                state.status = FeishuSyncStatus.MISSING
                state.error_code = "missing"
            else:
                state.status = FeishuSyncStatus.FAILED
                state.error_code = "feishu_api_error"
            state.error_message = str(exc)[:500]
            state.save(
                update_fields=[
                    "status",
                    "error_code",
                    "error_message",
                    "updated_at",
                ]
            )

        while pending_folders:
            current_folder = pending_folders.popleft()
            if current_folder in visited_folders:
                continue
            visited_folders.add(current_folder)
            page_token = None

            visited_page_tokens: set[str] = set()
            while True:
                try:
                    data = client.list_folder_files(
                        access_token,
                        current_folder,
                        page_size=200,
                        page_token=page_token,
                    )
                except FeishuAPIError as exc:
                    record_state_error(exc)
                    return common._feishu_error_response(
                        exc, operation="folder sync"
                    )

                for item in data.get("files") or []:
                    item_type = str(item.get("type") or "").lower()
                    if item_type in {"folder", "drive#folder"}:
                        child_token = str(
                            folder_token_for_item(item)
                            or item.get("file_token")
                            or item.get("id")
                            or ""
                        ).strip()
                        if child_token and child_token not in visited_folders:
                            pending_folders.append(child_token)
                        if child_token:
                            child_name = str(
                                item.get("name") or "Folder"
                            ).strip()
                            folders.setdefault(
                                child_token,
                                {
                                    "token": child_token,
                                    "name": child_name,
                                    "parent_token": current_folder,
                                },
                            )
                            folder_paths.setdefault(
                                child_token,
                                [
                                    *folder_paths.get(current_folder, []),
                                    {
                                        "token": child_token,
                                        "name": child_name,
                                    },
                                ],
                            )
                        skipped += 1
                        continue
                    file_token = str(item.get("token") or "").strip()
                    file_name = str(item.get("name") or file_token).strip()
                    if not file_token or not file_name.lower().endswith(
                        tuple(settings.QUOTATION_ALLOWED_EXTENSIONS)
                    ):
                        skipped += 1
                        continue
                    current_path = folder_paths.get(current_folder, [])
                    remote_size = int(item.get("size") or 0)
                    seen_tokens.add(file_token)
                    if remote_size > settings.QUOTATION_MAX_UPLOAD_BYTES:
                        errors.append(
                            {
                                "file": file_name,
                                "detail": "file exceeds quotation size limit",
                            }
                        )
                        continue
                    metadata = file_metadata(
                        item,
                        folder_token=current_folder,
                        folder_path=current_path,
                    )
                    fingerprint = metadata_fingerprint(metadata)
                    snapshot = (
                        FeishuFileSnapshot.objects.select_related("asset")
                        .filter(remote_file_token=file_token)
                        .first()
                    )
                    previous = snapshot_metadata(snapshot) if snapshot else {}
                    moved = bool(
                        snapshot and snapshot.folder_token != current_folder
                    )
                    renamed = bool(
                        snapshot and snapshot.file_name != file_name
                    )
                    modified = bool(
                        snapshot
                        and (
                            (
                                remote_size > 0
                                and snapshot.size_bytes != remote_size
                            )
                            or (
                                metadata["modified_time"]
                                and snapshot.modified_time
                                != metadata["modified_time"]
                            )
                        )
                    )
                    remote_assets = DocumentAsset.objects.filter(
                        source="feishu",
                        feishu_file_token=file_token,
                    )
                    existing_assets = list(
                        remote_assets.prefetch_related("parse_results")
                    )
                    existing_asset = max(
                        existing_assets,
                        key=_existing_asset_priority,
                        default=None,
                    )
                    if existing_asset:
                        update_fields = [
                            "feishu_folder_token",
                            "feishu_folder_path",
                        ]
                        existing_asset.feishu_folder_token = current_folder
                        existing_asset.feishu_folder_path = current_path
                        if renamed:
                            existing_asset.file_name = file_name
                            update_fields.append("file_name")
                        if metadata["url"]:
                            existing_asset.feishu_url = metadata["url"]
                            update_fields.append("feishu_url")
                        if modified:
                            try:
                                content, mime_type, resolved_name = (
                                    client.download_drive_item(
                                        access_token,
                                        file_token=file_token,
                                        file_type=item.get("type"),
                                        file_name=file_name,
                                    )
                                )
                            except FeishuAPIError as exc:
                                errors.append(
                                    {
                                        "file": file_name,
                                        "detail": "Feishu download failed",
                                    }
                                )
                                if snapshot is not None:
                                    record_difference(
                                        snapshot=snapshot,
                                        difference_type=(
                                            FeishuSyncDifferenceType.MODIFIED
                                        ),
                                        previous=previous,
                                        current=metadata,
                                        status=(
                                            FeishuSyncDifferenceStatus.FAILED
                                        ),
                                        error_message=str(exc),
                                    )
                                continue
                            if not content:
                                errors.append(
                                    {
                                        "file": file_name,
                                        "detail": "empty file",
                                    }
                                )
                                continue
                            if (
                                len(content)
                                > settings.QUOTATION_MAX_UPLOAD_BYTES
                            ):
                                errors.append(
                                    {
                                        "file": file_name,
                                        "detail": (
                                            "file exceeds quotation size limit"
                                        ),
                                    }
                                )
                                continue
                            write_document(content, existing_asset.storage_key)
                            existing_asset.file_name = (
                                resolved_name or file_name
                            )
                            existing_asset.mime_type = (
                                mime_type or "application/octet-stream"
                            )
                            existing_asset.size_bytes = len(content)
                            existing_asset.content_hash = sha256(
                                content
                            ).hexdigest()
                            update_fields.extend(
                                [
                                    "file_name",
                                    "mime_type",
                                    "size_bytes",
                                    "content_hash",
                                ]
                            )
                            metadata["file_name"] = existing_asset.file_name
                            metadata["size_bytes"] = len(content)
                            fingerprint = metadata_fingerprint(metadata)
                        existing_asset.save(
                            update_fields=list(dict.fromkeys(update_fields))
                        )
                        if snapshot is None:
                            snapshot = FeishuFileSnapshot.objects.create(
                                state=state,
                                asset=existing_asset,
                                remote_file_token=file_token,
                                folder_token=current_folder,
                                folder_path=current_path,
                                file_name=metadata["file_name"],
                                file_type=metadata["file_type"],
                                size_bytes=metadata["size_bytes"],
                                modified_time=metadata["modified_time"],
                                metadata_fingerprint=fingerprint,
                                last_seen_at=timezone.now(),
                            )
                        else:
                            if moved:
                                record_difference(
                                    snapshot=snapshot,
                                    difference_type=(
                                        FeishuSyncDifferenceType.MOVED
                                    ),
                                    previous=previous,
                                    current=metadata,
                                )
                            if renamed:
                                record_difference(
                                    snapshot=snapshot,
                                    difference_type=(
                                        FeishuSyncDifferenceType.RENAMED
                                    ),
                                    previous=previous,
                                    current=metadata,
                                )
                            if modified:
                                record_difference(
                                    snapshot=snapshot,
                                    difference_type=(
                                        FeishuSyncDifferenceType.MODIFIED
                                    ),
                                    previous=previous,
                                    current=metadata,
                                )
                            snapshot.state = state
                            snapshot.asset = existing_asset
                            snapshot.folder_token = current_folder
                            snapshot.folder_path = current_path
                            snapshot.file_name = metadata["file_name"]
                            snapshot.file_type = metadata["file_type"]
                            snapshot.size_bytes = metadata["size_bytes"]
                            snapshot.modified_time = metadata["modified_time"]
                            snapshot.metadata_fingerprint = fingerprint
                            snapshot.deleted_in_feishu = False
                            snapshot.deleted_at = None
                            snapshot.last_seen_at = timezone.now()
                            snapshot.save()
                        auto_parse_asset(existing_asset)
                        file_locations.append(
                            {
                                "document_id": existing_asset.id,
                                "folder_token": current_folder,
                            }
                        )
                        skipped += 1
                        continue

                    try:
                        content, mime_type, resolved_name = (
                            client.download_drive_item(
                                access_token,
                                file_token=file_token,
                                file_type=item.get("type"),
                                file_name=file_name,
                            )
                        )
                    except FeishuAPIError:
                        errors.append(
                            {
                                "file": file_name,
                                "detail": "Feishu download failed",
                            }
                        )
                        continue
                    if not content:
                        errors.append(
                            {"file": file_name, "detail": "empty file"}
                        )
                        continue
                    if len(content) > settings.QUOTATION_MAX_UPLOAD_BYTES:
                        errors.append(
                            {
                                "file": file_name,
                                "detail": "file exceeds quotation size limit",
                            }
                        )
                        continue

                    safe_name = resolved_name or file_name
                    asset_id = str(uuid4())
                    storage_key = document_storage_key(asset_id, None)
                    write_document(content, storage_key)
                    created_asset = True
                    try:
                        with transaction.atomic():
                            preserve_remote_file_reference(
                                file_token,
                                connection=storage_connection,
                                owned=False,
                            )
                            asset = DocumentAsset.objects.create(
                                id=asset_id,
                                doc_type=common._guess_doc_type(
                                    safe_name, mime_type
                                ),
                                file_name=safe_name,
                                mime_type=(
                                    mime_type or "application/octet-stream"
                                ),
                                storage_key=storage_key,
                                size_bytes=len(content),
                                content_hash=sha256(content).hexdigest(),
                                source="feishu",
                                feishu_file_token=file_token,
                                feishu_url=item.get("url")
                                or build_feishu_file_url(file_token),
                                feishu_folder_token=current_folder,
                                feishu_folder_path=current_path,
                                created_by_email=email,
                            )
                    except IntegrityError:
                        delete_document(storage_key)
                        asset = (
                            DocumentAsset.objects.filter(
                                source="feishu",
                                feishu_file_token=file_token,
                            )
                            .prefetch_related("parse_results")
                            .first()
                        )
                        if asset is None:
                            raise
                        created_asset = False
                    except Exception:
                        delete_document(storage_key)
                        raise
                    file_locations.append(
                        {
                            "document_id": asset.id,
                            "folder_token": current_folder,
                        }
                    )
                    if created_asset:
                        created_document_ids.append(asset.id)
                        created += 1
                    else:
                        skipped += 1
                    metadata["file_name"] = asset.file_name
                    metadata["size_bytes"] = asset.size_bytes
                    fingerprint = metadata_fingerprint(metadata)
                    snapshot, snapshot_created = (
                        FeishuFileSnapshot.objects.update_or_create(
                            remote_file_token=file_token,
                            defaults={
                                "state": state,
                                "asset": asset,
                                "folder_token": current_folder,
                                "folder_path": current_path,
                                "file_name": asset.file_name,
                                "file_type": metadata["file_type"],
                                "size_bytes": asset.size_bytes,
                                "modified_time": metadata["modified_time"],
                                "metadata_fingerprint": fingerprint,
                                "deleted_in_feishu": False,
                                "deleted_at": None,
                                "last_seen_at": timezone.now(),
                            },
                        )
                    )
                    if created_asset and snapshot_created:
                        record_difference(
                            snapshot=snapshot,
                            difference_type=FeishuSyncDifferenceType.ADDED,
                            previous={},
                            current=metadata,
                        )
                    auto_parse_asset(asset)

                if not data.get("has_more"):
                    break
                page_token = data.get("next_page_token")
                if not page_token or page_token in visited_page_tokens:
                    scan_complete = False
                    errors.append(
                        {
                            "folder": folders.get(current_folder, {}).get(
                                "name", ""
                            ),
                            "detail": "incomplete Feishu pagination",
                        }
                    )
                    break
                visited_page_tokens.add(page_token)

        if scan_complete:
            missing_snapshots = state.file_snapshots.filter(
                deleted_in_feishu=False,
            )
            if seen_tokens:
                missing_snapshots = missing_snapshots.exclude(
                    remote_file_token__in=seen_tokens
                )
            for snapshot in missing_snapshots.select_related("asset"):
                previous = snapshot_metadata(snapshot)
                snapshot.deleted_in_feishu = True
                snapshot.deleted_at = timezone.now()
                snapshot.save(
                    update_fields=[
                        "deleted_in_feishu",
                        "deleted_at",
                        "updated_at",
                    ]
                )
                record_difference(
                    snapshot=snapshot,
                    difference_type=FeishuSyncDifferenceType.DELETED,
                    previous=previous,
                    current={},
                    status=(FeishuSyncDifferenceStatus.PENDING_CONFIRMATION),
                )

        unresolved_statuses = {
            FeishuSyncDifferenceStatus.DETECTED,
            FeishuSyncDifferenceStatus.PENDING_CONFIRMATION,
            FeishuSyncDifferenceStatus.FAILED,
        }
        state.difference_count = state.differences.filter(
            status__in=unresolved_statuses
        ).count()
        state.last_local_sync_at = timezone.now()
        if errors:
            state.status = FeishuSyncStatus.FAILED
            state.error_code = "partial_failure"
            state.error_message = f"{len(errors)} file operations failed"
        elif state.difference_count:
            state.status = FeishuSyncStatus.HAS_DIFF
        else:
            state.status = FeishuSyncStatus.SYNCED
        state.save(
            update_fields=[
                "status",
                "last_local_sync_at",
                "difference_count",
                "error_code",
                "error_message",
                "updated_at",
            ]
        )

        return Response(
            {
                "created_count": created,
                "skipped_count": skipped,
                "errors": errors[:20],
                "folders": list(folders.values()),
                "file_locations": file_locations,
                "created_document_ids": created_document_ids,
                "parsed_count": parsed,
                "created_quotation_count": created_quotations,
                "updated_quotation_count": updated_quotations,
                "queued_parse_count": queued_parses,
                "parsed_document_ids": parsed_document_ids,
                "created_quotation_ids": created_quotation_ids,
                "updated_quotation_ids": updated_quotation_ids,
                "sync_state": state.status,
                "difference_count": state.difference_count,
            }
        )


class FeishuLoginSyncView(APIView):
    """Idempotently trigger synchronization after authentication."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        job, reused = enqueue_feishu_sync(
            actor=request.user,
            trigger="login",
            request_id=getattr(request, "audit_request_id", ""),
            trace_id=getattr(request, "audit_trace_id", ""),
        )
        if job is None:
            return Response(
                {
                    "sync_job_id": None,
                    "sync_status": "unavailable",
                    "reused": False,
                }
            )
        return Response(
            {
                "sync_job_id": job.id,
                "sync_status": job.status,
                "reused": reused,
            },
            status=202,
        )


class FeishuSyncStatusView(APIView):
    """Return synchronization state without crossing access boundaries."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        differences = FeishuSyncDifference.objects.select_related(
            "state",
            "snapshot",
            "snapshot__asset",
        )
        states = FeishuSyncState.objects.all()
        sync_admin = is_sync_admin(request.user)
        if not sync_admin:
            visible_asset_ids = filter_accessible_documents(
                request.user,
                DocumentAsset.objects.all(),
            ).values("id")
            differences = differences.filter(
                snapshot__asset_id__in=visible_asset_ids,
            )
            visible_state_ids = differences.values("state_id")
            authorized_scope = Q(pk__in=[])
            for target in authorized_sync_targets(request.user):
                target_scope = Q(
                    root_folder_token=target.folder_token,
                )
                if target.connection_id:
                    target_scope &= Q(
                        storage_connection_id=target.connection_id,
                    )
                else:
                    target_scope &= Q(storage_connection__isnull=True)
                authorized_scope |= target_scope
            states = states.filter(
                Q(requested_by=request.user)
                | Q(id__in=visible_state_ids)
                | Q(file_snapshots__asset_id__in=visible_asset_ids)
                | authorized_scope
            ).distinct()
        state_rows = list(states.order_by("root_folder_name", "id"))
        difference_rows = list(differences.order_by("-created_at")[:100])
        unresolved_statuses = {
            FeishuSyncDifferenceStatus.DETECTED,
            FeishuSyncDifferenceStatus.PENDING_CONFIRMATION,
            FeishuSyncDifferenceStatus.FAILED,
        }
        if sync_admin:
            visible_difference_counts = {
                state.id: state.difference_count for state in state_rows
            }
        else:
            visible_difference_counts = {
                row["state_id"]: row["total"]
                for row in differences.filter(
                    status__in=unresolved_statuses,
                )
                .values("state_id")
                .annotate(total=Count("id"))
            }

        def state_difference_count(state: FeishuSyncState) -> int:
            return visible_difference_counts.get(state.id, 0)

        def state_display_status(state: FeishuSyncState) -> str:
            if (
                not sync_admin
                and state.status == FeishuSyncStatus.HAS_DIFF
                and state_difference_count(state) == 0
            ):
                return FeishuSyncStatus.SYNCED
            return state.status

        priority = {
            FeishuSyncStatus.PERMISSION: 6,
            FeishuSyncStatus.MISSING: 5,
            FeishuSyncStatus.FAILED: 4,
            FeishuSyncStatus.HAS_DIFF: 3,
            FeishuSyncStatus.SYNCING: 2,
            FeishuSyncStatus.SYNCED: 1,
        }
        overall_status = max(
            (state_display_status(state) for state in state_rows),
            key=lambda status: priority.get(status, 0),
            default=FeishuSyncStatus.SYNCED,
        )
        if SyncJob.objects.filter(
            actor=request.user,
            job_type=SyncJobType.PULL,
            status__in=ACTIVE_SYNC_STATUSES,
        ).exists():
            overall_status = FeishuSyncStatus.SYNCING

        def latest_time(field: str):
            values = [
                getattr(state, field)
                for state in state_rows
                if getattr(state, field) is not None
            ]
            return max(values) if values else None

        def safe_difference_metadata(metadata: dict) -> dict:
            allowed_fields = {
                "file_name",
                "file_type",
                "size_bytes",
                "modified_time",
            }
            return {
                key: value
                for key, value in metadata.items()
                if key in allowed_fields
            }

        def safe_state_error_message(state: FeishuSyncState) -> str:
            if not state.error_message:
                return ""
            messages = {
                "permission": "Feishu folder permission denied",
                "missing": "Feishu folder not found",
                "partial_failure": "Some Feishu files failed to synchronize",
            }
            return messages.get(
                state.error_code,
                "Feishu folder synchronization failed",
            )

        return Response(
            {
                "status": overall_status,
                "last_local_sync_at": latest_time("last_local_sync_at"),
                "latest_feishu_check_at": latest_time(
                    "latest_feishu_check_at"
                ),
                "difference_count": sum(
                    state_difference_count(state) for state in state_rows
                ),
                "states": [
                    {
                        "id": state.id,
                        "folder_name": state.root_folder_name,
                        "status": state_display_status(state),
                        "last_local_sync_at": state.last_local_sync_at,
                        "latest_feishu_check_at": (
                            state.latest_feishu_check_at
                        ),
                        "difference_count": state_difference_count(state),
                        "error_code": state.error_code,
                        "error_message": safe_state_error_message(state),
                    }
                    for state in state_rows
                ],
                "differences": [
                    {
                        "id": difference.id,
                        "type": difference.difference_type,
                        "status": difference.status,
                        "file_name": str(
                            difference.current_metadata.get("file_name")
                            or difference.previous_metadata.get("file_name")
                            or ""
                        ),
                        "folder_name": difference.state.root_folder_name,
                        "previous": safe_difference_metadata(
                            difference.previous_metadata
                        ),
                        "current": safe_difference_metadata(
                            difference.current_metadata
                        ),
                        "error_message": (
                            "Feishu file synchronization failed"
                            if difference.error_message
                            else ""
                        ),
                        "detected_at": difference.created_at,
                    }
                    for difference in difference_rows
                ],
            }
        )


class FeishuSyncDifferenceResolveView(APIView):
    """Resolve a Feishu deletion after administrator confirmation."""

    permission_classes = [IsAuthenticated]

    def post(self, request, difference_id: str):
        if not is_sync_admin(request.user):
            return forbidden_response()
        action = str(request.data.get("action") or "").strip().lower()
        if action not in {"archive", "delete"}:
            return Response({"detail": "invalid action"}, status=400)
        with transaction.atomic():
            difference = (
                FeishuSyncDifference.objects.select_for_update()
                .filter(pk=difference_id)
                .first()
            )
            if difference is None:
                return Response(
                    {"detail": "sync difference not found"},
                    status=404,
                )
            if (
                difference.difference_type != FeishuSyncDifferenceType.DELETED
                or difference.status
                != FeishuSyncDifferenceStatus.PENDING_CONFIRMATION
            ):
                return Response(
                    {"detail": "difference is not awaiting confirmation"},
                    status=409,
                )
            asset = (
                difference.snapshot.asset
                if difference.snapshot is not None
                else None
            )
            if action == "delete" and asset is not None:
                asset.delete()
            difference.status = FeishuSyncDifferenceStatus.ARCHIVED
            difference.resolved_at = timezone.now()
            difference.save(
                update_fields=["status", "resolved_at", "updated_at"]
            )
            state = difference.state
            state.difference_count = state.differences.filter(
                status__in={
                    FeishuSyncDifferenceStatus.DETECTED,
                    FeishuSyncDifferenceStatus.PENDING_CONFIRMATION,
                    FeishuSyncDifferenceStatus.FAILED,
                }
            ).count()
            state.status = (
                FeishuSyncStatus.HAS_DIFF
                if state.difference_count
                else FeishuSyncStatus.SYNCED
            )
            state.save(
                update_fields=[
                    "status",
                    "difference_count",
                    "updated_at",
                ]
            )
        return Response(
            {
                "id": difference.id,
                "status": difference.status,
                "action": action,
            }
        )


class FeishuSyncJobDetailView(APIView):
    """Return one caller-owned synchronization job."""

    permission_classes = [IsAuthenticated]

    def get(self, request, job_id: str):
        job = SyncJob.objects.filter(pk=job_id, actor=request.user).first()
        if job is None:
            return Response({"detail": "sync job not found"}, status=404)
        return Response(
            {
                "id": job.id,
                "status": job.status,
                "stage": job.stage,
                "attempt_count": job.attempt_count,
                "max_attempts": job.max_attempts,
                "duration_ms": job.duration_ms,
                "result": job.result_json or {},
                "error_code": job.error_code,
                "error_message": job.error_message or "",
                "created_at": job.created_at,
                "updated_at": job.updated_at,
                "finished_at": job.finished_at,
            }
        )


class FeishuFileAccessView(APIView):
    """Check the remote state of one authorized document asset."""

    permission_classes = [IsAuthenticated]

    def get(self, request, document_id: str):
        asset, denied = get_accessible_document(
            request.user,
            document_id,
            DocumentAction.CHECK_REMOTE,
        )
        if denied:
            return denied
        set_request_audit_target(
            request,
            target_label=(
                asset.quotation.quote_no
                if asset.quotation_id
                else asset.file_name
            ),
        )
        reference = remote_document_reference(asset)
        file_token = reference.token
        if not file_token:
            return Response(
                {
                    "exists": False,
                    "cleared": False,
                    "document_id": asset.id,
                }
            )
        if asset.source == "feishu":
            direct_url = trusted_feishu_file_url(asset)
            if not direct_url:
                return Response(
                    {
                        "exists": False,
                        "cleared": False,
                        "document_id": asset.id,
                    }
                )
            return Response(
                {
                    "exists": True,
                    "document_id": asset.id,
                    "direct_access_allowed": True,
                    "url": direct_url,
                }
            )
        try:
            client, access_token = _drive_context_for_reference(reference)
            meta = client.batch_query_file_meta(
                access_token,
                file_token,
                doc_type="file",
                with_url=True,
            )
            resolved_token = str(meta.get("doc_token") or file_token)
            if str(meta.get("doc_type") or "").lower() == "file":
                client.download_file(access_token, resolved_token)
        except FeishuAPIError as exc:
            if common._feishu_file_not_found(exc):
                visible_assets = filter_accessible_documents(
                    request.user,
                    DocumentAsset.objects.filter(pk=asset.pk),
                    DocumentAction.CHECK_REMOTE,
                )
                cleared = common._clear_feishu_file_links(
                    file_token=file_token,
                    base_qs=visible_assets,
                    quotation_id=asset.quotation_id,
                    doc_type=asset.doc_type,
                    document_id=asset.id,
                )
                return Response(
                    {
                        "exists": False,
                        "cleared": cleared > 0,
                        "document_id": asset.id,
                    }
                )
            if exc.code == 99991401:
                direct_url = trusted_feishu_file_url(asset)
                if direct_url:
                    return Response(
                        {
                            "exists": True,
                            "document_id": asset.id,
                            "direct_access_allowed": True,
                            "url": direct_url,
                        }
                    )
            return common._feishu_error_response(exc, operation="file check")

        direct_url = trusted_feishu_file_url(asset)
        return Response(
            {
                "exists": True,
                "document_id": asset.id,
                "direct_access_allowed": True,
                "url": direct_url or build_feishu_file_url(resolved_token),
            }
        )


class FeishuFileAccessBatchView(APIView):
    """Validate remote state for authorized document assets."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw_items = request.data.get("items") or []
        if not isinstance(raw_items, list):
            return Response({"detail": "items must be a list"}, status=400)

        items: list[DocumentAsset] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                return Response(
                    {"detail": "each item must be an object"},
                    status=400,
                )
            document_id = str(raw.get("document_id") or "").strip()
            if not document_id:
                return Response(
                    {"detail": "document_id is required"}, status=400
                )
            asset, denied = get_accessible_document(
                request.user,
                document_id,
                DocumentAction.CHECK_REMOTE,
            )
            if denied:
                return denied
            items.append(asset)
        if not items:
            return Response({"results": [], "cleared_count": 0})

        reference_by_asset_id = {
            str(asset.id): remote_document_reference(asset) for asset in items
        }
        unique_tokens = list(
            dict.fromkeys(
                reference.token
                for reference in reference_by_asset_id.values()
                if reference.token
            )
        )
        existing_tokens: set[str] = set()
        missing_tokens: set[str] = set()
        try:
            replica_references = [
                reference
                for reference in reference_by_asset_id.values()
                if reference.replica is not None and reference.token
            ]
            if replica_references:
                for reference in replica_references:
                    client, access_token = _drive_context_for_reference(
                        reference
                    )
                    try:
                        meta = client.batch_query_file_meta(
                            access_token,
                            reference.token,
                            doc_type="file",
                            with_url=False,
                        )
                        resolved_token = str(
                            meta.get("doc_token") or reference.token
                        )
                        existing_tokens.add(reference.token)
                        if str(meta.get("doc_type") or "").lower() == "file":
                            client.download_file(
                                access_token,
                                resolved_token,
                            )
                    except FeishuAPIError as exc:
                        if common._feishu_file_not_found(exc):
                            existing_tokens.discard(reference.token)
                            missing_tokens.add(reference.token)
                            continue
                        raise
            legacy_tokens = [
                token
                for token in unique_tokens
                if token
                not in {reference.token for reference in replica_references}
            ]
            if legacy_tokens:
                client, access_token, _ = common._system_drive_context()
                for chunk in common._chunked_file_tokens(legacy_tokens):
                    metas, failed_list = client.batch_query_files_meta(
                        access_token,
                        chunk,
                        doc_type="file",
                        with_url=False,
                    )
                    chunk_existing, chunk_missing = (
                        common._classify_batch_query_results(
                            metas,
                            failed_list,
                            chunk,
                        )
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
        except FeishuAPIError as exc:
            return common._feishu_error_response(
                exc, operation="batch file check"
            )

        results = []
        cleared_count = 0
        visible_assets = filter_accessible_documents(
            request.user,
            DocumentAsset.objects.select_related("quotation"),
        )
        for asset in items:
            file_token = reference_by_asset_id[str(asset.id)].token
            if not file_token:
                results.append(
                    {
                        "document_id": asset.id,
                        "exists": False,
                        "cleared": False,
                    }
                )
                continue
            if file_token in missing_tokens:
                cleared = common._clear_feishu_file_links(
                    file_token=file_token,
                    base_qs=visible_assets.filter(pk=asset.pk),
                    quotation_id=asset.quotation_id,
                    doc_type=asset.doc_type,
                    document_id=asset.id,
                )
                if cleared:
                    cleared_count += cleared
                results.append(
                    {
                        "document_id": asset.id,
                        "exists": False,
                        "cleared": cleared > 0,
                    }
                )
                continue
            results.append(
                {
                    "document_id": asset.id,
                    "exists": True,
                    "direct_access_allowed": False,
                }
            )

        return Response({"results": results, "cleared_count": cleared_count})


class FeishuFileContentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, document_id: str):
        asset, denied = get_accessible_document(
            request.user,
            document_id,
            DocumentAction.DOWNLOAD,
        )
        if denied:
            return denied
        set_request_audit_target(
            request,
            target_label=(
                asset.quotation.quote_no
                if asset.quotation_id
                else asset.file_name
            ),
        )
        reference = remote_document_reference(asset)
        file_token = reference.token
        if not file_token:
            return Response({"detail": "remote file not found"}, status=404)
        try:
            client, access_token = _drive_context_for_reference(reference)
            content, mime_type, resolved_name = client.download_drive_item(
                access_token,
                file_token=file_token,
                file_type=asset.doc_type,
                file_name=asset.file_name,
            )
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
                    "发版后重启后端服务，再下载在线表格。"
                )
            if detail != str(exc):
                return Response({"detail": detail}, status=502)
            return common._feishu_error_response(exc, operation="download")

        filename = resolved_name or asset.file_name or f"{asset.id}.bin"
        response = HttpResponse(
            content, content_type=mime_type or "application/octet-stream"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
