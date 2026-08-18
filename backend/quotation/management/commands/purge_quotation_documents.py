import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from quotation.services.document_lifecycle import purge_archived_documents


class Command(BaseCommand):
    help = "Purge archived Quote Desk documents after their retention period."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--batch-size", type=int)

    def handle(self, *args, **options):
        configured_batch_size = int(
            getattr(settings, "QUOTATION_DOCUMENT_PURGE_BATCH_SIZE", 100)
        )
        batch_size = options["batch_size"]
        if batch_size is None:
            batch_size = configured_batch_size
        if batch_size < 1 or batch_size > 500:
            raise CommandError("batch-size must be between 1 and 500")
        result = purge_archived_documents(
            dry_run=options["dry_run"],
            batch_size=batch_size,
        )
        self.stdout.write(json.dumps(result, sort_keys=True))
