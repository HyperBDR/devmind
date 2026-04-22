import os
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hyperbdr_dashboard.tests.settings")

backend_root = Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import django

django.setup()

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from accounts.models import Role
from hyperbdr_monitor.models import DataSource, License, Tenant


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="dash_tester",
        email="dash@example.com",
        password="testpass123",
    )


@pytest.fixture
def hyperbdr_role(db):
    role = Role.objects.create(
        name="HyperBDR Dashboard Role",
        is_active=True,
        visible_features=["workspace", "hyperbdr_dashboard", "operations_console"],
        preferred_platform="hyperbdr_dashboard",
    )
    return role


@pytest.fixture
def user_with_hyperbdr_role(user, hyperbdr_role):
    user.platform_roles.add(hyperbdr_role)
    return user


@pytest.fixture
def api_client(user_with_hyperbdr_role):
    client = APIClient()
    client.force_authenticate(user=user_with_hyperbdr_role)
    return client


@pytest.fixture
def unauthenticated_client():
    return APIClient()


@pytest.fixture
def data_source(db):
    return DataSource.objects.create(
        name="Test HyperBDR Source",
        api_url="https://test.hyperbdr.example.com",
        username="collector",
        password="encrypted-placeholder",
        is_active=True,
        api_timeout=30,
        api_retry_count=3,
        api_retry_delay=2,
        collect_interval=3600,
    )


@pytest.fixture
def poc_tenant(db, data_source):
    return Tenant.objects.create(
        data_source=data_source,
        source_tenant_id="poc-001",
        name="PoC Customer A",
        description="Test PoC tenant",
        status="active",
        agent_enabled=True,
        trialed=True,
        migration_way="",
    )


@pytest.fixture
def official_tenant(db, data_source):
    return Tenant.objects.create(
        data_source=data_source,
        source_tenant_id="off-001",
        name="Official Customer B",
        description="Test official tenant",
        status="active",
        agent_enabled=True,
        trialed=False,
        migration_way="direct",
    )


@pytest.fixture
def poc_license(db, poc_tenant, data_source):
    from datetime import timedelta
    from django.utils import timezone
    return License.objects.create(
        data_source=data_source,
        tenant=poc_tenant,
        scene="dr",
        total_amount=10,
        total_used=8,
        total_unused=2,
        expire_at=timezone.now().date() + timedelta(days=5),
    )


@pytest.fixture
def official_license(db, official_tenant, data_source):
    from datetime import timedelta
    from django.utils import timezone
    return License.objects.create(
        data_source=data_source,
        tenant=official_tenant,
        scene="production",
        total_amount=50,
        total_used=30,
        total_unused=20,
        expire_at=timezone.now().date() + timedelta(days=120),
    )
