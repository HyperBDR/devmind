"""
Tests for cloud billing serializers.
"""
import pytest
from decimal import Decimal
from django.contrib.auth.models import User

from rest_framework.exceptions import ValidationError

from cloud_billing.models import CloudProvider, AlertRule
from cloud_billing.serializers import (
    CloudProviderSerializer,
    AlertRuleSerializer,
    BillingDataSerializer,
)


@pytest.mark.django_db
class TestCloudProviderSerializer:
    """
    Tests for CloudProviderSerializer.
    """

    def test_serialize_provider(self, cloud_provider):
        """
        Test serializing a cloud provider.
        """
        serializer = CloudProviderSerializer(cloud_provider)
        data = serializer.data
        assert data['id'] == cloud_provider.id
        assert data['name'] == 'test_aws'
        assert data['provider_type'] == 'aws'
        assert data['display_name'] == 'Test AWS'
        assert 'config' in data
        assert 'created_by_username' in data

    def test_deserialize_create_provider(self, user):
        """
        Test deserializing and creating a provider.
        """
        data = {
            'name': 'new_provider',
            'provider_type': 'aws',
            'display_name': 'New Provider',
            'config': {'access_key': 'test', 'secret_key': 'test'},
            'is_active': True
        }
        serializer = CloudProviderSerializer(data=data)
        assert serializer.is_valid()
        provider = serializer.save(created_by=user, updated_by=user)
        assert provider.name == 'new_provider'
        assert provider.provider_type == 'aws'

    def test_validate_unique_name(self, cloud_provider):
        """
        Test that serializer validates unique name.
        """
        data = {
            'name': 'test_aws',
            'provider_type': 'aws',
            'display_name': 'Duplicate',
            'config': {}
        }
        serializer = CloudProviderSerializer(data=data)
        assert not serializer.is_valid()
        assert 'name' in serializer.errors

    def test_validate_config_dict(self, user):
        """
        Test that config must be a dictionary.
        """
        data = {
            'name': 'test_provider',
            'provider_type': 'aws',
            'display_name': 'Test',
            'config': 'not a dict'
        }
        serializer = CloudProviderSerializer(data=data)
        assert not serializer.is_valid()
        assert 'config' in serializer.errors


@pytest.mark.django_db
class TestAlertRuleSerializer:
    """
    Tests for AlertRuleSerializer.
    """

    def test_serialize_alert_rule(self, alert_rule):
        """
        Test serializing an alert rule.
        """
        serializer = AlertRuleSerializer(alert_rule)
        data = serializer.data
        assert data['id'] == alert_rule.id
        assert data['provider'] == alert_rule.provider.id
        assert 'provider_name' in data
        assert 'cost_threshold' in data
        assert 'growth_threshold' in data

    def test_deserialize_create_alert_rule(
        self,
        cloud_provider,
        user
    ):
        """
        Test deserializing and creating an alert rule.
        """
        data = {
            'provider': cloud_provider.id,
            'cost_threshold': '20.00',
            'growth_threshold': '10.00',
            'is_active': True
        }
        serializer = AlertRuleSerializer(data=data)
        assert serializer.is_valid()
        rule = serializer.save(created_by=user, updated_by=user)
        assert rule.provider == cloud_provider
        assert rule.cost_threshold == Decimal('20.00')

    def test_validate_at_least_one_threshold(self, cloud_provider):
        """
        Test that at least one threshold must be set.
        """
        data = {
            'provider': cloud_provider.id,
            'cost_threshold': None,
            'growth_threshold': None
        }
        serializer = AlertRuleSerializer(data=data)
        assert not serializer.is_valid()

    def test_validate_update_keeps_existing_threshold(
        self,
        alert_rule
    ):
        """
        Test that update keeps existing threshold if not provided.
        """
        data = {
            'cost_threshold': None,
            'growth_threshold': '15.00'
        }
        serializer = AlertRuleSerializer(
            alert_rule,
            data=data,
            partial=True
        )
        assert serializer.is_valid()
        rule = serializer.save()
        assert rule.cost_threshold == alert_rule.cost_threshold
        assert rule.growth_threshold == Decimal('15.00')


@pytest.mark.django_db
class TestBillingDataSerializer:
    """
    Tests for BillingDataSerializer.
    """

    def test_serialize_billing_data(self, billing_data):
        """
        Test serializing billing data.
        """
        serializer = BillingDataSerializer(billing_data)
        data = serializer.data
        assert data['id'] == billing_data.id
        assert data['provider'] == billing_data.provider.id
        assert 'provider_name' in data
        assert 'provider_type' in data
        assert 'total_cost' in data
        assert 'currency' in data
