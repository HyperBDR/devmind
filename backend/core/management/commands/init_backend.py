"""
Run deployment-time backend initialization in a single Django process.

The container entrypoint used to invoke several ``manage.py`` commands in
sequence. Each invocation paid the full Django import and app-loading cost.
This command keeps the same operations in one process and reports per-step
timings so slow startup work is visible in container logs.
"""
import os
import time
from contextlib import contextmanager

from django.core.management import call_command
from django.core.management.base import BaseCommand

from core.management.commands.register_periodic_tasks import (
    discover_and_register,
)
from core.periodic_registry import TASK_REGISTRY


FALSE_VALUES = {"0", "false", "no", "off"}


def _env_enabled(name, default=True):
    """Return a boolean from an environment variable."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() not in FALSE_VALUES


class Command(BaseCommand):
    """Initialize database-backed runtime state for the backend service."""

    help = (
        "Run migrations, register periodic tasks, and optionally collect "
        "static files in one Django process."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--phase",
            choices=("all", "schema", "runtime"),
            default="all",
            help=(
                "Initialization phase to run. schema runs migrations only; "
                "runtime runs database-backed runtime setup only."
            ),
        )
        parser.add_argument(
            "--skip-collectstatic",
            action="store_true",
            help="Skip collectstatic even if BACKEND_INIT_COLLECTSTATIC=true.",
        )

    @contextmanager
    def _timed_step(self, label):
        started_at = time.perf_counter()
        self.stdout.write(f"[init_backend] {label}...")
        try:
            yield
        except Exception:
            elapsed = time.perf_counter() - started_at
            self.stdout.write(
                self.style.ERROR(
                    f"[init_backend] {label} failed after {elapsed:.2f}s"
                )
            )
            raise
        elapsed = time.perf_counter() - started_at
        self.stdout.write(
            self.style.SUCCESS(
                f"[init_backend] {label} finished in {elapsed:.2f}s"
            )
        )

    def handle(self, *args, **options):
        verbosity = options.get("verbosity", 1)
        phase = options["phase"]

        if phase in {"all", "schema"}:
            with self._timed_step("Running Django migrations"):
                call_command("migrate", interactive=False, verbosity=verbosity)

        if phase == "schema":
            return

        with self._timed_step("Registering periodic tasks"):
            discover_and_register()
            count = len(TASK_REGISTRY)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[init_backend] Registered {count} periodic task(s)."
                )
            )

        with self._timed_step("Preparing quotation storage control plane"):
            call_command(
                "migrate_feishu_control_plane",
                "--apply",
                verbosity=verbosity,
            )

        should_collect_static = _env_enabled(
            "BACKEND_INIT_COLLECTSTATIC",
            default=True,
        )
        if options["skip_collectstatic"]:
            should_collect_static = False

        if should_collect_static:
            with self._timed_step("Collecting static files"):
                call_command(
                    "collectstatic",
                    interactive=False,
                    verbosity=verbosity,
                )
        else:
            self.stdout.write(
                "[init_backend] BACKEND_INIT_COLLECTSTATIC disabled; "
                "skipping collectstatic."
            )
