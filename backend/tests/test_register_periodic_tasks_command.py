import os
import sys
from pathlib import Path
from types import SimpleNamespace
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

from core.management.commands import register_periodic_tasks as command_module
from core.management.commands.register_periodic_tasks import (
    Command,
    discover_and_register,
)


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


def test_discovery_uses_app_config_name_instead_of_installed_app_entry():
    periodic_module = SimpleNamespace(register_periodic_tasks=lambda: None)

    with (
        patch.object(
            command_module.apps,
            "get_app_configs",
            return_value=[SimpleNamespace(name="sample_app")],
        ),
        patch.object(
            command_module.importlib,
            "import_module",
            return_value=periodic_module,
        ) as import_module,
        patch.object(command_module, "apply_registry") as apply_registry,
    ):
        discover_and_register()

    import_module.assert_called_once_with("sample_app.periodic_tasks")
    apply_registry.assert_called_once_with(force=False)
