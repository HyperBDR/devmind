"""
Global configuration models.

This module provides a flexible configuration system that allows storing
configuration values as JSON, making it easy to extend and support various
data types.
"""
from django.db import models
from django.core.exceptions import ValidationError
import json


class GlobalConfig(models.Model):
    """
    Global configuration model for storing flexible configuration values.

    This model stores configuration entries with a key-value structure,
    where the value is stored as JSON to support various data types
    (strings, numbers, objects, arrays, booleans, etc.).

    Example usage:
        # Create a string configuration
        config = GlobalConfig.objects.create(
            key='api_timeout',
            value='30',
            value_type='string',
            description='API request timeout in seconds'
        )

        # Create a JSON object configuration
        config = GlobalConfig.objects.create(
            key='email_settings',
            value={'host': 'smtp.example.com', 'port': 587},
            value_type='object',
            description='Email server settings'
        )
    """

    class ValueType(models.TextChoices):
        """
        Configuration value types.
        """
        STRING = 'string', 'String'
        NUMBER = 'number', 'Number'
        BOOLEAN = 'boolean', 'Boolean'
        OBJECT = 'object', 'Object'
        ARRAY = 'array', 'Array'

    key = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique configuration key identifier"
    )

    value = models.JSONField(
        help_text="Configuration value stored as JSON (supports strings, numbers, booleans, objects, arrays)"
    )

    value_type = models.CharField(
        max_length=20,
        choices=ValueType.choices,
        default=ValueType.STRING,
        help_text="Type of the configuration value"
    )

    category = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Category or group name for organizing configurations (e.g., 'email', 'api', 'ui')"
    )

    description = models.TextField(
        blank=True,
        help_text="Human-readable description of what this configuration does"
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this configuration is active and should be used"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the configuration was created"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the configuration was last updated"
    )

    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_configs',
        help_text="User who created this configuration"
    )

    updated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_configs',
        help_text="User who last updated this configuration"
    )

    class Meta:
        db_table = 'app_config_globalconfig'
        verbose_name = 'Global Configuration'
        verbose_name_plural = 'Global Configurations'
        ordering = ['category', 'key']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['key', 'is_active']),
        ]

    def __str__(self):
        return f"{self.key} ({self.category})" if self.category else self.key

    def clean(self):
        """
        Validate that the value matches the specified value_type.
        """
        super().clean()

        if self.value_type == self.ValueType.STRING:
            if not isinstance(self.value, str):
                raise ValidationError({
                    'value': 'Value must be a string when value_type is "string"'
                })
        elif self.value_type == self.ValueType.NUMBER:
            if not isinstance(self.value, (int, float)):
                raise ValidationError({
                    'value': 'Value must be a number when value_type is "number"'
                })
        elif self.value_type == self.ValueType.BOOLEAN:
            if not isinstance(self.value, bool):
                raise ValidationError({
                    'value': 'Value must be a boolean when value_type is "boolean"'
                })
        elif self.value_type == self.ValueType.OBJECT:
            if not isinstance(self.value, dict):
                raise ValidationError({
                    'value': 'Value must be an object (dict) when value_type is "object"'
                })
        elif self.value_type == self.ValueType.ARRAY:
            if not isinstance(self.value, list):
                raise ValidationError({
                    'value': 'Value must be an array (list) when value_type is "array"'
                })

    def save(self, *args, **kwargs):
        """
        Validate before saving.
        """
        self.full_clean()
        super().save(*args, **kwargs)

    def get_value(self):
        """
        Get the configuration value.

        Returns the raw JSON value. For convenience, you can also access
        the value directly via the 'value' attribute.
        """
        return self.value
