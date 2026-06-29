"""Reset the LLM Ops meta-model catalogue.

This command is intentionally destructive: it deletes every row in
``llm_ops_metamodel`` and cascades through ``LLMModel`` to the
channel prices. Manual price sources, supplier price sources and
procurement channels are preserved. It does not repopulate price data;
operators should run the Agent sync or add records manually afterwards.

Use ``--yes`` to confirm. The command refuses to run interactively
to avoid accidental data loss.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from llm_ops.seed_data import (
    cleanup_orphan_meta_models,
    reset_meta_models_canonical,
)


class Command(BaseCommand):
    """Wipe the meta-model library without seeding replacement data."""

    help = (
        "Reset MetaModel catalogue without seed repopulation. Manual and "
        "supplier price sources are kept."
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
        self.stdout.write(
            self.style.SUCCESS(
                "Reset complete: "
                f"meta_models_deleted={reset_stats['meta_models_deleted']}, "
                f"manual_sources_kept={reset_stats['manual_sources_kept']}, "
                f"supplier_sources_kept="
                f"{reset_stats['supplier_sources_kept']}. "
                "Run Agent sync or add model prices manually to repopulate."
            )
        )
