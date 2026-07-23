from __future__ import annotations

from hashlib import sha256
import logging
from time import perf_counter

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from quotation.models import (
    DocumentAsset,
    DocumentParseResult,
    DocumentParseStatus,
    Quotation,
    QuotationSourceType,
    QuoteStatus,
    SyncJob,
    SyncJobStatus,
    SyncJobType,
)
from quotation.permissions import user_display_email
from quotation.services.document_parsing.excel_parser import (
    PARSER_NAME,
    PARSER_VERSION,
    QuotationExcelParseError,
    parse_standard_quotation_excel,
)
from quotation.services.document_parsing.flexible_parser import (
    complete_document_parse,
)
from quotation.services.document_parsing.pdf_parser import (
    PARSER_NAME as PDF_PARSER_NAME,
    PARSER_VERSION as PDF_PARSER_VERSION,
    QuotationPdfParseError,
    parse_standard_quotation_pdf,
)
from quotation.services.quotation_service import (
    build_quotation,
    create_version_snapshot,
    replace_items,
)
from quotation.services.storage import resolve_document_path

logger = logging.getLogger(__name__)


class QuotationDocumentParseError(ValueError):
    """Raised when a quotation document cannot be parsed safely."""


def _file_hash(path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parser_for_asset(asset: DocumentAsset):
    file_name = asset.file_name.lower()
    doc_type = str(asset.doc_type or "").lower()
    if file_name.startswith("~$"):
        raise QuotationDocumentParseError(
            "Temporary office files are not business documents"
        )
    if doc_type == "excel" and file_name.endswith(".xlsx"):
        return (
            PARSER_NAME,
            PARSER_VERSION,
            parse_standard_quotation_excel,
            QuotationExcelParseError,
        )
    if doc_type == "pdf" and file_name.endswith(".pdf"):
        return (
            PDF_PARSER_NAME,
            PDF_PARSER_VERSION,
            parse_standard_quotation_pdf,
            QuotationPdfParseError,
        )
    raise QuotationDocumentParseError(
        "Only .xlsx and text PDF quotation documents are supported"
    )


def parser_version_for_asset(asset: DocumentAsset) -> str:
    """Return the parser version currently required for an asset."""
    return _parser_for_asset(asset)[1]


def parse_document_asset(
    asset: DocumentAsset, *, actor=None
) -> tuple[DocumentParseResult, bool]:
    """Parse one supported asset and return its reviewable result."""
    parser_name, parser_version, parser, parser_error = _parser_for_asset(
        asset
    )
    path = resolve_document_path(asset.storage_key)
    if not path.is_file():
        raise QuotationDocumentParseError("Document file is missing")
    started = perf_counter()
    hash_started = perf_counter()
    content_hash = _file_hash(path)
    hash_duration_ms = round((perf_counter() - hash_started) * 1000)
    existing = DocumentParseResult.objects.filter(
        asset=asset,
        content_hash=content_hash,
        parser_version=parser_version,
    ).first()
    if existing and existing.status not in {
        DocumentParseStatus.FAILED,
        DocumentParseStatus.PENDING,
        DocumentParseStatus.RUNNING,
    }:
        return existing, True

    job = SyncJob.objects.create(
        job_type=SyncJobType.PARSE,
        status=SyncJobStatus.RUNNING,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        asset=asset,
        quotation=asset.quotation,
        payload_json={
            "parser_name": parser_name,
            "parser_version": parser_version,
            "content_hash": content_hash,
        },
        stage="parsing",
        attempt_count=1,
        started_at=timezone.now(),
        heartbeat_at=timezone.now(),
    )
    result, _ = DocumentParseResult.objects.update_or_create(
        asset=asset,
        content_hash=content_hash,
        parser_version=parser_version,
        defaults={
            "sync_job": job,
            "status": DocumentParseStatus.RUNNING,
            "parser_name": parser_name,
            "created_by_email": (
                user_display_email(actor) if actor is not None else ""
            ),
        },
    )
    try:
        parse_started = perf_counter()
        try:
            standard_parsed = parser(path)
        except (
            parser_error,
            QuotationExcelParseError,
            QuotationPdfParseError,
        ):
            standard_parsed = None
        parsed = complete_document_parse(asset, path, standard_parsed)
        parse_duration_ms = round((perf_counter() - parse_started) * 1000)
        if parsed.document_kind == "not_quotation":
            status = DocumentParseStatus.NOT_QUOTATION
        elif parsed.validation_errors:
            status = DocumentParseStatus.REVIEW_REQUIRED
        else:
            status = DocumentParseStatus.READY
        with transaction.atomic():
            result.status = status
            result.normalized_json = parsed.quotation.model_dump(mode="json")
            result.source_totals_json = parsed.source_totals
            result.field_confidence_json = parsed.field_confidence
            result.validation_errors_json = parsed.validation_errors
            result.validation_warnings_json = parsed.validation_warnings
            result.confidence = parsed.confidence
            result.save()
            job.status = SyncJobStatus.SUCCESS
            job.result_json = {
                "parse_result_id": result.id,
                "status": status,
                "confidence": str(parsed.confidence),
                "error_count": len(parsed.validation_errors),
                "warning_count": len(parsed.validation_warnings),
                "hash_duration_ms": hash_duration_ms,
                "parse_duration_ms": parse_duration_ms,
            }
            job.stage = "finished"
            job.finished_at = timezone.now()
            job.duration_ms = round((perf_counter() - started) * 1000)
            job.save(
                update_fields=[
                    "status",
                    "stage",
                    "result_json",
                    "finished_at",
                    "duration_ms",
                    "updated_at",
                ]
            )
            logger.info(
                "quotation_document_parsed",
                extra={
                    "asset_id": asset.id,
                    "doc_type": asset.doc_type,
                    "size_bytes": asset.size_bytes,
                    "hash_duration_ms": hash_duration_ms,
                    "parse_duration_ms": parse_duration_ms,
                    "duration_ms": job.duration_ms,
                    "status": status,
                },
            )
    except Exception as exc:
        result.status = DocumentParseStatus.FAILED
        result.validation_errors_json = [
            {
                "field": "document",
                "code": "parse_failed",
                "detail": str(exc),
            }
        ]
        result.save(
            update_fields=[
                "status",
                "validation_errors_json",
                "updated_at",
            ]
        )
        job.status = SyncJobStatus.FAILED
        job.error_code = "parse_failed"
        job.error_message = str(exc)[:500]
        job.stage = "failed"
        job.finished_at = timezone.now()
        job.duration_ms = round((perf_counter() - started) * 1000)
        job.save(
            update_fields=[
                "status",
                "error_code",
                "error_message",
                "stage",
                "finished_at",
                "duration_ms",
                "updated_at",
            ]
        )
        raise
    return result, False


def _validation_errors_from_serializer(exc: serializers.ValidationError):
    detail = getattr(exc, "detail", {})
    if isinstance(detail, dict):
        return [
            {
                "field": str(field),
                "code": "invalid",
                "detail": "; ".join(str(item) for item in value)
                if isinstance(value, list)
                else str(value),
            }
            for field, value in detail.items()
        ]
    return [
        {
            "field": "quotation",
            "code": "invalid",
            "detail": str(detail),
        }
    ]


def _unique_import_quote_no(
    result: DocumentParseResult,
    source_no: str,
    *,
    force_suffix: bool = False,
) -> str:
    """Build a stable internal number while preserving the source number."""
    if (
        not force_suffix
        and not Quotation.objects.filter(quote_no=source_no).exists()
    ):
        return source_no
    asset_key = str(result.asset_id).replace("-", "")
    suffix = f"__{result.asset.doc_type.upper()}_{asset_key}"
    base = source_no[: 120 - len(suffix)]
    candidate = f"{base}{suffix}"
    counter = 2
    while Quotation.objects.filter(quote_no=candidate).exists():
        numbered_suffix = f"{suffix}_{counter}"
        base = source_no[: 120 - len(numbered_suffix)]
        candidate = f"{base}{numbered_suffix}"
        counter += 1
    return candidate


def discard_non_quotation_import(result: DocumentParseResult) -> None:
    """Detach and remove a derived quote for a non-quotation document."""
    with transaction.atomic():
        locked = (
            DocumentParseResult.objects.select_for_update()
            .select_related("asset")
            .get(pk=result.pk)
        )
        asset = locked.asset
        quotation_id = asset.quotation_id
        if quotation_id:
            asset.parse_results.filter(quotation_id=quotation_id).exclude(
                pk=locked.pk
            ).update(
                quotation=None,
                status=DocumentParseStatus.SUPERSEDED,
            )
            asset.quotation = None
            asset.save(update_fields=["quotation"])
        locked.quotation = None
        locked.status = DocumentParseStatus.NOT_QUOTATION
        locked.confirmed_at = None
        locked.save(
            update_fields=[
                "quotation",
                "status",
                "confirmed_at",
                "updated_at",
            ]
        )
        if quotation_id:
            quotation = Quotation.objects.filter(
                id=quotation_id,
                source_type=QuotationSourceType.DOCUMENT_IMPORT,
            ).first()
            if quotation and not quotation.documents.exists():
                quotation.delete()
        result.status = DocumentParseStatus.NOT_QUOTATION
        result.quotation = None


def parse_and_create_quotation(
    asset: DocumentAsset, *, actor=None
) -> tuple[DocumentParseResult, bool]:
    """Parse a document and automatically save a generated quotation."""
    if asset.quotation_id:
        confirmed = (
            asset.parse_results.filter(
                quotation_id=asset.quotation_id,
                status=DocumentParseStatus.CONFIRMED,
            )
            .order_by("-created_at", "-id")
            .first()
        )
        if (
            confirmed is not None
            and confirmed.parser_version == parser_version_for_asset(asset)
        ):
            return confirmed, True
    result, reused_parse = parse_document_asset(asset, actor=actor)
    if result.quotation_id:
        return result, True
    if result.status == DocumentParseStatus.NOT_QUOTATION:
        discard_non_quotation_import(result)
        return result, reused_parse
    warning_codes = {
        warning.get("code")
        for warning in result.validation_warnings_json
        if isinstance(warning, dict)
    }
    if "ocr_required" in warning_codes:
        return result, reused_parse
    if result.status == DocumentParseStatus.REVIEW_REQUIRED:
        result.status = DocumentParseStatus.FAILED
        result.error_message = "Automatic parsing validation failed"
        result.save(update_fields=["status", "error_message", "updated_at"])
        return result, reused_parse
    if result.status != DocumentParseStatus.READY:
        return result, reused_parse

    from quotation.serializers import QuotationCreateSerializer

    serializer = QuotationCreateSerializer(
        data=result.normalized_json,
        context={"document_import": True},
    )
    try:
        serializer.is_valid(raise_exception=True)
    except serializers.ValidationError as exc:
        result.status = DocumentParseStatus.FAILED
        result.validation_errors_json = _validation_errors_from_serializer(exc)
        result.save(
            update_fields=[
                "status",
                "validation_errors_json",
                "updated_at",
            ]
        )
        return result, reused_parse

    if asset.quotation_id:
        quotation = update_imported_quotation_from_parse(
            result,
            validated_data=serializer.validated_data,
            actor=actor,
        )
        reused_quotation = True
    else:
        quotation, reused_quotation = confirm_document_parse_result(
            result,
            validated_data=serializer.validated_data,
            actor=actor,
        )
    result.refresh_from_db()
    return result, reused_quotation


def update_imported_quotation_from_parse(
    result: DocumentParseResult,
    *,
    validated_data: dict,
    actor=None,
) -> Quotation:
    """Update an imported quotation when its parser version advances."""
    with transaction.atomic():
        locked = DocumentParseResult.objects.select_for_update().get(
            pk=result.pk
        )
        quotation = Quotation.objects.select_for_update().get(
            pk=locked.asset.quotation_id
        )
        data = dict(validated_data)
        items = data.pop("items", [])
        quotation.source_quote_no = str(data["quote_no"])
        field_names = (
            "product_line",
            "project_name",
            "currency",
            "payment_term_option",
            "payment_terms",
            "quote_date",
            "expire_date",
            "tax_label",
            "vat_rate",
            "remarks_disclaimer",
            "issuer_company_name",
            "issuer_contact_name",
            "issuer_contact_email",
            "issuer_contact_title",
            "issuer_signature",
            "client_company",
            "contact_person",
            "email",
            "billing_company",
            "billing_contact",
            "billing_email",
        )
        for field in field_names:
            if field in data:
                setattr(quotation, field, data[field])
        quotation.status = QuoteStatus.GENERATED
        quotation.source_type = QuotationSourceType.DOCUMENT_IMPORT
        quotation.save(
            update_fields=[
                "source_quote_no",
                *field_names,
                "status",
                "source_type",
                "updated_at",
            ]
        )
        replace_items(quotation, items)
        operator_email = (
            user_display_email(actor)
            if actor is not None
            else locked.created_by_email
        )
        create_version_snapshot(
            quotation,
            operator_email=operator_email,
            notes=(
                f"Reparsed {locked.asset.file_name} with "
                f"{locked.parser_version}"
            ),
        )
        locked.asset.parse_results.filter(
            status=DocumentParseStatus.CONFIRMED,
        ).exclude(pk=locked.pk).update(
            status=DocumentParseStatus.SUPERSEDED,
        )
        locked.quotation = quotation
        locked.status = DocumentParseStatus.CONFIRMED
        locked.confirmed_at = timezone.now()
        locked.save(
            update_fields=[
                "quotation",
                "status",
                "confirmed_at",
                "updated_at",
            ]
        )
        locked._quotation_version_created = True
        result._quotation_version_created = True
        return quotation


def link_parse_result_to_quotation(
    result: DocumentParseResult, quotation: Quotation
) -> None:
    """Link another source document for a quotation that already exists."""
    with transaction.atomic():
        locked = DocumentParseResult.objects.select_for_update().get(
            pk=result.pk
        )
        if locked.quotation_id:
            return
        locked.asset.quotation = quotation
        locked.asset.save(update_fields=["quotation"])
        locked.quotation = quotation
        locked.status = DocumentParseStatus.CONFIRMED
        locked.confirmed_at = timezone.now()
        locked.save(
            update_fields=[
                "quotation",
                "status",
                "confirmed_at",
                "updated_at",
            ]
        )


def confirm_document_parse_result(
    result: DocumentParseResult,
    *,
    validated_data: dict,
    actor=None,
):
    """Create one generated quotation from a reviewed parse result."""
    with transaction.atomic():
        locked = DocumentParseResult.objects.select_for_update().get(
            pk=result.pk
        )
        if locked.quotation_id:
            return locked.quotation, True
        if locked.status not in {
            DocumentParseStatus.READY,
            DocumentParseStatus.REVIEW_REQUIRED,
        }:
            raise ValueError("Parse result is not ready for confirmation")
        data = dict(validated_data)
        items = data.pop("items", [])
        source_quote_no = str(data["quote_no"])
        data["source_quote_no"] = source_quote_no
        data["quote_no"] = _unique_import_quote_no(locked, source_quote_no)
        data["created_by_email"] = (
            user_display_email(actor)
            if actor is not None
            else locked.created_by_email
        )
        data["source_type"] = QuotationSourceType.DOCUMENT_IMPORT
        try:
            with transaction.atomic():
                quotation = build_quotation(data=data, items_data=items)
        except IntegrityError:
            data["quote_no"] = _unique_import_quote_no(
                locked,
                source_quote_no,
                force_suffix=True,
            )
            with transaction.atomic():
                quotation = build_quotation(data=data, items_data=items)
        quotation.status = QuoteStatus.GENERATED
        quotation.save(update_fields=["status", "updated_at"])
        locked.asset.quotation = quotation
        locked.asset.save(update_fields=["quotation"])
        create_version_snapshot(
            quotation,
            operator_email=data["created_by_email"],
            notes=f"Imported from {locked.asset.file_name}",
        )
        locked.quotation = quotation
        locked.status = DocumentParseStatus.CONFIRMED
        locked.confirmed_at = timezone.now()
        locked.save(
            update_fields=[
                "quotation",
                "status",
                "confirmed_at",
                "updated_at",
            ]
        )
        return quotation, False
