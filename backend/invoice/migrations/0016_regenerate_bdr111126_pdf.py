import hashlib
import uuid

from django.db import migrations

INVOICE_NO = "BDR111126"


def regenerate_pdf(apps, schema_editor):
    """Re-render the generated PDF of one invoice with the fixed layout."""
    Invoice = apps.get_model("invoice", "Invoice")
    InvoiceDocument = apps.get_model("invoice", "InvoiceDocument")
    matches = list(
        Invoice.objects.select_for_update().filter(
            invoice_no=INVOICE_NO,
            status__in=["issued", "paid"],
        )
    )
    if len(matches) != 1:
        state = "not found" if not matches else "ambiguous"
        print(f"\n  invoice pdf {INVOICE_NO}: {state}, skipped")
        return
    invoice = matches[0]
    current = (
        invoice.documents.filter(purpose="issued", status="active")
        .order_by("-created_at", "-id")
        .first()
    )
    if current is None:
        print(f"\n  invoice pdf {INVOICE_NO}: no generated pdf, skipped")
        return

    # Imported lazily so fresh databases never depend on these modules.
    from invoice.services.documents import invoice_storage
    from invoice.services.pdf_renderer import (
        InvoicePdfRenderError,
        render_invoice_pdf,
    )

    try:
        content = render_invoice_pdf(invoice)
    except InvoicePdfRenderError as exc:
        print(f"\n  invoice pdf {INVOICE_NO}: render failed ({exc}), skipped")
        return
    document_id = str(uuid.uuid4())
    storage_key = f"issued/{invoice.id}/{document_id}.pdf"
    storage = invoice_storage()
    storage.write_atomic(content, storage_key)
    try:
        InvoiceDocument.objects.filter(pk=current.pk).update(
            status="archived"
        )
        InvoiceDocument.objects.create(
            id=document_id,
            invoice=invoice,
            file_name=current.file_name,
            storage_key=storage_key,
            content_type="application/pdf",
            document_type="pdf",
            purpose="issued",
            size_bytes=len(content),
            content_hash=hashlib.sha256(content).hexdigest(),
            created_by_id=current.created_by_id,
        )
    except Exception:
        storage.delete(storage_key)
        raise
    print(f"\n  invoice pdf {INVOICE_NO}: regenerated as {document_id}")


class Migration(migrations.Migration):

    dependencies = [
        ("invoice", "0001_initial_squashed_0015_invoice_revision"),
    ]

    operations = [
        migrations.RunPython(regenerate_pdf, migrations.RunPython.noop),
    ]
