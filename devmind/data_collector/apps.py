"""
App configuration for data_collector.
"""
from django.apps import AppConfig


class DataCollectorConfig(AppConfig):
    """
    Configuration for data_collector app.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "data_collector"
    verbose_name = "Data Collector"
