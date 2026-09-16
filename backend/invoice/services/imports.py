from __future__ import annotations

from decimal import Decimal

from django.db import IntegrityError, transaction

from core.file_hash import hash_file
from invoice.models import (
    Invoice,
    InvoiceDocument,
    InvoiceDocumentKind,
    InvoiceDocumentPurpose,
    InvoiceItem,
    InvoiceNumberingMode,
    InvoiceParseResult,
    InvoiceParseStatus,
    InvoiceSourceType,
    InvoiceStatus,
)
from invoice.parsing.pdf_parser import (
    PARSER_NAME,
    PARSER_VERSION,
    parse_invoice_pdf,
)
from invoice.services.documents import invoice_storage


INVOICE_FIELDS = (
    "due_date",
    "currency",
    "seller_name",
    "seller_tax_id",
    "seller_address",
    "seller_website",
    "seller_email",
    "customer_name",
    "customer_tax_id",
    "customer_address",
    "customer_contact_person",
    "customer_contact_email",
    "customer_contact_phone",
    "contact_person",
    "contact_email",
    "purchase_order_no",
    "payment_terms",
    "region",
    "sales_owner",
    "tax_rate",
    "subtotal_amount",
    "tax_amount",
    "total_amount",
    "notes",
    "additional_notes",
    "remarks",
    "bank_account_name",
    "bank_name",
    "bank_address",
    "bank_account_number",
    "bank_code",
    "bank_branch_code",
    "bank_swift_code",
    "remittance_instruction",
    "signatory_name",
    "signatory_title",
)

ITEM_FIELDS = (
    "line_no",
    "product_code",
    "product_name",
    "description",
    "quantity",
    "unit_price",
    "discount_amount",
    "net_amount",
    "tax_rate",
    "tax_amount",
    "total_amount",
)

CONTACT_FIELDS = (
    "customer_contact_person",
    "customer_contact_email",
    "customer_contact_phone",
    "contact_person",
    "contact_email",
)

def _fallback_import_number(
    document: InvoiceDocument,
    source_no: str,
) -> str:
    """Return a stable fallback when the source number already exists."""
    suffix = f"__PDF_{str(document.id).replace('-', '')[:8]}"
    return f"{source_no[:120 - len(suffix)]}{suffix}"


def _source_number(document: InvoiceDocument, parsed_number: str) -> str:
    return str(parsed_number or "").strip()[:120]


def _validate_required_fields(parsed) -> None:
    """Reject records whose sales-critical fields were not read from PDF."""
    missing = []
    if not str(parsed.invoice_no or "").strip():
        missing.append("invoice number")
    if parsed.invoice_date is None:
        missing.append("invoice date")
    if not str(parsed.customer_name or "").strip():
        missing.append("customer")
    if not str(parsed.currency or "").strip():
        missing.append("currency")
    if parsed.total_amount is None or parsed.total_amount <= 0:
        missing.append("positive total amount")
    if missing:
        fields = ", ".join(missing)
        raise ValueError(
            f"Required invoice fields were not found in the PDF: {fields}"
        )


def _item_data(item, line_no: int) -> dict:
    data = item.model_dump(mode="python")
    data["line_no"] = line_no
    data["product_name"] = (
        str(data.get("product_name") or "").strip()
        or str(data.get("description") or "").strip()
        or "Unspecified"
    )
    return {field: data[field] for field in ITEM_FIELDS}


def _invoice_amounts(parsed, items: list[dict]) -> dict:
    subtotal = parsed.subtotal_amount
    tax = parsed.tax_amount
    total = parsed.total_amount
    if not subtotal and items:
        subtotal = sum(
            (item["net_amount"] for item in items),
            Decimal("0"),
        )
    if not tax and items:
        tax = sum(
            (item["tax_amount"] for item in items),
            Decimal("0"),
        )
    if not total:
        total = subtotal + tax
    return {
        "subtotal_amount": subtotal,
        "tax_amount": tax,
        "total_amount": total,
    }


def _save_parse_result(
    document: InvoiceDocument,
    *,
    content_hash: str,
    parsed,
    actor,
    status: str,
) -> InvoiceParseResult:
    """Persist the current parser output before changing derived records."""
    result, _ = InvoiceParseResult.objects.update_or_create(
        document=document,
        content_hash=content_hash,
        parser_version=PARSER_VERSION,
        defaults={
            "parser_name": PARSER_NAME,
            "status": status,
            "normalized_json": parsed.invoice.model_dump(mode="json"),
            "field_confidence_json": parsed.field_confidence,
            "validation_errors_json": parsed.validation_errors,
            "validation_warnings_json": parsed.validation_warnings,
            "confidence": parsed.confidence,
            "created_by_email": (
                actor.email or actor.username
                if getattr(actor, "is_authenticated", False)
                else ""
            ).lower(),
        },
    )
    return result


def _import_status(parsed) -> str:
    """Only complete formal invoices enter issued sales records."""
    if parsed.document_kind != InvoiceDocumentKind.INVOICE:
        return InvoiceStatus.DRAFT
    try:
        _validate_required_fields(parsed.invoice)
    except ValueError:
        return InvoiceStatus.DRAFT
    return InvoiceStatus.ISSUED


def parse_and_create_invoice(
    document: InvoiceDocument,
    *,
    actor=None,
    source_type: str = InvoiceSourceType.PDF_UPLOAD,
    region_hint: str = "",
) -> tuple[Invoice | None, bool]:
    """Parse one imported PDF and immediately create its sales record."""
    path = invoice_storage().resolve(document.storage_key)
    if not path.is_file():
        raise ValueError("document file is missing")
    content_hash = document.content_hash or hash_file(path)
    existing_document = (
        InvoiceDocument.objects.filter(
            content_hash=content_hash,
            invoice__isnull=False,
        )
        .exclude(pk=document.pk)
        .select_related("invoice")
        .first()
    )
    if existing_document:
        document.invoice = existing_document.invoice
        document.content_hash = content_hash
        document.save(
            update_fields=["invoice", "content_hash", "updated_at"]
        )
        return existing_document.invoice, True

    parsed = parse_invoice_pdf(path)
    document_kind = (
        parsed.document_kind
        if parsed.document_kind in InvoiceDocumentKind.values
        else InvoiceDocumentKind.INVOICE
    )
    result = _save_parse_result(
        document,
        content_hash=content_hash,
        parsed=parsed,
        actor=actor,
        status=InvoiceParseStatus.READY,
    )
    linked_invoice = document.invoice
    if (
        document_kind != InvoiceDocumentKind.INVOICE
        and document.purpose == InvoiceDocumentPurpose.SUPPORTING
    ):
        with transaction.atomic():
            locked_document = InvoiceDocument.objects.select_for_update().get(
                pk=document.pk
            )
            locked_document.invoice = None
            locked_document.purpose = InvoiceDocumentPurpose.SOURCE
            locked_document.save(
                update_fields=["invoice", "purpose", "updated_at"]
            )
        document.invoice = None
        document.purpose = InvoiceDocumentPurpose.SOURCE
        linked_invoice = None
    items = [
        _item_data(item, index)
        for index, item in enumerate(parsed.invoice.items, start=1)
    ]
    data = parsed.invoice.model_dump(mode="python")
    data.update(_invoice_amounts(parsed.invoice, items))
    data["customer_name"] = str(data["customer_name"]).strip()
    data["currency"] = str(data["currency"]).strip().upper()
    if not data.get("region") and region_hint:
        data["region"] = region_hint[:120]

    if linked_invoice is not None:
        with transaction.atomic():
            locked = InvoiceDocument.objects.select_for_update().get(
                pk=document.pk
            )
            invoice = Invoice.objects.select_for_update().get(
                pk=locked.invoice_id
            )
            update_data = {
                field: data[field]
                for field in INVOICE_FIELDS
            }
            parsed_customer_contact = any(
                data[field] for field in CONTACT_FIELDS[:3]
            )
            parsed_invoice_contact = any(
                data[field] for field in CONTACT_FIELDS[3:]
            )
            existing_customer_contact = any(
                getattr(invoice, field) for field in CONTACT_FIELDS[:3]
            )
            existing_invoice_contact = any(
                getattr(invoice, field) for field in CONTACT_FIELDS[3:]
            )
            role_swap = (
                parsed_customer_contact
                and not parsed_invoice_contact
                and existing_invoice_contact
                and not existing_customer_contact
            )
            for field in CONTACT_FIELDS:
                if data[field]:
                    continue
                if role_swap and field in CONTACT_FIELDS[3:]:
                    update_data[field] = ""
                else:
                    update_data[field] = getattr(invoice, field)
            update_data["invoice_date"] = parsed.invoice.invoice_date
            update_data["document_kind"] = document_kind
            update_data["status"] = _import_status(parsed)
            source_number = str(parsed.invoice.invoice_no or "").strip()
            if source_number and source_number != invoice.invoice_no:
                conflict = (
                    document_kind == InvoiceDocumentKind.INVOICE
                    and Invoice.objects.filter(
                        invoice_no=source_number,
                        document_kind=InvoiceDocumentKind.INVOICE,
                    ).exclude(pk=invoice.pk).exists()
                )
                if not conflict:
                    update_data["invoice_no"] = source_number[:120]
            update_data.update(_invoice_amounts(parsed.invoice, items))
            for field, value in update_data.items():
                setattr(invoice, field, value)
            invoice.save(update_fields=[*update_data, "updated_at"])
            InvoiceItem.objects.filter(invoice=invoice).delete()
            InvoiceItem.objects.bulk_create(
                [InvoiceItem(invoice=invoice, **item) for item in items]
            )
            result.status = InvoiceParseStatus.CONFIRMED
            result.save(update_fields=["status", "updated_at"])
            if locked.purpose != InvoiceDocumentPurpose.SOURCE:
                locked.purpose = InvoiceDocumentPurpose.SOURCE
                locked.save(update_fields=["purpose", "updated_at"])
        return invoice, True

    with transaction.atomic():
        locked = InvoiceDocument.objects.select_for_update().get(
            pk=document.pk
        )
        if locked.invoice_id:
            return locked.invoice, True
        source_number = _source_number(locked, parsed.invoice.invoice_no)
        invoice_data = {
            field: data[field]
            for field in INVOICE_FIELDS
        }
        create_data = {
            "numbering_mode": InvoiceNumberingMode.CUSTOM,
            "invoice_date": parsed.invoice.invoice_date,
            "document_kind": document_kind,
            "status": _import_status(parsed),
            "source_type": source_type,
            "created_by": (
                actor
                if getattr(actor, "is_authenticated", False)
                else None
            ),
            **invoice_data,
        }
        try:
            with transaction.atomic():
                invoice = Invoice.objects.create(
                    invoice_no=source_number,
                    **create_data,
                )
        except IntegrityError:
            if not source_number:
                raise
            invoice = Invoice.objects.create(
                invoice_no=_fallback_import_number(
                    locked,
                    source_number,
                ),
                **create_data,
            )
        InvoiceItem.objects.bulk_create(
            [InvoiceItem(invoice=invoice, **item) for item in items]
        )
        locked.invoice = invoice
        locked.content_hash = content_hash
        locked.purpose = InvoiceDocumentPurpose.SOURCE
        locked.save(
            update_fields=[
                "invoice",
                "content_hash",
                "purpose",
                "updated_at",
            ]
        )
        result.status = InvoiceParseStatus.CONFIRMED
        result.save(update_fields=["status", "updated_at"])
    return invoice, False
