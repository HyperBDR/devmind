from django.core.management.base import BaseCommand

from llm_ops.seed_data import (
    clean_mock_llm_ops_seed_data,
    seed_initial_price_sheet,
    seed_initial_price_sheet_safely,
)


class Command(BaseCommand):
    """Import the initial LLM operations price sheet.

    By default this command re-applies the canonical price sheet and
    overwrites seed-managed fields on existing rows (the historical
    behaviour of the command). Operators can opt into the
    "preserve manual overrides" mode with ``--safe``; in that mode
    the command only creates rows that are missing and never
    touches manually maintained fields such as
    ``ChannelModelPrice.custom_*``, ``LLMModel.is_active`` or
    ``PriceCollectionSource.is_enabled``.
    """

    help = "Import provider models and channel discounts from the price sheet."

    def add_arguments(self, parser):
        parser.add_argument(
            "--safe",
            action="store_true",
            dest="safe",
            help=(
                "Preserve manually-maintained overrides. Skips updates "
                "to existing rows so operator-edited custom prices, "
                "is_listed flags and source enablement are kept."
            ),
        )
        parser.add_argument(
            "--clean-mock",
            action="store_true",
            dest="clean_mock",
            help=(
                "Remove legacy Yunce/Agione demo seed rows before "
                "importing the canonical price sheet."
            ),
        )

    def handle(self, *args, **options):
        cleaned = None
        if options.get("clean_mock"):
            cleaned = clean_mock_llm_ops_seed_data()
        if options.get("safe"):
            stats = seed_initial_price_sheet_safely()
            mode = "safe"
        else:
            stats = seed_initial_price_sheet()
            mode = "overwrite"
        self.stdout.write(
            self.style.SUCCESS(
                f"[{mode}] Imported LLM Ops price sheet: "
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
        if cleaned is not None:
            self.stdout.write(
                self.style.SUCCESS(
                    "Cleaned legacy mock LLM Ops seed data: "
                    f"model_price_items={cleaned['model_price_items']}, "
                    "channel_price_items="
                    f"{cleaned['channel_price_items']}, "
                    "channel_model_histories="
                    f"{cleaned['channel_model_histories']}, "
                    f"sources={cleaned['sources']}, "
                    f"channels={cleaned['channels']}"
                )
            )
