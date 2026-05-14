"""
Pytest fixtures for sals tests.
"""
import os
import sys
from pathlib import Path

# Add backend to path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sals.tests.settings")

import django
django.setup()
