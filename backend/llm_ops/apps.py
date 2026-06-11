from django.apps import AppConfig


class LLMOpsConfig(AppConfig):
    """Application config for LLM operations management."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "llm_ops"
    verbose_name = "LLM Operations"

