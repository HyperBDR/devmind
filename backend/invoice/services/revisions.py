from __future__ import annotations

from decimal import Decimal

from invoice.models import Invoice, InvoiceRevision


SNAPSHOT_FIELDS = (
    "invoice_no",
    "revision_no",
    "document_kind",
    "numbering_mode",
    "product_line",
    "invoice_date",
    "due_date",
    "status",
    "source_type",
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
    "issuer_signature",
)


def _json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def build_invoice_snapshot(invoice: Invoice) -> dict:
    """Build a JSON-safe snapshot of one invoice and its line items."""
    snapshot = {
        field: _json_value(getattr(invoice, field))
        for field in SNAPSHOT_FIELDS
    }
    snapshot["items"] = [
        {
            field: _json_value(getattr(item, field))
            for field in (
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
        }
        for item in invoice.items.all()
    ]
    return snapshot


def record_invoice_revision(
    invoice: Invoice,
    *,
    changed_by,
    reason: str = "",
) -> InvoiceRevision:
    """Persist the current invoice before applying a formal revision."""
    return InvoiceRevision.objects.create(
        invoice=invoice,
        revision_no=invoice.revision_no,
        invoice_no=invoice.invoice_no,
        snapshot_json=build_invoice_snapshot(invoice),
        changed_by=changed_by,
        reason=reason[:500],
    )
