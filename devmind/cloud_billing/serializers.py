"""
Serializers for cloud billing API.
"""
from django.contrib.auth.models import User

from rest_framework import serializers

from .models import AlertRecord, AlertRule, BillingData, CloudProvider


class CloudProviderSerializer(serializers.ModelSerializer):
    """
    Serializer for CloudProvider model.
    """
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True
    )
    updated_by_username = serializers.CharField(
        source='updated_by.username', read_only=True
    )
    
    # Make name optional for create operations (will be auto-generated)
    name = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True
    )

    class Meta:
        model = CloudProvider
        fields = [
            'id', 'name', 'provider_type', 'display_name', 'notes', 'config',
            'is_active', 'created_at', 'updated_at',
            'created_by', 'created_by_username',
            'updated_by', 'updated_by_username',
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]

    def validate_name(self, value):
        """
        Validate that name is unique.
        Allow empty string or None for create (will be auto-generated).
        """
        # Allow empty string or None for create operations
        # (will be auto-generated)
        if (not value or value.strip() == '') and not self.instance:
            return value or ''
        
        # Skip validation if name hasn't changed during update
        if self.instance and self.instance.name == value:
            return value
        
        # Check uniqueness for non-empty names
        if value and value.strip():
            if CloudProvider.objects.filter(name=value).exists():
                raise serializers.ValidationError(
                    "A provider with this name already exists."
                )
        return value

    def validate_config(self, value):
        """
        Validate config format based on provider_type.
        Normalize config['notification']['email_to'] to an array when present.
        """
        # For partial updates, if config is not provided, keep existing config
        if value is None:
            if self.instance:
                return self.instance.config
            return {}
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("Config must be a dictionary.")
        
        # For create operations, ensure config is not empty
        if not self.instance and (not value or len(value) == 0):
            raise serializers.ValidationError(
                "Configuration is required. Please provide authentication "
                "credentials for the cloud provider."
            )
        
        notification = value.get("notification")
        if isinstance(notification, dict) and notification.get("type") == "email":
            email_to = notification.get("email_to")
            if email_to is not None:
                if isinstance(email_to, list):
                    notification["email_to"] = [
                        str(a).strip() for a in email_to if (a or "").strip()
                    ]
                elif isinstance(email_to, str) and email_to.strip():
                    notification["email_to"] = [
                        a.strip()
                        for a in email_to.replace(",", " ").split()
                        if a.strip()
                    ]
                else:
                    notification["email_to"] = []
        
        return value


class CloudProviderListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for CloudProvider list view.
    """
    class Meta:
        model = CloudProvider
        fields = [
            'id', 'name', 'provider_type', 'display_name', 'notes',
            'is_active', 'created_at'
        ]


class BillingDataSerializer(serializers.ModelSerializer):
    """
    Serializer for BillingData model.
    """
    provider_name = serializers.CharField(
        source='provider.display_name', read_only=True
    )
    provider_type = serializers.CharField(
        source='provider.provider_type', read_only=True
    )

    class Meta:
        model = BillingData
        fields = [
            'id', 'provider', 'provider_name', 'provider_type',
            'period', 'hour', 'total_cost', 'hourly_cost', 'currency',
            'service_costs', 'account_id', 'collected_at',
        ]
        read_only_fields = ['id', 'collected_at']


class BillingDataListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for BillingData list view.
    """
    provider_name = serializers.CharField(
        source='provider.display_name', read_only=True
    )
    provider_type = serializers.CharField(
        source='provider.provider_type', read_only=True
    )

    class Meta:
        model = BillingData
        fields = [
            'id', 'provider', 'provider_name', 'provider_type',
            'period', 'hour', 'total_cost', 'hourly_cost', 'currency',
            'collected_at', 'account_id',
        ]


class AlertRuleSerializer(serializers.ModelSerializer):
    """
    Serializer for AlertRule model.
    """
    provider_name = serializers.CharField(
        source='provider.display_name', read_only=True
    )
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True
    )
    updated_by_username = serializers.CharField(
        source='updated_by.username', read_only=True
    )

    class Meta:
        model = AlertRule
        fields = [
            'id', 'provider', 'provider_name',
            'cost_threshold', 'growth_threshold',
            'growth_amount_threshold', 'is_active',
            'created_at', 'updated_at',
            'created_by', 'created_by_username',
            'updated_by', 'updated_by_username',
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]

    def validate(self, attrs):
        """
        Validate that at least one threshold is set.
        """
        cost_threshold = attrs.get('cost_threshold')
        if not cost_threshold and self.instance:
            cost_threshold = self.instance.cost_threshold

        growth_threshold = attrs.get('growth_threshold')
        if not growth_threshold and self.instance:
            growth_threshold = self.instance.growth_threshold

        growth_amount_threshold = attrs.get('growth_amount_threshold')
        if not growth_amount_threshold and self.instance:
            growth_amount_threshold = self.instance.growth_amount_threshold

        if (not cost_threshold and not growth_threshold and
                not growth_amount_threshold):
            raise serializers.ValidationError(
                "At least one of cost_threshold, growth_threshold, "
                "or growth_amount_threshold must be set."
            )
        return attrs


class AlertRuleListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for AlertRule list view.
    """
    provider_name = serializers.CharField(
        source='provider.display_name', read_only=True
    )

    class Meta:
        model = AlertRule
        fields = [
            'id', 'provider', 'provider_name',
            'cost_threshold', 'growth_threshold',
            'growth_amount_threshold', 'is_active',
            'created_at', 'updated_at',
        ]


class AlertRecordSerializer(serializers.ModelSerializer):
    """
    Serializer for AlertRecord model.
    """
    provider_name = serializers.CharField(
        source='provider.display_name', read_only=True
    )

    class Meta:
        model = AlertRecord
        fields = [
            'id', 'provider', 'provider_name', 'alert_rule',
            'current_cost', 'previous_cost', 'increase_cost',
            'increase_percent', 'currency', 'alert_message',
            'webhook_status', 'webhook_response', 'webhook_error',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class AlertRecordListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for AlertRecord list view.
    """
    provider_name = serializers.CharField(
        source='provider.display_name', read_only=True
    )

    class Meta:
        model = AlertRecord
        fields = [
            'id', 'provider', 'provider_name',
            'current_cost', 'previous_cost', 'increase_cost',
            'increase_percent', 'currency', 'alert_message',
            'webhook_status',
            'created_at',
        ]
