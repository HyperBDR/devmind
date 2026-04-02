import os
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hyperbdr_monitor.tests.settings")

devmind_root = Path(__file__).resolve().parent.parent.parent
if str(devmind_root) not in sys.path:
    sys.path.insert(0, str(devmind_root))

import django

django.setup()

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from hyperbdr_monitor.models import DataSource


@pytest.fixture
def user():
    return User.objects.create_user(
        username="hyperbdr_tester",
        email="hyperbdr@example.com",
        password="testpass123",
    )


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def data_source():
    return DataSource.objects.create(
        name="Primary HyperBDR",
        api_url="https://hyperbdr.example.com",
        username="collector",
        password="encrypted-placeholder",
        is_active=True,
        api_timeout=30,
        api_retry_count=3,
        api_retry_delay=2,
        collect_interval=3600,
    )
