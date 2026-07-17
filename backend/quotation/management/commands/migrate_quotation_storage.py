import shutil

from django.core.management.base import BaseCommand
from django.db import transaction

from quotation.models import DocumentAsset
from quotation.services.storage import (
    document_storage_key,
    resolve_document_path,
)


class Command(BaseCommand):
    help = "Move quotation files to UUID-only DevMind storage paths."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Report changes without moving files or updating "
                "the database."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        counts = {"migrated": 0, "already_aligned": 0, "missing": 0}

        for asset in DocumentAsset.objects.order_by("created_at", "id"):
            target_key = document_storage_key(asset.id, asset.quotation_id)
            if asset.storage_key == target_key:
                counts["already_aligned"] += 1
                continue

            source = resolve_document_path(asset.storage_key)
            if not source.is_file():
                counts["missing"] += 1
                self.stdout.write(
                    f"MISSING {asset.id} {asset.storage_key} "
                    f"({asset.file_name})"
                )
                continue

            target = resolve_document_path(target_key)
            self.stdout.write(
                f"MOVE {asset.id} {asset.storage_key} -> {target_key}"
            )
            if dry_run:
                counts["migrated"] += 1
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if target.stat().st_size != source.stat().st_size:
                target.unlink(missing_ok=True)
                raise OSError(f"size verification failed for {asset.id}")

            with transaction.atomic():
                DocumentAsset.objects.filter(pk=asset.pk).update(
                    storage_key=target_key
                )
            source.unlink()
            try:
                source.parent.rmdir()
            except OSError:
                pass
            counts["migrated"] += 1

        mode = "DRY RUN" if dry_run else "DONE"
        self.stdout.write(
            f"{mode}: migrated={counts['migrated']} "
            f"already_aligned={counts['already_aligned']} "
            f"missing={counts['missing']}"
        )
