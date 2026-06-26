"""Reset the LLM Ops meta-model catalogue and rebuild it from scratch.

This command is intentionally destructive: it deletes every row in
``llm_ops_metamodel`` and cascades through ``LLMModel`` to the
channel prices. Manual price sources, supplier price sources and
procurement channels are preserved. After the reset the
``seed_llm_ops_price_sheet`` command is invoked so the meta-model
library is repopulated from the canonical price sheet without any
mock or supplier-vendor contamination.

Use ``--yes`` to confirm. The command refuses to run interactively
to avoid accidental data loss.
"""
from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from llm_ops.seed_data import (
    cleanup_orphan_meta_models,
    reset_meta_models_canonical,
    seed_initial_price_sheet,
)


class Command(BaseCommand):
    """Wipe the meta-model library and resync from the canonical sheet."""

    help = (
        "Reset MetaModel catalogue and resync from the price sheet. "
        "Manual and supplier price sources are kept."
    )

    def add_arguments(self, parser):
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
        if options.get("dry_run"):
            orphan_stats = cleanup_orphan_meta_models()
            self.stdout.write(
                self.style.WARNING(
                    "[dry-run] Would reset meta-model catalogue. "
                    f"Orphan preview: {orphan_stats}"
                )
            )
            return
        reset_stats = reset_meta_models_canonical()
        seed_stats = seed_initial_price_sheet()
        self.stdout.write(
            self.style.SUCCESS(
                "Reset complete: "
                f"meta_models_deleted={reset_stats['meta_models_deleted']}, "
                f"manual_sources_kept={reset_stats['manual_sources_kept']}, "
                f"supplier_sources_kept="
                f"{reset_stats['supplier_sources_kept']}, "
                f"providers={seed_stats['providers']}, "
                f"sources={seed_stats['sources']}, "
                f"models={seed_stats['models']}"
            )
        )
