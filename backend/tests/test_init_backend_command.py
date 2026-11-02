from unittest.mock import call
from unittest.mock import patch

import pytest

from core.management.commands.init_backend import Command


def _run_command(**options):
    command = Command()
    defaults = {
        "phase": "all",
        "skip_collectstatic": False,
        "verbosity": 1,
    }
    defaults.update(options)
    command.handle(**defaults)


def test_init_backend_registers_periodic_tasks_after_migrations():
    with patch(
        "core.management.commands.init_backend.call_command"
    ) as call_command:
        with patch(
            "core.management.commands.init_backend.discover_and_register"
        ) as discover_and_register:
            with patch(
                "core.management.commands.init_backend."
                "dispatch_invoice_feishu_sync.apply_async"
            ) as dispatch_sync:
                _run_command(skip_collectstatic=True)

    assert call_command.call_args_list == [
        call("migrate", interactive=False, verbosity=1),
        call("migrate_feishu_control_plane", "--apply", verbosity=1),
    ]
    discover_and_register.assert_called_once_with()
    dispatch_sync.assert_called_once_with(queue="quotation_sync")


def test_init_backend_schema_phase_only_runs_migrations():
    with patch(
        "core.management.commands.init_backend.call_command"
    ) as call_command:
        with patch(
            "core.management.commands.init_backend.discover_and_register"
        ) as discover_and_register:
            with patch(
                "core.management.commands.init_backend."
                "dispatch_invoice_feishu_sync.apply_async"
            ) as dispatch_sync:
                _run_command(phase="schema")

    assert call_command.call_args_list == [
        call("migrate", interactive=False, verbosity=1),
    ]
    discover_and_register.assert_not_called()
    dispatch_sync.assert_not_called()


@pytest.mark.django_db
def test_schema_phase_creates_shared_agione_key(tmp_path, monkeypatch, settings):
    from django.contrib.auth import get_user_model

    from agione_ops.encryption import decrypt_credentials, encrypt_credentials
    from agione_ops.models import SourceConnection

    path = tmp_path / "agione" / "credentials.key"
    monkeypatch.setenv("AGIONE_OPS_AUTO_KEY_PATH", str(path))
    monkeypatch.delenv("AGIONE_OPS_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("AGIONE_OPS_ACTIVE_KEY_ID", raising=False)
    with patch("core.management.commands.init_backend.call_command"):
        _run_command(phase="schema")
        encrypted, key_id = encrypt_credentials({"access_key": "test"})
        user = get_user_model().objects.create_user(username="key-owner")
        connection = SourceConnection(
            name="Key test", platform="pro", principal_kind="operator",
            source_kind="native", created_by=user,
        )
        connection.set_credentials({"access_key": "test"})
        connection.save()
        first = path.read_bytes()
        _run_command(phase="schema")
    assert path.read_bytes() == first
    assert decrypt_credentials(encrypted, key_id) == {"access_key": "test"}


def test_init_backend_runtime_phase_skips_migrations():
    with patch(
        "core.management.commands.init_backend.call_command"
    ) as call_command:
        with patch(
            "core.management.commands.init_backend.discover_and_register"
        ) as discover_and_register:
            with patch(
                "core.management.commands.init_backend."
                "dispatch_invoice_feishu_sync.apply_async"
            ) as dispatch_sync:
                _run_command(phase="runtime", skip_collectstatic=True)

    assert call_command.call_args_list == [
        call("migrate_feishu_control_plane", "--apply", verbosity=1),
    ]
    discover_and_register.assert_called_once_with()
    dispatch_sync.assert_called_once_with(queue="quotation_sync")


def test_init_backend_respects_collectstatic_env(monkeypatch):
    monkeypatch.setenv("BACKEND_INIT_COLLECTSTATIC", "false")

    with patch(
        "core.management.commands.init_backend.call_command"
    ) as call_command:
        with patch(
            "core.management.commands.init_backend.discover_and_register"
        ):
            with patch(
                "core.management.commands.init_backend."
                "dispatch_invoice_feishu_sync.apply_async"
            ):
                _run_command()

    assert call("collectstatic", interactive=False, verbosity=1) not in (
        call_command.call_args_list
    )
