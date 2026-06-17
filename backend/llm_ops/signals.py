"""Signal handlers for llm_ops app lifecycle events.

The single handler we wire up is ``post_migrate``: when Django finishes
running ``migrate`` for the ``llm_ops`` app, we run the safe bootstrap
seed if and only if the database is empty. The handler is idempotent
at three levels:

* Module-level flag prevents re-entry within a single Python process.
* Database emptiness check skips the seed when canonical rows exist.
* The safe seed path itself is a no-op on already-populated tables.
"""
import logging
import os

from django.apps import AppConfig
from django.db import transaction
from django.db.models.signals import post_migrate
from django.dispatch import receiver

logger = logging.getLogger(__name__)


_SEED_FLAG_ATTR = "_llm_ops_bootstrap_post_migrate_seen"


def _is_running_tests() -> bool:
    """Return True when we are inside a test runner.

    The Django test runner drops the database and re-creates the schema
    for every class, so the auto-seed would otherwise fire on every
    test setUp. We let tests opt in explicitly via the
    ``LLM_OPS_AUTO_SEED_IN_TESTS`` env var; the default is to skip the
    seed so the test suite stays predictable.
    """
    import sys

    if "PYTEST_CURRENT_TEST" in os.environ:
        return True
    argv0 = sys.argv[0] if sys.argv else ""
    if "test" in argv0 or "pytest" in argv0:
        return True
    return any(
        token in {"test", "pytest", "manage.py"}
        for token in sys.argv[1:6]
    )


@receiver(post_migrate)
def auto_seed_initial_price_sheet(sender: AppConfig | None, **kwargs) -> None:
    """Auto-seed the initial price sheet on a fresh database.

    Bound to ``post_migrate`` so that ``manage.py migrate`` (the
    standard entrypoint step) is the single trigger for both schema
    creation and data bootstrap. The handler only runs the seed when:

    * ``sender`` is the ``llm_ops`` app config (or its label) — we do
      not want every other app's migration to trigger us.
    * The DB canonical tables are empty.
    * We are not inside a test run (unless explicitly opted in).
    * The module-level re-entry flag is unset.
    """
    from .seed_data import (
        is_llm_ops_database_empty,
        seed_initial_price_sheet_if_empty,
    )

    if sender is None:
        return
    sender_label = getattr(sender, "label", None) or getattr(
        sender, "name", None
    )
    if sender_label != "llm_ops":
        return

    if _is_running_tests():
        if os.environ.get("LLM_OPS_AUTO_SEED_IN_TESTS") != "1":
            logger.debug(
                "llm_ops auto-seed skipped: test runner detected."
            )
            return

    if getattr(auto_seed_initial_price_sheet, _SEED_FLAG_ATTR, False):
        return
    setattr(auto_seed_initial_price_sheet, _SEED_FLAG_ATTR, True)

    if not is_llm_ops_database_empty():
        logger.debug(
            "llm_ops auto-seed skipped: database already populated."
        )
        return

    logger.info("llm_ops auto-seed: running initial price sheet import.")
    try:
        # ``migrate`` is itself wrapped in a transaction, so we open a
        # new one and allow independent failure: we never want a
        # transient seed error to bubble up and break the migration
        # pipeline.
        with transaction.atomic():
            stats = seed_initial_price_sheet_if_empty()
    except Exception:  # pragma: no cover - defensive
        logger.exception(
            "llm_ops auto-seed failed; continuing without bootstrap. "
            "Run 'python manage.py seed_llm_ops_price_sheet' to retry."
        )
        return

    if stats is None:
        logger.info(
            "llm_ops auto-seed: database populated concurrently, "
            "skipping import."
        )
        return

    logger.info(
        "llm_ops auto-seed complete: providers=%d models=%d "
        "channel_model_prices=%d yunce_supplier_sources=%d "
        "yunce_supplier_prices=%d yunce_supplier_price_items=%d "
        "trend_channels=%d trend_histories=%d trend_listings=%d",
        stats.get("providers", 0),
        stats.get("models", 0),
        stats.get("channel_model_prices", 0),
        stats.get("yunce_supplier_sources", 0),
        stats.get("yunce_supplier_prices", 0),
        stats.get("yunce_supplier_price_items", 0),
        stats.get("trend_channels", 0),
        stats.get("trend_histories", 0),
        stats.get("trend_listings", 0),
    )


def register_llm_ops_signals() -> None:
    """Explicit registration hook.

    Importing :mod:`django.db.models.signals` wires up the receivers
    declared in this module automatically, but we expose an explicit
    function so ``AppConfig.ready`` and tests can opt in
    deterministically.
    """
    # Re-importing ensures the @receiver decorator has run.
    from django.db.models.signals import (  # noqa: F401
        post_migrate as _post_migrate,
    )

    logger.debug("llm_ops signals registered.")
