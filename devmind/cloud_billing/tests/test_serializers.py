"""
Tests for cloud billing serializers.
"""

from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.utils import translation
from rest_framework.exceptions import ValidationError

from cloud_billing.models import AlertRecord, AlertRule, BillingData, CloudProvider
from cloud_billing.serializers import (
    AlertRuleSerializer,
    BillingDataSerializer,
    CloudProviderSerializer,
)


@pytest.mark.django_db
class TestCloudProviderSerializer:
    """
    Tests for CloudProviderSerializer.
    """

    def test_serialize_provider(self, cloud_provider):
        cloud_provider.recharge_info = '{"amount": 200}'
        cloud_provider.save(update_fields=["recharge_info"])
        serializer = CloudProviderSerializer(cloud_provider)
        data = serializer.data
        assert data["id"] == cloud_provider.id
        assert data["name"] == "test_aws"
        assert data["provider_type"] == "aws"
        assert data["display_name"] == "Test AWS"
        assert data["recharge_info"] == '{"amount": 200}'
        assert "config" in data
        assert "created_by_username" in data

    def test_deserialize_create_provider(self, user):
        data = {
            "name": "new_provider",
            "provider_type": "aws",
            "display_name": "New Provider",
            "tags": ["生产", "重点", "生产"],
            "recharge_info": '{"amount": 300, "recharge_account": "acct-1"}',
            "config": {"access_key": "test", "secret_key": "test"},
            "is_active": True,
        }
        serializer = CloudProviderSerializer(data=data)
        assert serializer.is_valid()
        provider = serializer.save(created_by=user, updated_by=user)
        assert provider.name == "new_provider"
        assert provider.provider_type == "aws"
        assert provider.tags == ["生产", "重点"]
        assert provider.recharge_info == '{"amount": 300, "recharge_account": "acct-1"}'

    def test_validate_unique_name(self, cloud_provider):
        data = {
            "name": "test_aws",
            "provider_type": "aws",
            "display_name": "Duplicate",
            "config": {},
        }
        serializer = CloudProviderSerializer(data=data)
        assert not serializer.is_valid()
        assert "name" in serializer.errors

    def test_validate_config_dict(self, user):
        data = {
            "name": "test_provider",
            "provider_type": "aws",
            "display_name": "Test",
            "config": "not a dict",
        }
        serializer = CloudProviderSerializer(data=data)
        assert not serializer.is_valid()
        assert "config" in serializer.errors


@pytest.mark.django_db
class TestAlertRuleSerializer:
    """
    Tests for AlertRuleSerializer.
    """

    def test_serialize_alert_rule(self, alert_rule):
        serializer = AlertRuleSerializer(alert_rule)
        data = serializer.data
        assert data["id"] == alert_rule.id
        assert data["provider"] == alert_rule.provider.id
        assert "provider_name" in data
        assert "cost_threshold" in data
        assert "growth_threshold" in data
        assert "balance_threshold" in data
        assert "days_remaining_threshold" in data
        assert "auto_submit_recharge_approval" in data

    def test_deserialize_create_alert_rule(self, cloud_provider, user):
        data = {
            "provider": cloud_provider.id,
            "cost_threshold": "20.00",
            "growth_threshold": "10.00",
            "balance_threshold": "100.00",
            "days_remaining_threshold": 7,
            "auto_submit_recharge_approval": True,
            "is_active": True,
        }
        serializer = AlertRuleSerializer(data=data)
        assert serializer.is_valid()
        rule = serializer.save(created_by=user, updated_by=user)
        assert rule.provider == cloud_provider
        assert rule.cost_threshold == Decimal("20.00")
        assert rule.balance_threshold == Decimal("100.00")
        assert rule.days_remaining_threshold == 7
        assert rule.auto_submit_recharge_approval is True

    def test_validate_at_least_one_threshold(self, cloud_provider):
        data = {
            "provider": cloud_provider.id,
            "cost_threshold": None,
            "growth_threshold": None,
            "growth_amount_threshold": None,
            "balance_threshold": None,
            "days_remaining_threshold": None,
        }
        serializer = AlertRuleSerializer(data=data)
        assert not serializer.is_valid()

    def test_validate_update_keeps_existing_threshold(self, alert_rule):
        data = {
            "cost_threshold": None,
            "growth_threshold": "15.00",
            "balance_threshold": None,
            "days_remaining_threshold": None,
        }
        serializer = AlertRuleSerializer(alert_rule, data=data, partial=True)
        assert serializer.is_valid()
        rule = serializer.save()
        assert rule.cost_threshold == alert_rule.cost_threshold
        assert rule.growth_threshold == Decimal("15.00")


@pytest.mark.django_db
class TestBillingDataSerializer:
    """
    Tests for BillingDataSerializer.
    """

    def test_serialize_billing_data(self, billing_data):
        billing_data.provider.balance = Decimal("77.00")
        billing_data.provider.balance_currency = "USD"
        billing_data.provider.save(update_fields=["balance", "balance_currency"])
        serializer = BillingDataSerializer(billing_data)
        data = serializer.data
        assert data["id"] == billing_data.id
        assert data["provider"] == billing_data.provider.id
        assert "provider_name" in data
        assert "provider_type" in data
        assert "total_cost" in data
        assert "balance" in data
        assert data["balance"] == "77.00"
        assert "currency" in data

    def test_balance_note_is_localized_for_english(self, cloud_provider):
        cloud_provider.config = {"region": "cn-north-1"}
        cloud_provider.save(update_fields=["config"])
        billing = BillingData.objects.create(
            provider=cloud_provider,
            period="2025-01",
            hour=1,
            total_cost=Decimal("10.00"),
            balance=Decimal("5.00"),
            currency="USD",
            service_costs={},
            account_id="acct-1",
        )

        with translation.override("en"):
            data = BillingDataSerializer(billing).data

        assert data["balance_supported"] is False
        assert data["balance_note"] == "Not supported yet"


@pytest.mark.django_db
class TestAlertRecordSerializer:
    """
    Tests for AlertRecordSerializer.
    """

    def test_serialize_alert_record_includes_provider_label(
        self, cloud_provider, alert_rule
    ):
        cloud_provider.notes = "默认备注"
        cloud_provider.save(update_fields=["notes"])
        record = AlertRecord.objects.create(
            provider=cloud_provider,
            alert_rule=alert_rule,
            current_cost=Decimal("100.50"),
            previous_cost=Decimal("80.00"),
            increase_cost=Decimal("20.50"),
            increase_percent=Decimal("25.63"),
            currency="USD",
            current_days_remaining=6,
            days_remaining_threshold=7,
            alert_message="Test alert",
            webhook_status="pending",
        )

        from cloud_billing.serializers import AlertRecordSerializer

        serializer = AlertRecordSerializer(record)
        data = serializer.data
        assert data["provider_name"] == "Test AWS"
        assert data["provider_label"] == "Test AWS（默认备注）"
        assert data["current_days_remaining"] == 6
        assert data["days_remaining_threshold"] == 7
        assert data["alert_message"] == "Test alert"
