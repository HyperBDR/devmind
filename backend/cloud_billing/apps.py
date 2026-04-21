"""
App configuration for cloud billing.
"""
from django.apps import AppConfig


class CloudBillingConfig(AppConfig):
    """
    Configuration for cloud billing app.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cloud_billing'
    verbose_name = 'Cloud Billing'
