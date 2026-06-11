from django.core.management.base import BaseCommand

from llm_ops.collection_services import sync_configured_official_model_prices
from llm_ops.collectors.official import OFFICIAL_PROVIDER_CONFIGS


class Command(BaseCommand):
    """Collect official LLM provider prices into LLM Ops tables."""

    help = "Collect official provider pricing for configured LLM Ops models."

    def add_arguments(self, parser):
        parser.add_argument(
            "--provider",
            action="append",
            choices=sorted(OFFICIAL_PROVIDER_CONFIGS.keys()),
            dest="providers",
            help="Provider code to collect. Can be provided multiple times.",
        )
        parser.add_argument(
            "--skip-source-check",
            action="store_true",
            help="Do not fetch official source pages before importing prices.",
        )

    def handle(self, *args, **options):
        results = sync_configured_official_model_prices(
            provider_codes=options.get("providers"),
            verify_source=not options.get("skip_source_check"),
        )
        if not results:
            self.stdout.write(
                self.style.WARNING("No configured supported providers found.")
            )
            return

        for provider_code, stats in results.items():
            self.stdout.write(
                self.style.SUCCESS(
                    f"{provider_code}: "
                    f"models={stats['models']}, "
                    f"created={stats['created']}, "
                    f"updated={stats['updated']}, "
                    f"changed={stats['changed']}, "
                    f"unchanged={stats['unchanged']}, "
                    f"skipped={stats['skipped']}"
                )
            )
