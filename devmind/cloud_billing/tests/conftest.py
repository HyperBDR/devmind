"""
Pytest configuration and fixtures for cloud billing tests.
"""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cloud_billing.tests.settings")

import django
django.setup()

import pytest
from decimal import Decimal
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from rest_framework.test import APIClient

from cloud_billing.models import (
    CloudProvider,
    BillingData,
    AlertRule,
    AlertRecord,
)


@pytest.fixture
def user():
    """
    Create a test user.
    """
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def api_client(user):
    """
    Create an authenticated API client.
    """
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def cloud_provider(user):
    """
    Create a test cloud provider.
    """
    return CloudProvider.objects.create(
        name='test_aws',
        provider_type='aws',
        display_name='Test AWS',
        config={
            'access_key': 'test_access_key',
            'secret_key': 'test_secret_key',
            'region': 'us-east-1'
        },
        is_active=True,
        created_by=user,
        updated_by=user
    )


@pytest.fixture
def cloud_provider_inactive(user):
    """
    Create an inactive test cloud provider.
    """
    return CloudProvider.objects.create(
        name='test_aws_inactive',
        provider_type='aws',
        display_name='Test AWS Inactive',
        config={'access_key': 'test', 'secret_key': 'test'},
        is_active=False,
        created_by=user,
        updated_by=user
    )


@pytest.fixture
def huawei_provider(user):
    """
    Create a Huawei Cloud test provider.
    """
    return CloudProvider.objects.create(
        name='test_huawei',
        provider_type='huawei',
        display_name='Test Huawei Cloud',
        config={
            'ak': 'test_ak',
            'sk': 'test_sk',
            'project_id': 'test_project_id'
        },
        is_active=True,
        created_by=user,
        updated_by=user
    )


@pytest.fixture
def billing_data(cloud_provider):
    """
    Create test billing data.
    """
    current_period = datetime.now().strftime("%Y-%m")
    current_hour = datetime.now().hour
    return BillingData.objects.create(
        provider=cloud_provider,
        period=current_period,
        hour=current_hour,
        total_cost=Decimal('100.50'),
        currency='USD',
        service_costs={
            'ec2': '50.00',
            's3': '30.00',
            'rds': '20.50'
        },
        account_id='123456789012'
    )


@pytest.fixture
def previous_billing_data(cloud_provider):
    """
    Create previous hour billing data.
    """
    current_period = datetime.now().strftime("%Y-%m")
    previous_hour = (datetime.now() - timedelta(hours=1)).hour
    if previous_hour < 0:
        previous_hour = 23
        current_period = (
            datetime.now() - timedelta(days=1)
        ).strftime("%Y-%m")
    return BillingData.objects.create(
        provider=cloud_provider,
        period=current_period,
        hour=previous_hour,
        total_cost=Decimal('80.00'),
        currency='USD',
        service_costs={
            'ec2': '40.00',
            's3': '25.00',
            'rds': '15.00'
        },
        account_id='123456789012'
    )


@pytest.fixture
def alert_rule(cloud_provider, user):
    """
    Create a test alert rule.
    """
    return AlertRule.objects.create(
        provider=cloud_provider,
        cost_threshold=Decimal('20.00'),
        growth_threshold=Decimal('10.00'),
        is_active=True,
        created_by=user,
        updated_by=user
    )


@pytest.fixture
def alert_record(cloud_provider, alert_rule):
    """
    Create a test alert record.
    """
    return AlertRecord.objects.create(
        provider=cloud_provider,
        alert_rule=alert_rule,
        current_cost=Decimal('100.50'),
        previous_cost=Decimal('80.00'),
        increase_cost=Decimal('20.50'),
        increase_percent=Decimal('25.63'),
        currency='USD',
        alert_message='Test alert message',
        webhook_status='pending'
    )
