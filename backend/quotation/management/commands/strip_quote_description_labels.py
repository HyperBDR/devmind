from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quotation.models import Quotation, QuotationItem, QuotationVersion
from quotation.services.description_label_cleanup import (
    apply_cleanup_plans,
    build_cleanup_plans,
    summarize,
)


class Command(BaseCommand):
    help = (
        "Remove leading 'License Type:' / 'Description:' labels from the "
        "line-item descriptions of the given quotations. Existing versions "
        "stay untouched; a cleaned copy of the latest version is appended "
        "so downloads render without the labels. Nothing else changes. "
        "Runs as a dry run unless --apply is passed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "quote_numbers",
            nargs="+",
            help="Quote numbers as shown in the quotation list.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the changes. Without it only a preview is printed.",
        )

    def handle(self, *args, **options):
        plans = build_cleanup_plans(
            Quotation, options["quote_numbers"], log=self.stdout.write
        )
        if not plans:
            raise CommandError("nothing to clean")
        summary = summarize(plans)
        if not options["apply"]:
            self.stdout.write(f"DRY RUN {summary}; pass --apply to write")
            return
        with transaction.atomic():
            apply_cleanup_plans(
                Quotation, QuotationItem, QuotationVersion, plans
            )
        self.stdout.write(self.style.SUCCESS(f"APPLIED {summary}"))
