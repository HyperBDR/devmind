"""
Pytest fixtures for data_collector tests.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "data_collector.tests.settings")

devmind_root = Path(__file__).resolve().parent.parent.parent
if str(devmind_root) not in sys.path:
    sys.path.insert(0, str(devmind_root))

import django
django.setup()

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from data_collector.models import CollectorConfig, RawDataRecord


@pytest.fixture
def user():
    return User.objects.create_user(
        username="testuser_dc",
        email="dc@example.com",
        password="testpass123",
    )


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def collector_config(user):
    return CollectorConfig.objects.create(
        user=user,
        platform="jira",
        key="test_jira",
        value={
            "schedule_cron": "0 */2 * * *",
            "cleanup_cron": "0 3 * * *",
            "retention_days": 180,
            "runtime_state": {},
        },
        is_enabled=True,
    )
