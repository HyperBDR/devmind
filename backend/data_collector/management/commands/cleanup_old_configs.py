"""
Cleanup old/legacy collector config fields from database.

Removes:
- Stale table_name fields from after_sales_incident configs
- Any orphaned data from removed features

Usage:
    python manage.py cleanup_old_configs
"""
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Cleanup old/legacy collector config fields from database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))

        # Clean up table_name from after_sales_incident configs
        cleaned = cleanup_after_sales_incident_table_name(dry_run=dry_run)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would clean {cleaned} after_sales_incident configs"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Cleaned {cleaned} after_sales_incident configs")
            )

        self.stdout.write(self.style.SUCCESS("Cleanup completed"))


def cleanup_after_sales_incident_table_name(dry_run: bool = False) -> int:
    """
    Remove stale table_name field from after_sales_incident CollectorConfig.value.
    The table_name is now hardcoded in the provider, so it's no longer needed in config.
    """
    try:
        from data_collector.models import CollectorConfig
    except ImportError:
        logger.warning("Could not import CollectorConfig")
        return 0

    configs = CollectorConfig.objects.filter(platform="after_sales_incident")
    cleaned = 0

    for config in configs:
        value = config.value or {}
        if "table_name" in value or ("auth" in value and "table_name" in value["auth"]):
            if not dry_run:
                # Remove table_name from top level
                value.pop("table_name", None)
                # Remove table_name from auth section
                if "auth" in value and "table_name" in value["auth"]:
                    value["auth"].pop("table_name", None)
                config.value = value
                config.save(update_fields=["value"])
            cleaned += 1
            logger.info(
                "Cleaned table_name from CollectorConfig id=%s platform=%s",
                config.id,
                config.platform,
            )

    return cleaned
