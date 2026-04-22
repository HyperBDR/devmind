"""
Discover all installed apps' periodic_tasks and register to Celery Beat.

Run at startup (e.g. in entrypoint after migrate) so that each app's
register_periodic_tasks() is called and tasks are written to
django_celery_beat. No Django signals; keeps the flow explicit and portable.
"""
import importlib
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from core.periodic_registry import (
    TASK_REGISTRY,
    apply_registry,
    remove_periodic_tasks,
)

logger = logging.getLogger(__name__)

RETIRED_PERIODIC_TASK_NAMES = (
    "hyperbdr_monitor.collect_due_sources",
    "onepro_monitor.collect_due_sources",
)

RETIRED_PERIODIC_TASK_TASKS = (
    "hyperbdr_monitor.tasks.collect_due_sources",
    "onepro_monitor.tasks.collect_due_sources",
)


def discover_and_register():
    """
    Clear registry, discover each app's periodic_tasks, call
    register_periodic_tasks, then apply registry to django_celery_beat.
    """
    TASK_REGISTRY.clear()

    for app in settings.INSTALLED_APPS:
        try:
            module = importlib.import_module(f"{app}.periodic_tasks")
        except ModuleNotFoundError:
            continue

        if hasattr(module, "register_periodic_tasks"):
            try:
                module.register_periodic_tasks()
            except Exception as e:
                logger.exception(
                    f"register_periodic_tasks failed for app {app}: {e}"
                )

    removed_count = remove_periodic_tasks(
        names=RETIRED_PERIODIC_TASK_NAMES,
        task_names=RETIRED_PERIODIC_TASK_TASKS,
    )
    if removed_count:
        logger.info("Removed %s retired monitor periodic task row(s).", removed_count)

    apply_registry()
    return removed_count


class Command(BaseCommand):
    help = (
        "Discover all apps' periodic_tasks.register_periodic_tasks() and "
        "register entries to django_celery_beat without updating existing "
        "rows."
    )

    def handle(self, *args, **options):
        removed_count = discover_and_register()
        count = len(TASK_REGISTRY)
        self.stdout.write(
            self.style.SUCCESS(
                f"Registered {count} periodic task(s) to django_celery_beat; "
                f"removed {removed_count} retired task row(s)."
            )
        )
