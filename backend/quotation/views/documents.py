from __future__ import annotations

from uuid import uuid4

from django.http import FileResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.access import (
    DocumentAction,
    can_delete_document,
    filter_accessible_documents,
    forbidden_response,
    get_accessible_document,
    get_accessible_quotation,
)
from quotation.audit import set_request_audit_target
from quotation.models import DocumentAsset, DocumentType
from quotation.permissions import user_display_email
from quotation.serializers import DocumentAssetSerializer
from quotation.services.storage import (
    delete_document,
    document_storage_key,
    resolve_document_path,
    write_document,
)
from quotation.services.upload_validation import validate_quotation_upload


class DocumentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        source = request.query_params.get("source")
        if source == "feishu":
            qs = (
                DocumentAsset.objects.filter(
                    source="feishu",
                    created_by_email__iexact=user_display_email(request.user),
                )
                .order_by("-created_at")[:1000]
            )
            documents = []
            seen_tokens = set()
            for document in qs:
                token = document.feishu_file_token or document.id
                if token in seen_tokens:
                    continue
                seen_tokens.add(token)
                documents.append(document)
                if len(documents) >= 200:
                    break
            return Response(
                DocumentAssetSerializer(documents, many=True).data
            )

        qs = filter_accessible_documents(
            request.user, DocumentAsset.objects.select_related("quotation")
        )
        if source == "feishu_upload":
            qs = qs.filter(source=source)
        elif source:
            qs = qs.filter(source=source)
        qs = qs.order_by("-created_at")[:200]
        return Response(DocumentAssetSerializer(qs, many=True).data)


class QuotationDocumentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quotation_id: str):
        quotation, denied = get_accessible_quotation(
            request.user,
            quotation_id,
        )
        if denied:
            return denied
        set_request_audit_target(
            request,
            target_label=quotation.quote_no,
        )
        qs = DocumentAsset.objects.filter(quotation_id=quotation_id).order_by(
            "-created_at"
        )
        return Response(DocumentAssetSerializer(qs, many=True).data)

    def post(self, request, quotation_id: str):
        quotation, denied = get_accessible_quotation(
            request.user, quotation_id, DocumentAction.UPLOAD
        )
        if denied:
            return denied
        set_request_audit_target(
            request,
            target_label=quotation.quote_no,
        )
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "file required"}, status=400)
        try:
            validate_quotation_upload(upload)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        doc_type = (
            request.query_params.get("doc_type")
            or request.data.get("doc_type")
            or "excel"
        )
        if doc_type not in DocumentType.values:
            return Response({"detail": "invalid doc_type"}, status=400)
        asset_id = str(uuid4())
        storage_key = document_storage_key(asset_id, quotation_id)
        content = upload.read()
        write_document(content, storage_key)
        try:
            asset = DocumentAsset.objects.create(
                id=asset_id,
                quotation=quotation,
                doc_type=doc_type,
                file_name=upload.name,
                mime_type=upload.content_type or "application/octet-stream",
                storage_key=storage_key,
                size_bytes=len(content),
                source="local",
                created_by_email=user_display_email(request.user),
            )
        except Exception:
            delete_document(storage_key)
            raise
        return Response(DocumentAssetSerializer(asset).data, status=201)


class DocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, document_id: str):
        asset, denied = get_accessible_document(
            request.user, document_id, DocumentAction.DOWNLOAD
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
        path = resolve_document_path(asset.storage_key)
        if not path.is_file():
            return Response({"detail": "file missing on disk"}, status=404)
        return FileResponse(
            path.open("rb"), as_attachment=True, filename=asset.file_name
        )


class DocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, document_id: str):
        asset, denied = get_accessible_document(
            request.user, document_id, DocumentAction.DELETE
        )
        if denied:
            return denied
        if not can_delete_document(request.user, asset):
            return forbidden_response()
        set_request_audit_target(
            request,
            target_label=(
                asset.quotation.quote_no
                if asset.quotation_id
                else asset.file_name
            ),
        )

        try:
            delete_document(asset.storage_key)
        except OSError as exc:
            return Response(
                {"detail": f"failed to delete file: {exc}"}, status=500
            )

        asset.delete()
        return Response(status=204)
