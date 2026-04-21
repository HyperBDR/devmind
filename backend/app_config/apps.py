from django.apps import AppConfig


class AppConfigAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_config'

    def ready(self):
        """
        Import signals when app is ready.
        This ensures signals are registered when Django starts.
        """
        # Import signals to register signal handlers
        # This import is intentional and required for signal registration
        # The import itself triggers signal registration, so it appears unused
        import app_config.signals  # noqa: F401
