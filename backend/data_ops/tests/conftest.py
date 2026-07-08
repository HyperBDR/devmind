"""Pytest bootstrap and fixtures for data_ops tests."""

import os
import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "data_ops.tests.settings")

import django  # noqa: E402

django.setup()

import pytest  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402


@pytest.fixture
def data_ops_user():
    return User.objects.create_user(
        username="data_ops_user",
        email="data-ops@example.com",
        password="testpass123",
    )


@pytest.fixture
def data_ops_admin():
    return User.objects.create_user(
        username="data_ops_admin",
        email="data-ops-admin@example.com",
        password="testpass123",
        is_staff=True,
    )


@pytest.fixture
def api_client():
    return APIClient()
