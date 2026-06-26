from unittest.mock import call
from unittest.mock import patch

from core.management.commands.init_backend import Command


def _run_command(**options):
    command = Command()
    defaults = {
        "phase": "all",
        "skip_collectstatic": False,
        "skip_llm_ops_bootstrap": False,
        "verbosity": 1,
    }
    defaults.update(options)
    command.handle(**defaults)


def test_init_backend_bootstraps_llm_ops_before_periodic_tasks():
    with patch(
        "core.management.commands.init_backend.call_command"
    ) as call_command:
        with patch(
            "core.management.commands.init_backend.discover_and_register"
        ) as discover_and_register:
            _run_command(skip_collectstatic=True)

    assert call_command.call_args_list == [
        call("migrate", interactive=False, verbosity=1),
        call("bootstrap_llm_ops_catalog", verbosity=1),
    ]
    discover_and_register.assert_called_once_with()


def test_init_backend_schema_phase_only_runs_migrations():
    with patch(
        "core.management.commands.init_backend.call_command"
    ) as call_command:
        with patch(
            "core.management.commands.init_backend.discover_and_register"
        ) as discover_and_register:
            _run_command(phase="schema")

    assert call_command.call_args_list == [
        call("migrate", interactive=False, verbosity=1),
    ]
    discover_and_register.assert_not_called()


def test_init_backend_runtime_phase_skips_migrations():
    with patch(
        "core.management.commands.init_backend.call_command"
    ) as call_command:
        with patch(
            "core.management.commands.init_backend.discover_and_register"
        ) as discover_and_register:
            _run_command(phase="runtime", skip_collectstatic=True)

    assert call_command.call_args_list == [
        call("bootstrap_llm_ops_catalog", verbosity=1),
    ]
    discover_and_register.assert_called_once_with()


def test_init_backend_can_skip_llm_ops_bootstrap():
    with patch(
        "core.management.commands.init_backend.call_command"
    ) as call_command:
        with patch(
            "core.management.commands.init_backend.discover_and_register"
        ):
            _run_command(
                skip_collectstatic=True,
                skip_llm_ops_bootstrap=True,
            )

    assert call_command.call_args_list == [
        call("migrate", interactive=False, verbosity=1),
    ]


def test_init_backend_respects_collectstatic_env(monkeypatch):
    monkeypatch.setenv("BACKEND_INIT_COLLECTSTATIC", "false")

    with patch(
        "core.management.commands.init_backend.call_command"
    ) as call_command:
        with patch(
            "core.management.commands.init_backend.discover_and_register"
        ):
            _run_command()

    assert call("collectstatic", interactive=False, verbosity=1) not in (
        call_command.call_args_list
    )
