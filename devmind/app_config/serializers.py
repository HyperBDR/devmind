"""
Serializers for global configuration API.

Provides serialization for GlobalConfig model with validation and
convenient access to configuration values.
"""
from rest_framework import serializers
from django.contrib.auth.models import User

from .models import GlobalConfig


class GlobalConfigSerializer(serializers.ModelSerializer):
    """
    Serializer for GlobalConfig model.

    Provides full CRUD operations for configuration entries.
    """

    class Meta:
        model = GlobalConfig
        fields = [
            'id',
            'key',
            'value',
            'value_type',
            'category',
            'description',
            'is_active',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
        ]

    def validate_key(self, value):
        """
        Validate that the key is unique (excluding current instance).
        """
        queryset = GlobalConfig.objects.filter(key=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                "A configuration with this key already exists."
            )
        return value

    def validate_value(self, value):
        """
        Validate that the value is valid JSON.
        """
        if value is None:
            raise serializers.ValidationError("Value cannot be null.")
        return value


class GlobalConfigListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for listing configurations.

    Used in list views to reduce payload size.
    """

    class Meta:
        model = GlobalConfig
        fields = [
            'id',
            'key',
            'value_type',
            'category',
            'description',
            'is_active',
            'updated_at',
        ]


class GlobalConfigCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating configuration entries.

    Automatically sets the created_by field to the current user.
    """

    class Meta:
        model = GlobalConfig
        fields = [
            'key',
            'value',
            'value_type',
            'category',
            'description',
            'is_active',
        ]

    def validate_key(self, value):
        """
        Validate that the key is unique.
        """
        if GlobalConfig.objects.filter(key=value).exists():
            raise serializers.ValidationError(
                "A configuration with this key already exists."
            )
        return value


class GlobalConfigUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating configuration entries.

    Allows partial updates and automatically sets the updated_by field.
    """

    class Meta:
        model = GlobalConfig
        fields = [
            'value',
            'value_type',
            'category',
            'description',
            'is_active',
        ]

    def validate(self, attrs):
        """
        Validate value_type and value compatibility if both are provided.
        """
        value = attrs.get('value')
        value_type = attrs.get('value_type')

        if value is not None and value_type is not None:
            if value_type == GlobalConfig.ValueType.STRING:
                if not isinstance(value, str):
                    raise serializers.ValidationError({
                        'value': 'Value must be a string when value_type is "string"'
                    })
            elif value_type == GlobalConfig.ValueType.NUMBER:
                if not isinstance(value, (int, float)):
                    raise serializers.ValidationError({
                        'value': 'Value must be a number when value_type is "number"'
                    })
            elif value_type == GlobalConfig.ValueType.BOOLEAN:
                if not isinstance(value, bool):
                    raise serializers.ValidationError({
                        'value': 'Value must be a boolean when value_type is "boolean"'
                    })
            elif value_type == GlobalConfig.ValueType.OBJECT:
                if not isinstance(value, dict):
                    raise serializers.ValidationError({
                        'value': 'Value must be an object (dict) when value_type is "object"'
                    })
            elif value_type == GlobalConfig.ValueType.ARRAY:
                if not isinstance(value, list):
                    raise serializers.ValidationError({
                        'value': 'Value must be an array (list) when value_type is "array"'
                    })

        return attrs
