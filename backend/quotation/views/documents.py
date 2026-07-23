from __future__ import annotations

from uuid import uuid4

from django.db import IntegrityError
from django.http import FileResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.access import (
    DocumentAction,
    filter_accessible_documents,
    get_accessible_document,
    get_accessible_quotation,
)
from quotation.audit import set_request_audit_target
from quotation.models import DocumentAsset, DocumentParseResult, DocumentType
from quotation.permissions import user_display_email
from quotation.serializers import (
    DocumentAssetSerializer,
    DocumentParseResultSerializer,
    QuotationCreateSerializer,
    QuotationSerializer,
)
from quotation.services.document_parsing.excel_parser import (
    QuotationExcelParseError,
)
from quotation.services.document_parsing.pdf_parser import (
    QuotationPdfParseError,
)
from quotation.services.document_parsing.service import (
    QuotationDocumentParseError,
    confirm_document_parse_result,
    parse_and_create_quotation,
)
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
            qs = filter_accessible_documents(
                request.user,
                DocumentAsset.objects.filter(source="feishu"),
            )
            qs = (
                qs
                .select_related("quotation")
                .prefetch_related("parse_results")
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
            request.user,
            DocumentAsset.objects.select_related("quotation").prefetch_related(
                "parse_results"
            ),
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


class DocumentParseView(APIView):
    """Create or retrieve the latest reviewable parse result."""

    permission_classes = [IsAuthenticated]

    def get_asset(self, request, document_id: str):
        return get_accessible_document(
            request.user,
            document_id,
            DocumentAction.PARSE,
        )

    def get(self, request, document_id: str):
        asset, denied = self.get_asset(request, document_id)
        if denied:
            return denied
        result = asset.parse_results.order_by("-created_at", "-id").first()
        if result is None:
            return Response({"detail": "parse result not found"}, status=404)
        set_request_audit_target(request, target_label=asset.file_name)
        return Response(DocumentParseResultSerializer(result).data)

    def post(self, request, document_id: str):
        asset, denied = self.get_asset(request, document_id)
        if denied:
            return denied
        set_request_audit_target(request, target_label=asset.file_name)
        try:
            result, reused = parse_and_create_quotation(
                asset,
                actor=request.user,
            )
        except (
            QuotationDocumentParseError,
            QuotationExcelParseError,
            QuotationPdfParseError,
        ) as exc:
            return Response({"detail": str(exc)}, status=422)
        data = DocumentParseResultSerializer(result).data
        data["reused"] = reused
        data["version_created"] = bool(
            getattr(result, "_quotation_version_created", False)
        )
        return Response(data, status=200 if reused else 201)


class DocumentParseConfirmView(APIView):
    """Confirm a reviewed parse result and create a generated quotation."""

    permission_classes = [IsAuthenticated]

    def post(self, request, parse_result_id: str):
        result = (
            DocumentParseResult.objects.select_related(
                "asset",
                "quotation",
            )
            .filter(pk=parse_result_id)
            .first()
        )
        if result is None:
            return Response({"detail": "parse result not found"}, status=404)
        _, denied = get_accessible_document(
            request.user,
            result.asset_id,
            DocumentAction.PARSE,
        )
        if denied:
            return denied
        set_request_audit_target(request, target_label=result.asset.file_name)
        if result.quotation_id:
            quotation = result.quotation
            reused = True
        else:
            candidate = request.data.get("quotation")
            if candidate is None:
                candidate = result.normalized_json
            serializer = QuotationCreateSerializer(
                data=candidate,
                context={"document_import": True},
            )
            serializer.is_valid(raise_exception=True)
            try:
                quotation, reused = confirm_document_parse_result(
                    result,
                    validated_data=serializer.validated_data,
                    actor=request.user,
                )
            except IntegrityError:
                return Response(
                    {"detail": "quote_no already exists"},
                    status=409,
                )
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=409)
        quotation = quotation.__class__.objects.prefetch_related(
            "items",
            "documents",
            "versions",
        ).get(pk=quotation.pk)
        result.refresh_from_db()
        return Response(
            {
                "quotation": QuotationSerializer(quotation).data,
                "parse_result": DocumentParseResultSerializer(result).data,
                "reused": reused,
            },
            status=200 if reused else 201,
        )
