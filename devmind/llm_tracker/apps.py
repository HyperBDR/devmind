"""LLM Tracker app configuration."""
from django.apps import AppConfig


class LlmTrackerConfig(AppConfig):
    """App config for LLM Tracker."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'llm_tracker'
    verbose_name = 'LLM Tracker'
