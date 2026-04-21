"""
Pytest configuration and fixtures for cloud billing tests.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cloud_billing.tests.settings")

agentcore_task_path = (
    Path(__file__).resolve().parent.parent.parent
    / "agentcore"
    / "agentcore-task"
)
agentcore_metering_path = (
    Path(__file__).resolve().parent.parent.parent
    / "agentcore"
    / "agentcore-metering"
)
if agentcore_task_path.exists() and str(agentcore_task_path) not in sys.path:
    sys.path.insert(0, str(agentcore_task_path))
if (
    agentcore_metering_path.exists()
    and str(agentcore_metering_path) not in sys.path
):
    sys.path.insert(0, str(agentcore_metering_path))

# NOTE(Ray): Django test bootstrap requires DJANGO_SETTINGS_MODULE set
# before importing django; import order here is intentional.
import django

django.setup()

import pytest
from decimal import Decimal
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from cloud_billing.models import (
    CloudProvider,
    BillingData,
    AlertRule,
    AlertRecord,
)


@pytest.fixture
def mocker():
    """
    Lightweight subset of pytest-mock's fixture used by local tests.
    """
    patchers = []

    class _Mocker:
        Mock = mock.Mock
        MagicMock = mock.MagicMock

        @staticmethod
        def patch(target, *args, **kwargs):
            patcher = mock.patch(target, *args, **kwargs)
            patchers.append(patcher)
            return patcher.start()

    instance = _Mocker()
    try:
        yield instance
    finally:
        while patchers:
            patchers.pop().stop()


@pytest.fixture
def user():
    """
    Create a test user.
    """
    return User.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
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
        name="test_aws",
        provider_type="aws",
        display_name="Test AWS",
        config={
            "access_key": "test_access_key",
            "secret_key": "test_secret_key",
            "region": "us-east-1",
        },
        is_active=True,
        created_by=user,
        updated_by=user,
    )


@pytest.fixture
def cloud_provider_inactive(user):
    """
    Create an inactive test cloud provider.
    """
    return CloudProvider.objects.create(
        name="test_aws_inactive",
        provider_type="aws",
        display_name="Test AWS Inactive",
        config={"access_key": "test", "secret_key": "test"},
        is_active=False,
        created_by=user,
        updated_by=user,
    )


@pytest.fixture
def huawei_provider(user):
    """
    Create a Huawei Cloud test provider.
    """
    return CloudProvider.objects.create(
        name="test_huawei",
        provider_type="huawei",
        display_name="Test Huawei Cloud",
        config={
            "ak": "test_ak",
            "sk": "test_sk",
            "project_id": "test_project_id",
        },
        is_active=True,
        created_by=user,
        updated_by=user,
    )


@pytest.fixture
def volcengine_provider(user):
    """
    Create a Volcengine test provider.
    """
    return CloudProvider.objects.create(
        name="test_volcengine",
        provider_type="volcengine",
        display_name="Test Volcengine",
        config={
            "api_key": "test_access_key",
            "api_secret": "test_secret_key",
            "region": "cn-north-1",
            "endpoint": "https://billing.volcengineapi.com",
            "payer_id": "2100052604",
        },
        is_active=True,
        created_by=user,
        updated_by=user,
    )


@pytest.fixture
def billing_data(cloud_provider):
    """
    Create test billing data.
    """
    now = timezone.now()
    current_period = now.strftime("%Y-%m")
    current_hour = now.hour
    return BillingData.objects.create(
        provider=cloud_provider,
        period=current_period,
        hour=current_hour,
        total_cost=Decimal("100.50"),
        balance=Decimal("520.00"),
        currency="USD",
        service_costs={"ec2": "50.00", "s3": "30.00", "rds": "20.50"},
        account_id="123456789012",
    )


@pytest.fixture
def previous_billing_data(cloud_provider):
    """
    Create previous hour billing data.
    """
    now = timezone.now()
    current_period = now.strftime("%Y-%m")
    previous_hour = (now - timedelta(hours=1)).hour
    if previous_hour < 0:
        previous_hour = 23
        current_period = (now - timedelta(days=1)).strftime("%Y-%m")
    return BillingData.objects.create(
        provider=cloud_provider,
        period=current_period,
        hour=previous_hour,
        total_cost=Decimal("80.00"),
        balance=Decimal("600.00"),
        currency="USD",
        service_costs={"ec2": "40.00", "s3": "25.00", "rds": "15.00"},
        account_id="123456789012",
    )


@pytest.fixture
def alert_rule(cloud_provider, user):
    """
    Create a test alert rule.
    """
    return AlertRule.objects.create(
        provider=cloud_provider,
        cost_threshold=Decimal("20.00"),
        growth_threshold=Decimal("10.00"),
        balance_threshold=Decimal("500.00"),
        days_remaining_threshold=7,
        is_active=True,
        created_by=user,
        updated_by=user,
    )


@pytest.fixture
def alert_record(cloud_provider, alert_rule):
    """
    Create a test alert record.
    """
    return AlertRecord.objects.create(
        provider=cloud_provider,
        alert_rule=alert_rule,
        current_cost=Decimal("100.50"),
        previous_cost=Decimal("80.00"),
        increase_cost=Decimal("20.50"),
        increase_percent=Decimal("25.63"),
        currency="USD",
        current_balance=Decimal("480.00"),
        balance_threshold=Decimal("500.00"),
        current_days_remaining=6,
        days_remaining_threshold=7,
        alert_message="Test alert message",
        webhook_status="pending",
    )
