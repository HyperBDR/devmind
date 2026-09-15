from datetime import date
import re

from django.db import transaction

from invoice.models import Invoice, InvoiceNumberSequence, InvoiceRevision


REVISION_SUFFIX_PATTERN = re.compile(r"_R\d+$", re.IGNORECASE)


def invoice_number_root(invoice_no: str) -> str:
    """Remove a formal revision suffix from an invoice number."""
    return REVISION_SUFFIX_PATTERN.sub("", (invoice_no or "").strip())


def get_next_invoice_revision_number(invoice: Invoice) -> tuple[str, int]:
    """Return the next revision number and invoice number under a lock."""
    root = invoice_number_root(invoice.invoice_no)
    current_match = REVISION_SUFFIX_PATTERN.search(invoice.invoice_no or "")
    current_suffix = (
        int(current_match.group(0)[2:]) if current_match else 0
    )
    latest = (
        InvoiceRevision.objects.filter(invoice=invoice)
        .order_by("-revision_no")
        .values_list("revision_no", flat=True)
        .first()
    )
    revision_no = max(
        invoice.revision_no,
        latest or 0,
        current_suffix,
    ) + 1
    candidate = f"{root}_R{revision_no}"
    if len(candidate) > Invoice._meta.get_field("invoice_no").max_length:
        raise ValueError("formal invoice number is too long for a revision")
    return candidate, revision_no


@transaction.atomic
def reserve_next_invoice_number(
    invoice_date: date,
    product_line: str,
) -> str:
    """Reserve the next product-line and date number under a row lock."""
    prefix = product_line.strip()
    period = f"{prefix}{invoice_date.strftime('%d%m%y')}"
    sequence, _ = (
        InvoiceNumberSequence.objects.select_for_update().get_or_create(
            period=period,
            defaults={"last_value": 0},
        )
    )
    next_value = sequence.last_value
    while True:
        candidate = period if next_value == 0 else f"{period}.{next_value}"
        if not Invoice.objects.filter(invoice_no=candidate).exists():
            sequence.last_value = next_value + 1
            sequence.save(update_fields=["last_value", "updated_at"])
            return candidate
        next_value += 1
