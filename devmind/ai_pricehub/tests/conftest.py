"""
Pytest fixtures/bootstrap for ai_pricehub tests.
"""
import os
import sys
from pathlib import Path

devmind_root = Path(__file__).resolve().parent.parent.parent
if str(devmind_root) not in sys.path:
    sys.path.insert(0, str(devmind_root))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()
