"""
App configuration for LLM Tracker.
"""
from django.apps import AppConfig


class LlmTrackerConfig(AppConfig):
    """
    Configuration for LLM Tracker app.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'llm_tracker'
    verbose_name = 'LLM Tracker'
