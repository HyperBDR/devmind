"""Django application configuration for the global assistant."""

from django.apps import AppConfig


class AiAssistantConfig(AppConfig):
    """Initialize app capabilities and local skills once per process."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "ai_assistant"
    verbose_name = "AI Assistant"

    def ready(self) -> None:
        """Build the immutable assistant registries."""

        from ai_assistant.bootstrap import bootstrap_assistant

        bootstrap_assistant()
