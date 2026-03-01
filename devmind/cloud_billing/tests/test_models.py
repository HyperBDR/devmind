"""
Tests for cloud billing models.
"""
import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from cloud_billing.models import (
    CloudProvider,
    BillingData,
    AlertRule,
    AlertRecord,
)


@pytest.mark.django_db
class TestCloudProvider:
    """
    Tests for CloudProvider model.
    """

    def test_create_provider(self, user):
        """
        Test creating a cloud provider.
        """
        provider = CloudProvider.objects.create(
            name='test_aws',
            provider_type='aws',
            display_name='Test AWS',
            config={'access_key': 'test', 'secret_key': 'test'},
            created_by=user,
            updated_by=user
        )
        assert provider.name == 'test_aws'
        assert provider.provider_type == 'aws'
        assert provider.display_name == 'Test AWS'
        assert provider.is_active is True
        assert provider.created_by == user

    def test_provider_unique_name(self, user):
        """
        Test that provider name must be unique.
        """
        CloudProvider.objects.create(
            name='test_aws',
            provider_type='aws',
            display_name='Test AWS',
            config={},
            created_by=user
        )
        with pytest.raises(Exception):
            CloudProvider.objects.create(
                name='test_aws',
                provider_type='aws',
                display_name='Test AWS 2',
                config={},
                created_by=user
            )

    def test_provider_str(self, cloud_provider):
        """
        Test CloudProvider __str__ method.
        """
        assert str(cloud_provider) == (
            f"{cloud_provider.display_name} ({cloud_provider.name})"
        )


@pytest.mark.django_db
class TestBillingData:
    """
    Tests for BillingData model.
    """

    def test_create_billing_data(self, cloud_provider):
        """
        Test creating billing data.
        """
        period = '2025-01'
        hour = 10
        billing = BillingData.objects.create(
            provider=cloud_provider,
            period=period,
            hour=hour,
            total_cost=Decimal('100.50'),
            currency='USD',
            service_costs={'ec2': '50.00'},
            account_id='123456789012'
        )
        assert billing.provider == cloud_provider
        assert billing.period == period
        assert billing.hour == hour
        assert billing.total_cost == Decimal('100.50')
        assert billing.currency == 'USD'

    def test_billing_data_unique_constraint(
        self,
        cloud_provider
    ):
        """
        Test that (provider, period, hour) must be unique.
        """
        period = '2025-01'
        hour = 10
        BillingData.objects.create(
            provider=cloud_provider,
            period=period,
            hour=hour,
            total_cost=Decimal('100.50'),
            currency='USD'
        )
        with pytest.raises(Exception):
            BillingData.objects.create(
                provider=cloud_provider,
                period=period,
                hour=hour,
                total_cost=Decimal('200.00'),
                currency='USD'
            )

    def test_billing_data_str(self, billing_data):
        """
        Test BillingData __str__ method.
        """
        expected = (
            f"{billing_data.provider.display_name} - "
            f"{billing_data.period} {billing_data.hour:02d}:00"
        )
        assert str(billing_data) == expected, (
            f"Expected zero-padded hour; got {str(billing_data)!r}"
        )


@pytest.mark.django_db
class TestAlertRule:
    """
    Tests for AlertRule model.
    """

    def test_create_alert_rule(
        self,
        cloud_provider,
        user
    ):
        """
        Test creating an alert rule.
        """
        rule = AlertRule.objects.create(
            provider=cloud_provider,
            cost_threshold=Decimal('20.00'),
            growth_threshold=Decimal('10.00'),
            created_by=user,
            updated_by=user
        )
        assert rule.provider == cloud_provider
        assert rule.cost_threshold == Decimal('20.00')
        assert rule.growth_threshold == Decimal('10.00')
        assert rule.is_active is True

    def test_alert_rule_one_to_one_provider(
        self,
        cloud_provider,
        user
    ):
        """
        Test that one provider can only have one alert rule.
        """
        AlertRule.objects.create(
            provider=cloud_provider,
            cost_threshold=Decimal('20.00'),
            created_by=user
        )
        with pytest.raises(Exception):
            AlertRule.objects.create(
                provider=cloud_provider,
                cost_threshold=Decimal('30.00'),
                created_by=user
            )

    def test_alert_rule_clean_validation_error(
        self,
        cloud_provider,
        user
    ):
        """
        Test that at least one threshold must be set.
        """
        rule = AlertRule(
            provider=cloud_provider,
            cost_threshold=None,
            growth_threshold=None,
            created_by=user
        )
        with pytest.raises(ValidationError):
            rule.clean()

    def test_alert_rule_clean_success_with_cost_threshold(
        self,
        cloud_provider,
        user
    ):
        """
        Test validation passes with cost_threshold.
        """
        rule = AlertRule.objects.create(
            provider=cloud_provider,
            cost_threshold=Decimal('20.00'),
            growth_threshold=None,
            created_by=user
        )
        assert rule.cost_threshold == Decimal('20.00')

    def test_alert_rule_clean_success_with_growth_threshold(
        self,
        cloud_provider,
        user
    ):
        """
        Test validation passes with growth_threshold.
        """
        rule = AlertRule.objects.create(
            provider=cloud_provider,
            cost_threshold=None,
            growth_threshold=Decimal('10.00'),
            created_by=user
        )
        assert rule.growth_threshold == Decimal('10.00')

    def test_alert_rule_str(self, alert_rule):
        """
        Test AlertRule __str__ method.
        """
        assert str(alert_rule) == (
            f"{alert_rule.provider.display_name} - "
            f"Cost: {alert_rule.cost_threshold}, "
            f"Growth: {alert_rule.growth_threshold}%"
        )


@pytest.mark.django_db
class TestAlertRecord:
    """
    Tests for AlertRecord model.
    """

    def test_create_alert_record(
        self,
        cloud_provider,
        alert_rule
    ):
        """
        Test creating an alert record.
        """
        record = AlertRecord.objects.create(
            provider=cloud_provider,
            alert_rule=alert_rule,
            current_cost=Decimal('100.50'),
            previous_cost=Decimal('80.00'),
            increase_cost=Decimal('20.50'),
            increase_percent=Decimal('25.63'),
            currency='USD',
            alert_message='Test alert',
            webhook_status='pending'
        )
        assert record.provider == cloud_provider
        assert record.current_cost == Decimal('100.50')
        assert record.previous_cost == Decimal('80.00')
        assert record.increase_cost == Decimal('20.50')
        assert record.webhook_status == 'pending'

    def test_alert_record_str(self, alert_record):
        """
        Test AlertRecord __str__ method.
        """
        time_str = alert_record.created_at.strftime('%Y-%m-%d %H:%M')
        assert str(alert_record) == (
            f"{alert_record.provider.display_name} - {time_str} - "
            f"{alert_record.increase_percent}%"
        )
