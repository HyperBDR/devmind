"""Persistence helpers for Invoice source and generated documents."""

from __future__ import annotations

import hashlib
import re
import uuid

from django.conf import settings
from django.db import transaction

from core.document_storage import LocalDocumentStorage
from invoice.models import (
    Invoice,
    InvoiceDocument,
    InvoiceDocumentPurpose,
    InvoiceDocumentStatus,
    InvoiceDocumentType,
    InvoiceStatus,
)
from invoice.services.pdf_renderer import render_invoice_pdf


def invoice_storage() -> LocalDocumentStorage:
    """Return the configured local Invoice document store."""
    return LocalDocumentStorage(
        settings.INVOICE_STORAGE,
        chunk_size=settings.INVOICE_UPLOAD_CHUNK_BYTES,
    )


def issued_invoice_filename(invoice: Invoice) -> str:
    """Return a safe attachment name derived from the invoice number."""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", invoice.invoice_no).strip("-.")
    return f"{stem or invoice.id}.pdf"


def latest_issued_document(invoice: Invoice) -> InvoiceDocument | None:
    """Return the current generated PDF for an issued invoice."""
    return (
        invoice.documents.filter(
            purpose=InvoiceDocumentPurpose.ISSUED,
            status=InvoiceDocumentStatus.ACTIVE,
        )
        .order_by("-created_at", "-id")
        .first()
    )


def latest_downloadable_document(
    invoice: Invoice,
) -> InvoiceDocument | None:
    """Prefer the generated PDF and fall back to an imported source PDF."""
    generated = latest_issued_document(invoice)
    if generated is not None:
        return generated
    return (
        invoice.documents.filter(
            purpose=InvoiceDocumentPurpose.SOURCE,
            status=InvoiceDocumentStatus.ACTIVE,
            document_type=InvoiceDocumentType.PDF,
        )
        .order_by("-created_at", "-id")
        .first()
    )


def generate_issued_invoice_pdf(
    invoice: Invoice,
    *,
    actor,
) -> InvoiceDocument:
    """Render and persist a new current PDF for an issued invoice."""
    if invoice.status not in {InvoiceStatus.ISSUED, InvoiceStatus.PAID}:
        raise ValueError("Only issued or paid invoices can generate a PDF.")
    invoice = Invoice.objects.prefetch_related("items").get(pk=invoice.pk)
    content = render_invoice_pdf(invoice)
    document_id = str(uuid.uuid4())
    storage_key = f"issued/{invoice.id}/{document_id}.pdf"
    storage = invoice_storage()
    storage.write_atomic(content, storage_key)
    try:
        with transaction.atomic():
            Invoice.objects.select_for_update().get(pk=invoice.pk)
            invoice.documents.filter(
                purpose=InvoiceDocumentPurpose.ISSUED,
                status=InvoiceDocumentStatus.ACTIVE,
            ).update(status=InvoiceDocumentStatus.ARCHIVED)
            return InvoiceDocument.objects.create(
                id=document_id,
                invoice=invoice,
                file_name=issued_invoice_filename(invoice),
                storage_key=storage_key,
                content_type="application/pdf",
                document_type=InvoiceDocumentType.PDF,
                purpose=InvoiceDocumentPurpose.ISSUED,
                size_bytes=len(content),
                content_hash=hashlib.sha256(content).hexdigest(),
                created_by=actor,
            )
    except Exception:
        storage.delete(storage_key)
        raise
