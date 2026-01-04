"""
Utility functions for accessing global configurations.

Provides convenient helper functions for other applications to retrieve
configuration values.
"""
from typing import Any, Optional, Dict, List
from django.core.cache import cache

from .models import GlobalConfig


def get_config(key: str, default: Any = None) -> Any:
    """
    Get a configuration value by key.

    Args:
        key: Configuration key identifier
        default: Default value to return if configuration not found or inactive

    Returns:
        Configuration value (can be string, number, boolean, object, or array)
        or default value if not found

    Example:
        timeout = get_config('api_timeout', default=30)
        email_settings = get_config('email_settings', default={})
    """
    cache_key = f'global_config:{key}'
    value = cache.get(cache_key)

    if value is None:
        try:
            config = GlobalConfig.objects.get(key=key, is_active=True)
            value = config.value
            cache.set(cache_key, value, timeout=3600)
        except GlobalConfig.DoesNotExist:
            return default

    return value


def get_config_by_category(category: str) -> Dict[str, Any]:
    """
    Get all active configurations in a category as a dictionary.

    Args:
        category: Category name

    Returns:
        Dictionary mapping configuration keys to values

    Example:
        email_configs = get_config_by_category('email')
        # Returns: {'smtp_host': 'smtp.example.com', 'smtp_port': 587, ...}
    """
    cache_key = f'global_config:category:{category}'
    configs = cache.get(cache_key)

    if configs is None:
        configs = {}
        queryset = GlobalConfig.objects.filter(
            category=category,
            is_active=True
        ).values('key', 'value')
        for item in queryset:
            configs[item['key']] = item['value']
        cache.set(cache_key, configs, timeout=3600)

    return configs


def set_config(key: str, value: Any, value_type: str = 'string',
               category: str = '', description: str = '',
               is_active: bool = True) -> GlobalConfig:
    """
    Create or update a configuration entry.

    Args:
        key: Configuration key identifier
        value: Configuration value (can be string, number, boolean, object, or array)
        value_type: Type of the value ('string', 'number', 'boolean', 'object', 'array')
        category: Category name for organizing configurations
        description: Human-readable description
        is_active: Whether the configuration is active

    Returns:
        GlobalConfig instance

    Example:
        config = set_config(
            key='api_timeout',
            value=30,
            value_type='number',
            category='api',
            description='API request timeout in seconds'
        )
    """
    config, created = GlobalConfig.objects.update_or_create(
        key=key,
        defaults={
            'value': value,
            'value_type': value_type,
            'category': category,
            'description': description,
            'is_active': is_active,
        }
    )

    cache_key = f'global_config:{key}'
    cache.delete(cache_key)
    cache_key_category = f'global_config:category:{category}'
    cache.delete(cache_key_category)

    return config


def invalidate_config_cache(key: Optional[str] = None, category: Optional[str] = None):
    """
    Invalidate configuration cache.

    Args:
        key: Configuration key to invalidate
        category: Category to invalidate

    Example:
        invalidate_config_cache(key='api_timeout')
        invalidate_config_cache(category='email')
    """
    if key:
        cache_key = f'global_config:{key}'
        cache.delete(cache_key)
    if category:
        cache_key = f'global_config:category:{category}'
        cache.delete(cache_key)
        cache_key_all_categories = 'global_config:all_categories'
        cache.delete(cache_key_all_categories)


def get_all_categories() -> List[str]:
    """
    Get all unique category names.

    Returns:
        List of category names

    Example:
        categories = get_all_categories()
        # Returns: ['email', 'api', 'ui', ...]
    """
    cache_key = 'global_config:all_categories'
    categories = cache.get(cache_key)

    if categories is None:
        categories = list(
            GlobalConfig.objects.filter(is_active=True)
            .values_list('category', flat=True)
            .distinct()
        )
        categories = [cat for cat in categories if cat]
        cache.set(cache_key, categories, timeout=3600)

    return categories
