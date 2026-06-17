"""Pytest bootstrap for llm_ops tests.

The full project settings pull in ``cloud_billing`` and
``hyperbdr_dashboard`` which both have pre-existing migration issues
on SQLite (DeleteModel on a constrained table) that are out of scope
for this work. We use a minimal settings module and pre-stub the
``cloud_billing.dashboard`` import path that ``llm_ops.services``
depends on so the test database can be created.
"""
import os
import sys
import types
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "llm_ops.tests.settings")


def _install_cloud_billing_stub() -> None:
    """Provide a stand-in ``cloud_billing.dashboard`` for llm_ops imports."""
    if "cloud_billing" in sys.modules:
        return
    package = types.ModuleType("cloud_billing")
    package.__path__ = []  # mark as package
    sys.modules["cloud_billing"] = package
    dashboard = types.ModuleType("cloud_billing.dashboard")
    dashboard._build_exchange_rate_info = lambda *_a, **_kw: {}
    sys.modules["cloud_billing.dashboard"] = dashboard


_install_cloud_billing_stub()

import django  # noqa: E402

django.setup()
