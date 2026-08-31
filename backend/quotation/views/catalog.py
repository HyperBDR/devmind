from pathlib import Path

from django.db import transaction
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.access import forbidden_response
from quotation.audit import record_audit_event
from quotation.models import (
    AuditEvent,
    DocumentAsset,
    DocumentType,
    PublicAttachment,
    PublicAttachmentStatus,
    UserQuotationCatalog,
)
from quotation.permissions import is_quotation_admin, user_display_email
from quotation.serializers import (
    UserQuotationCatalogSerializer,
    UserQuotationCatalogWriteSerializer,
)
from quotation.services.catalog_service import (
    catalog_item_changes,
    catalog_snapshot,
    empty_catalog_data,
    initialize_catalog,
    replace_catalog,
)
from quotation.services.storage import (
    delete_document,
    document_storage_key,
    write_document_stream,
)
from quotation.services.upload_validation import (
    validate_public_attachment_upload,
)


PUBLIC_ATTACHMENT_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
    ".xls": "application/vnd.ms-excel",
    ".xlsx": (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
}


def serialize_catalog(catalog: UserQuotationCatalog | None) -> dict:
    if not catalog:
        return empty_catalog_data()
    return UserQuotationCatalogSerializer(catalog).data


class UserQuotationCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        catalog = UserQuotationCatalog.objects.filter(
            user=request.user
        ).first()
        return Response(serialize_catalog(catalog))

    def put(self, request):
        serializer = UserQuotationCatalogWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            existing = UserQuotationCatalog.objects.select_for_update().filter(
                user=request.user
            ).first()
            before = catalog_snapshot(existing)
            catalog = replace_catalog(request.user, serializer.validated_data)
            after = catalog_snapshot(catalog)
            for change in catalog_item_changes(before, after):
                record_audit_event(
                    request=request,
                    module="catalog",
                    action=change["action"],
                    result=AuditEvent.RESULT_SUCCEEDED,
                    target_type=change["target_type"],
                    target_id=change["target_id"],
                    target_label=change["target_label"],
                    changes={"fields": change["fields"]}
                    if change["fields"]
                    else {},
                )
        response = Response(serialize_catalog(catalog))
        response._quotation_audit_handled = True
        return response


class LegacyCatalogImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UserQuotationCatalogWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        catalog, imported = initialize_catalog(
            request.user,
            serializer.validated_data,
        )
        return Response(
            {
                "imported": imported,
                "catalog": serialize_catalog(catalog),
            }
        )


class CatalogBootstrapView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UserQuotationCatalogWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        catalog, created = initialize_catalog(
            request.user,
            serializer.validated_data,
        )
        return Response(
            {
                "created": created,
                "catalog": serialize_catalog(catalog),
            }
        )


def public_attachment_data(item: PublicAttachment) -> dict:
    """Serialize a shared attachment for catalog and download consumers."""
    asset = item.asset
    return {
        "id": item.id,
        "asset_id": asset.id,
        "file_name": asset.file_name,
        "mime_type": asset.mime_type,
        "file_type": asset.file_name.rsplit(".", 1)[-1].lower()
        if "." in asset.file_name
        else "",
        "size_bytes": asset.size_bytes,
        "scope": item.scope,
        "product_line": item.product_line,
        "service_name": item.service_name,
        "status": item.status,
        "uploaded_by": user_display_email(item.uploaded_by)
        if item.uploaded_by_id
        else "",
        "created_at": item.created_at,
    }


class PublicAttachmentListCreateView(APIView):
    """List shared files and allow administrators to upload new ones."""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser]

    def get(self, request):
        queryset = PublicAttachment.objects.select_related(
            "asset", "uploaded_by"
        )
        if not is_quotation_admin(request.user):
            queryset = queryset.filter(status=PublicAttachmentStatus.ACTIVE)
        return Response(
            [public_attachment_data(item) for item in queryset]
        )

    def post(self, request):
        if not is_quotation_admin(request.user):
            return forbidden_response()
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "file required"}, status=400)
        try:
            validate_public_attachment_upload(upload)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        scope = str(request.data.get("scope") or "").strip()
        if not scope:
            return Response({"detail": "scope required"}, status=400)
        asset_id = _uuid()
        storage_key = document_storage_key(asset_id)
        _, size_bytes = write_document_stream(upload, storage_key)
        try:
            asset = DocumentAsset.objects.create(
                id=asset_id,
                doc_type="attachment",
                file_name=upload.name,
                mime_type=PUBLIC_ATTACHMENT_MIME_TYPES[
                    Path(upload.name).suffix.lower()
                ],
                storage_key=storage_key,
                size_bytes=size_bytes,
                source="public",
                created_by_email=user_display_email(request.user),
            )
            attachment = PublicAttachment.objects.create(
                asset=asset,
                scope=scope,
                product_line=str(
                    request.data.get("product_line") or ""
                ).strip(),
                service_name=str(
                    request.data.get("service_name") or ""
                ).strip(),
                uploaded_by=request.user,
            )
        except Exception:
            delete_document(storage_key)
            raise
        return Response(public_attachment_data(attachment), status=201)


class PublicAttachmentStatusView(APIView):
    """Archive or reactivate a public attachment."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, attachment_id: str):
        if not is_quotation_admin(request.user):
            return forbidden_response()
        attachment = PublicAttachment.objects.select_related(
            "asset", "uploaded_by"
        ).filter(pk=attachment_id).first()
        if attachment is None:
            return Response({"detail": "attachment not found"}, status=404)
        value = str(request.data.get("status") or "").strip()
        if value not in PublicAttachmentStatus.values:
            return Response({"detail": "invalid status"}, status=400)
        attachment.status = value
        attachment.save(update_fields=["status", "updated_at"])
        return Response(public_attachment_data(attachment))


def _uuid() -> str:
    import uuid

    return str(uuid.uuid4())
