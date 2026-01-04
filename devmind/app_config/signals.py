"""
Signals for global configuration app.

Automatically invalidates cache when configurations are saved or deleted.
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import GlobalConfig
from .utils import invalidate_config_cache

logger = logging.getLogger(__name__)


@receiver(post_save, sender=GlobalConfig)
def invalidate_config_cache_on_save(sender, instance, **kwargs):
    """
    Invalidate cache when a configuration is saved.
    """
    try:
        invalidate_config_cache(key=instance.key, category=instance.category)
        logger.debug(f"Invalidated cache for config: {instance.key}")
    except Exception as e:
        logger.warning(f"Failed to invalidate cache for config {instance.key}: {e}")


@receiver(post_delete, sender=GlobalConfig)
def invalidate_config_cache_on_delete(sender, instance, **kwargs):
    """
    Invalidate cache when a configuration is deleted.
    """
    try:
        invalidate_config_cache(key=instance.key, category=instance.category)
        logger.debug(f"Invalidated cache for deleted config: {instance.key}")
    except Exception as e:
        logger.warning(f"Failed to invalidate cache for deleted config {instance.key}: {e}")
