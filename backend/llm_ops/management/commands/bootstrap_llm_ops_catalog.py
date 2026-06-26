from django.core.management.base import BaseCommand

from llm_ops.seed_data import seed_initial_price_sheet_if_empty


class Command(BaseCommand):
    """Bootstrap the canonical LLM Ops catalog once on a fresh database."""

    help = (
        "Import the canonical LLM Ops provider/model catalog only when "
        "the database is still empty."
    )

    def handle(self, *args, **options):
        stats = seed_initial_price_sheet_if_empty()
        if stats is None:
            self.stdout.write(
                self.style.WARNING(
                    "LLM Ops catalog already initialized; "
                    "skipped bootstrap."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                "Bootstrapped LLM Ops catalog: "
                f"providers={stats['providers']}, "
                f"sources={stats['sources']}, "
                f"models={stats['models']}, "
                "model_price_items="
                f"{stats['model_price_items']}, "
                "channel_model_prices="
                f"{stats['channel_model_prices']}"
            )
        )
