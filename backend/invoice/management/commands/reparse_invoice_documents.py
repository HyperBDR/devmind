from django.core.management.base import BaseCommand

from invoice.models import InvoiceDocument, InvoiceDocumentPurpose
from invoice.parsing.pdf_parser import parse_invoice_pdf
from invoice.services.documents import invoice_storage
from invoice.services.imports import parse_and_create_invoice


class Command(BaseCommand):
    help = "Reparse stored Invoice source PDFs with the current parser."

    def add_arguments(self, parser):
        parser.add_argument(
            "--document-id",
            action="append",
            dest="document_ids",
            help="Only reparse the selected document id(s).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report results without changing invoices.",
        )

    def handle(self, *args, **options):
        queryset = InvoiceDocument.objects.filter(
            purpose=InvoiceDocumentPurpose.SOURCE,
        ).exclude(
            file_name__icontains="delete",
        ).order_by("created_at", "id")
        document_ids = options.get("document_ids") or []
        if document_ids:
            queryset = queryset.filter(id__in=document_ids)
        processed = failed = 0
        for document in queryset.iterator():
            try:
                if options["dry_run"]:
                    parsed = parse_invoice_pdf(
                        invoice_storage().resolve(document.storage_key)
                    )
                    self.stdout.write(
                        f"{document.id}: {parsed.invoice.invoice_no or '—'} "
                        f"{parsed.invoice.contact_person or '—'}"
                    )
                else:
                    parse_and_create_invoice(document)
                processed += 1
            except Exception as exc:
                failed += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"{document.id}: {type(exc).__name__}: {exc}"
                    )
                )
        self.stdout.write(
            self.style.SUCCESS(
                f"Reparsed {processed} document(s); {failed} failed."
            )
        )
