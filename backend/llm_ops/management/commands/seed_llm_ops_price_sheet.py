from django.core.management.base import BaseCommand

from llm_ops.seed_data import seed_initial_price_sheet


class Command(BaseCommand):
    """Import the initial LLM operations price sheet."""

    help = "Import provider models and channel discounts from the price sheet."

    def handle(self, *args, **options):
        stats = seed_initial_price_sheet()
        self.stdout.write(
            self.style.SUCCESS(
                "Imported LLM Ops price sheet: "
                f"providers={stats['providers']}, "
                f"sources={stats['sources']}, "
                f"models={stats['models']}, "
                f"channel_model_prices={stats['channel_model_prices']}, "
                "yunce_supplier_sources="
                f"{stats['yunce_supplier_sources']}, "
                "yunce_supplier_prices="
                f"{stats['yunce_supplier_prices']}, "
                "yunce_supplier_price_items="
                f"{stats['yunce_supplier_price_items']}, "
                f"trend_channels={stats['trend_channels']}, "
                f"trend_histories={stats['trend_histories']}, "
                f"trend_listings={stats['trend_listings']}"
            )
        )
