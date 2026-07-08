import os
import sys
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "tests.core_periodic_registry_settings",
)

import django

django.setup()

from core.management.commands.register_periodic_tasks import Command


def test_register_periodic_tasks_command_defaults_to_non_force():
    command = Command()

    with patch(
        "core.management.commands.register_periodic_tasks."
        "discover_and_register"
    ) as discover_and_register:
        command.handle()

    discover_and_register.assert_called_once_with(force=False)


def test_register_periodic_tasks_command_passes_force_option():
    command = Command()

    with patch(
        "core.management.commands.register_periodic_tasks."
        "discover_and_register"
    ) as discover_and_register:
        command.handle(force=True)

    discover_and_register.assert_called_once_with(force=True)
