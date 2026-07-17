from __future__ import annotations

from uuid import uuid4

from django.http import FileResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.models import DocumentAsset, DocumentType, Quotation
from quotation.permissions import user_display_email, user_role
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
        qs = DocumentAsset.objects.all()
        source = request.query_params.get("source")
        email = user_display_email(request.user)
        if source in {"feishu", "feishu_upload"}:
            qs = qs.filter(source=source, created_by_email__iexact=email)
        elif source:
            qs = qs.filter(source=source)
        qs = qs.order_by("-created_at")[:200]
        return Response(DocumentAssetSerializer(qs, many=True).data)


class QuotationDocumentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quotation_id: str):
        if not Quotation.objects.filter(pk=quotation_id).exists():
            return Response({"detail": "quotation not found"}, status=404)
        qs = DocumentAsset.objects.filter(quotation_id=quotation_id).order_by(
            "-created_at"
        )
        return Response(DocumentAssetSerializer(qs, many=True).data)

    def post(self, request, quotation_id: str):
        quotation = Quotation.objects.filter(pk=quotation_id).first()
        if not quotation:
            return Response({"detail": "quotation not found"}, status=404)
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
        asset = DocumentAsset.objects.filter(pk=document_id).first()
        if not asset:
            return Response({"detail": "document not found"}, status=404)
        path = resolve_document_path(asset.storage_key)
        if not path.is_file():
            return Response({"detail": "file missing on disk"}, status=404)
        return FileResponse(
            path.open("rb"), as_attachment=True, filename=asset.file_name
        )


class DocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, document_id: str):
        asset = DocumentAsset.objects.filter(pk=document_id).first()
        if not asset:
            return Response({"detail": "document not found"}, status=404)

        email = user_display_email(request.user)
        role = user_role(request.user)
        if (
            asset.created_by_email
            and asset.created_by_email.lower() != email.lower()
        ):
            if role not in {"admin", "sales_director"}:
                return Response({"detail": "Forbidden"}, status=403)

        try:
            delete_document(asset.storage_key)
        except OSError as exc:
            return Response(
                {"detail": f"failed to delete file: {exc}"}, status=500
            )

        asset.delete()
        return Response(status=204)
