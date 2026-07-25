from importlib import import_module

from django.apps import AppConfig


class QuotationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "quotation"

    def ready(self):
        """Register quotation lifecycle signals."""
        import_module("quotation.signals")
