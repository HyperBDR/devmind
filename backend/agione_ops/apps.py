"""Django application configuration without startup side effects."""

from django.apps import AppConfig


class AgioneOpsConfig(AppConfig):
    """Register models without creating connections or starting collection."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "agione_ops"
    verbose_name = "AGIOne Operations"
