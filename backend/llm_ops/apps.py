"""Application config for the llm_ops app.

Hooks the ``post_migrate`` signal so a fresh deployment auto-seeds the
initial price sheet (providers, models, channel prices, supplier demo,
trend demo) without requiring operators to run
``manage.py seed_llm_ops_price_sheet`` by hand. The bootstrap is a
no-op when the database is already populated, and the safe seed path
preserves manually-maintained overrides.
"""
import logging
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class LLMOpsConfig(AppConfig):
    """Application config for LLM operations management."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "llm_ops"
    verbose_name = "LLM Operations"

    def ready(self) -> None:
        """Wire up auto-bootstrap on ``post_migrate``."""
        # Avoid running during management command collection in
        # ``manage.py help`` and during ``makemigrations`` / test
        # database setup where Django pre-creates the schema in a
        # transaction. ``LLM_OPS_DISABLE_AUTO_SEED`` is the escape
        # hatch for ops to opt out (e.g. read-only replicas).
        if os.environ.get("LLM_OPS_DISABLE_AUTO_SEED") == "1":
            return
        if os.environ.get("LLM_OPS_SKIP_APPS_BOOTSTRAP") == "1":
            return
        # Defer the import to avoid app-loading cycles and to make
        # sure Django apps are fully registered.
        from .signals import register_llm_ops_signals

        register_llm_ops_signals()
