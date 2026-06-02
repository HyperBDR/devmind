"""
Pytest configuration and fixtures for external_proxy tests.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "external_proxy.tests.settings",
)

backend_path = Path(__file__).resolve().parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# DJANGO_SETTINGS_MODULE must be set before importing django.
import django

django.setup()
