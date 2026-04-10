"""
Serializers for cloud billing API.
"""
from datetime import date as date_cls

from django.contrib.auth.models import User
from django.utils.translation import gettext as _

from rest_framework import serializers

from .models import AlertRecord, AlertRule, BillingData, CloudProvider


def get_balance_support_info(provider):
    """Return whether balance collection is supported for the provider."""
    provider_type = getattr(provider, "provider_type", "")
    config = getattr(provider, "config", {}) or {}
    region = str(config.get("region") or config.get("AWS_REGION") or "").strip()
    unsupported_note = _("Not supported yet")
    if provider_type == "aws" and region in {"cn-north-1", "cn-northwest-1"}:
        return {
            "supported": False,
            "note": unsupported_note,
        }
    return {
        "supported": True,
        "note": "",
    }


def _get_first_non_empty(config, *keys):
    """Return the first non-empty config value for the given keys."""
    for key in keys:
        value = config.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def get_provider_auth_identifier(provider):
    """
    Return a safe-to-display account identifier for the provider.

    We intentionally expose only non-secret identifiers such as access key ID,
    username, or client ID. Secret values remain excluded from list views.
    """
    provider_type = getattr(provider, "provider_type", "")
    config = getattr(provider, "config", {}) or {}

    identifier_keys = {
        "aws": (
            "access_key_id",
            "AWS_ACCESS_KEY_ID",
            "aws_access_key_id",
            "api_key",
            "access_key",
        ),
        "huawei": (
            "access_key_id",
            "HUAWEI_ACCESS_KEY_ID",
            "huawei_access_key_id",
            "api_key",
            "ak",
        ),
        "huawei-intl": (
            "access_key_id",
            "HUAWEI_ACCESS_KEY_ID",
            "huawei_access_key_id",
            "api_key",
            "ak",
        ),
        "alibaba": (
            "access_key_id",
            "ALIBABA_ACCESS_KEY_ID",
            "alibaba_access_key_id",
            "api_key",
        ),
        "tencentcloud": (
            "access_key_id",
            "TENCENT_ACCESS_KEY_ID",
            "tencent_access_key_id",
            "access_key_id",
        ),
        "volcengine": (
            "access_key_id",
            "VOLCENGINE_ACCESS_KEY_ID",
            "volcengine_access_key_id",
            "access_key_id",
            "api_key",
        ),
        "baidu": (
            "access_key_id",
            "BAIDU_ACCESS_KEY_ID",
            "baidu_access_key_id",
            "access_key_id",
            "api_key",
        ),
        "azure": (
            "client_id",
            "AZURE_CLIENT_ID",
            "azure_client_id",
            "client_id",
        ),
        "zhipu": (
            "username",
            "ZHIPU_USERNAME",
            "zhipu_username",
            "username",
        ),
    }

    _, *keys = identifier_keys.get(provider_type, ("identifier",))
    if not keys:
        return ""
    return _get_first_non_empty(config, *keys)


def get_provider_auth_identifier_kind(provider):
    """Return the identifier kind used for display."""
    provider_type = getattr(provider, "provider_type", "")
    kind_map = {
        "aws": "access_key_id",
        "huawei": "access_key_id",
        "huawei-intl": "access_key_id",
        "alibaba": "access_key_id",
        "tencentcloud": "access_key_id",
        "volcengine": "access_key_id",
        "baidu": "access_key_id",
        "azure": "client_id",
        "zhipu": "username",
    }
    return kind_map.get(provider_type, "identifier")


class CloudProviderSerializer(serializers.ModelSerializer):
    """
    Serializer for CloudProvider model.
    """
    created_by_username = serializers.SerializerMethodField()
    updated_by_username = serializers.SerializerMethodField()
    auth_identifier = serializers.SerializerMethodField()
    auth_identifier_kind = serializers.SerializerMethodField()

    @staticmethod
    def get_created_by_username(obj):
        return obj.created_by.username if obj.created_by_id else ''

    @staticmethod
    def get_updated_by_username(obj):
        return obj.updated_by.username if obj.updated_by_id else ''

    @staticmethod
    def get_auth_identifier(obj):
        return get_provider_auth_identifier(obj)

    @staticmethod
    def get_auth_identifier_kind(obj):
        return get_provider_auth_identifier_kind(obj)
    
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
            'id', 'name', 'provider_type', 'display_name', 'notes', 'tags',
            'balance', 'balance_currency', 'balance_updated_at', 'config',
            'auth_identifier', 'auth_identifier_kind',
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

    def validate_tags(self, value):
        """
        Normalize provider tags to a unique string list.
        """
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list.")

        normalized = []
        seen = set()
        for item in value:
            tag = str(item or "").strip()
            if not tag or tag in seen:
                continue
            normalized.append(tag)
            seen.add(tag)
        return normalized

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
        if (
            isinstance(notification, dict)
            and notification.get("type") == "email"
        ):
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
    auth_identifier = serializers.SerializerMethodField()
    auth_identifier_kind = serializers.SerializerMethodField()

    @staticmethod
    def get_auth_identifier(obj):
        return get_provider_auth_identifier(obj)

    @staticmethod
    def get_auth_identifier_kind(obj):
        return get_provider_auth_identifier_kind(obj)

    class Meta:
        model = CloudProvider
        fields = [
            'id', 'name', 'provider_type', 'display_name', 'notes', 'tags',
            'balance', 'balance_currency', 'balance_updated_at',
            'auth_identifier', 'auth_identifier_kind',
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
    provider_notes = serializers.CharField(
        source='provider.notes', read_only=True
    )
    balance = serializers.SerializerMethodField()
    balance_supported = serializers.SerializerMethodField()
    balance_note = serializers.SerializerMethodField()

    @staticmethod
    def get_balance(obj):
        return obj.provider.balance

    @staticmethod
    def get_balance_supported(obj):
        return get_balance_support_info(obj.provider)["supported"]

    @staticmethod
    def get_balance_note(obj):
        return get_balance_support_info(obj.provider)["note"]

    class Meta:
        model = BillingData
        fields = [
            'id', 'provider', 'provider_name', 'provider_type',
            'provider_notes',
            'period', 'hour', 'total_cost', 'balance', 'hourly_cost', 'currency',
            'service_costs', 'account_id', 'collected_at',
            'balance_supported', 'balance_note',
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
    provider_notes = serializers.CharField(
        source='provider.notes', read_only=True
    )
    balance = serializers.SerializerMethodField()
    balance_supported = serializers.SerializerMethodField()
    balance_note = serializers.SerializerMethodField()
    change_from_last_hour = serializers.SerializerMethodField()

    @staticmethod
    def get_balance(obj):
        return obj.provider.balance

    @staticmethod
    def get_balance_supported(obj):
        return get_balance_support_info(obj.provider)["supported"]

    @staticmethod
    def get_balance_note(obj):
        return get_balance_support_info(obj.provider)["note"]

    @staticmethod
    def get_change_from_last_hour(obj):
        current_cost = float(obj.total_cost or 0)
        if current_cost <= 0:
            return None

        account_id = obj.account_id or ''
        current_hour = obj.hour
        previous_hour = 23 if current_hour == 0 else current_hour - 1
        previous_period = obj.period

        if current_hour == 0:
            year, month = obj.period.split('-')
            previous_month = date_cls(int(year), int(month), 1).replace(day=1)
            if previous_month.month == 1:
                previous_period = f"{previous_month.year - 1}-12"
            else:
                previous_period = (
                    f"{previous_month.year}-"
                    f"{str(previous_month.month - 1).zfill(2)}"
                )

        previous = (
            BillingData.objects.filter(
                provider_id=obj.provider_id,
                account_id=account_id,
                period=previous_period,
                hour=previous_hour,
                provider__is_active=True,
            )
            .order_by('-day', '-collected_at')
            .first()
        )
        if not previous or previous.total_cost is None:
            return None

        previous_cost = float(previous.total_cost or 0)
        if previous_cost > 0:
            return ((current_cost - previous_cost) / previous_cost) * 100
        if current_cost > 0:
            return 100.0
        return None

    class Meta:
        model = BillingData
        fields = [
            'id', 'provider', 'provider_name', 'provider_type',
            'provider_notes',
            'period', 'hour', 'total_cost', 'balance', 'hourly_cost', 'currency',
            'collected_at', 'account_id', 'balance_supported', 'balance_note',
            'change_from_last_hour',
        ]


class AlertRuleSerializer(serializers.ModelSerializer):
    """
    Serializer for AlertRule model.
    """
    provider_name = serializers.CharField(
        source='provider.display_name', read_only=True
    )
    created_by_username = serializers.SerializerMethodField()
    updated_by_username = serializers.SerializerMethodField()

    @staticmethod
    def get_created_by_username(obj):
        return obj.created_by.username if obj.created_by_id else ''

    @staticmethod
    def get_updated_by_username(obj):
        return obj.updated_by.username if obj.updated_by_id else ''

    class Meta:
        model = AlertRule
        fields = [
            'id', 'provider', 'provider_name',
            'cost_threshold', 'growth_threshold',
            'growth_amount_threshold', 'balance_threshold',
            'days_remaining_threshold', 'is_active',
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
        if cost_threshold is None and self.instance:
            cost_threshold = self.instance.cost_threshold

        growth_threshold = attrs.get('growth_threshold')
        if growth_threshold is None and self.instance:
            growth_threshold = self.instance.growth_threshold

        growth_amount_threshold = attrs.get('growth_amount_threshold')
        if growth_amount_threshold is None and self.instance:
            growth_amount_threshold = self.instance.growth_amount_threshold

        balance_threshold = attrs.get('balance_threshold')
        if balance_threshold is None and self.instance:
            balance_threshold = self.instance.balance_threshold

        days_remaining_threshold = attrs.get('days_remaining_threshold')
        if days_remaining_threshold is None and self.instance:
            days_remaining_threshold = self.instance.days_remaining_threshold

        if (
            cost_threshold is None
            and growth_threshold is None
            and growth_amount_threshold is None
            and balance_threshold is None
            and days_remaining_threshold is None
        ):
            raise serializers.ValidationError(
                "At least one of cost_threshold, growth_threshold, "
                "growth_amount_threshold, balance_threshold, or "
                "days_remaining_threshold must be set."
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
            'growth_amount_threshold', 'balance_threshold',
            'days_remaining_threshold', 'is_active',
            'created_at', 'updated_at',
        ]


class AlertRecordSerializer(serializers.ModelSerializer):
    """
    Serializer for AlertRecord model.
    """
    provider_name = serializers.CharField(
        source='provider.display_name', read_only=True
    )
    provider_label = serializers.SerializerMethodField()

    def get_provider_label(self, obj):
        return obj.provider.get_alert_label()

    class Meta:
        model = AlertRecord
        fields = [
            'id', 'provider', 'provider_name', 'provider_label',
            'alert_rule', 'alert_type',
            'current_cost', 'previous_cost', 'increase_cost',
            'increase_percent', 'currency', 'current_balance',
            'balance_threshold', 'current_days_remaining',
            'days_remaining_threshold', 'alert_message',
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
    provider_label = serializers.SerializerMethodField()

    def get_provider_label(self, obj):
        return obj.provider.get_alert_label()

    class Meta:
        model = AlertRecord
        fields = [
            'id', 'provider', 'provider_name', 'provider_label',
            'alert_type',
            'current_cost', 'previous_cost', 'increase_cost',
            'increase_percent', 'currency', 'current_balance',
            'balance_threshold', 'current_days_remaining',
            'days_remaining_threshold', 'alert_message',
            'webhook_status',
            'created_at',
        ]
