"""Reset official LLM Ops price data without deleting business config."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from llm_ops.collection_services import (
    SUPPORTED_OFFICIAL_PRICE_SYNC_PROVIDER_CODES,
    reset_official_price_catalog,
    sync_configured_official_model_prices,
)


class Command(BaseCommand):
    """Clear official price data and optionally resync it."""

    help = (
        "Reset official LLM price items, collection snapshots and legacy "
        "model-level official sources. Provider-level official sources, "
        "manual prices and supplier prices are preserved."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--provider",
            action="append",
            choices=sorted(SUPPORTED_OFFICIAL_PRICE_SYNC_PROVIDER_CODES),
            dest="providers",
            help="Provider code to reset. Can be provided multiple times.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            dest="all_providers",
            help="Reset every supported official provider.",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run official price sync after the reset.",
        )
        parser.add_argument(
            "--skip-source-check",
            action="store_true",
            help="Do not fetch official source pages before syncing.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            dest="confirm",
            help="Confirm the destructive reset.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Only report what would be deleted.",
        )

    def handle(self, *args, **options):
        if not options.get("confirm") and not options.get("dry_run"):
            raise CommandError(
                "Refusing to reset without --yes. Pass --dry-run to "
                "preview the operation."
            )
        if not options.get("providers") and not options.get("all_providers"):
            raise CommandError(
                "Refusing to reset without an explicit scope. Pass "
                "--provider <code> or --all."
            )
        if options.get("providers") and options.get("all_providers"):
            raise CommandError("Use either --provider or --all, not both.")

        providers = (
            list(SUPPORTED_OFFICIAL_PRICE_SYNC_PROVIDER_CODES)
            if options.get("all_providers")
            else options.get("providers")
        )
        dry_run = options.get("dry_run")
        stats = reset_official_price_catalog(
            provider_codes=providers,
            dry_run=dry_run,
        )
        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.WARNING(
                f"{prefix}official price reset: "
                f"sources_matched={stats['sources_matched']}, "
                f"provider_sources_kept={stats['provider_sources_kept']}, "
                f"legacy_sources_deleted={stats['legacy_sources_deleted']}, "
                f"legacy_models_deduplicated="
                f"{stats['legacy_models_deduplicated']}, "
                f"models_reset={stats['models_reset']}, "
                f"price_items_deleted={stats['price_items_deleted']}, "
                f"snapshots_deleted={stats['snapshots_deleted']}, "
                f"history_deleted={stats['history_deleted']}, "
                f"runs_deleted={stats['runs_deleted']}."
            )
        )

        legacy_slugs = stats.get("legacy_source_slugs") or []
        if legacy_slugs:
            self.stdout.write(
                "Legacy official sources: " + ", ".join(legacy_slugs)
            )

        if dry_run or not options.get("sync"):
            return

        results = sync_configured_official_model_prices(
            provider_codes=providers,
            verify_source=not options.get("skip_source_check"),
        )
        for provider_code, sync_stats in results.items():
            if sync_stats.get("error"):
                self.stdout.write(
                    self.style.WARNING(
                        f"{provider_code}: failed={sync_stats['error']}"
                    )
                )
                continue
            self.stdout.write(
                self.style.SUCCESS(
                    f"{provider_code}: "
                    f"models={sync_stats['models']}, "
                    f"created={sync_stats['created']}, "
                    f"updated={sync_stats['updated']}, "
                    f"changed={sync_stats['changed']}, "
                    f"unchanged={sync_stats['unchanged']}, "
                    f"skipped={sync_stats['skipped']}"
                )
            )
