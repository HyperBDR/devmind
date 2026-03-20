"""Regression tests for the periodic task registry."""

import importlib.util
import os
from pathlib import Path

import django
import pytest


os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "devmind.tests.core_periodic_registry_settings",
)
django.setup()


def _load_periodic_registry_module():
    module_path = (
        Path(__file__).resolve().parent.parent / "core" / "periodic_registry.py"
    )
    spec = importlib.util.spec_from_file_location(
        "devmind_core_periodic_registry",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.mark.django_db
def test_task_registry_skips_existing_periodic_task():
    module = _load_periodic_registry_module()

    from celery.schedules import crontab
    from django.conf import settings
    from django_celery_beat.models import CrontabSchedule, PeriodicTask

    existing_schedule = CrontabSchedule.objects.create(
        minute="0",
        hour="1",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone=settings.TIME_ZONE,
    )
    task = PeriodicTask.objects.create(
        name="sample-task",
        task="legacy.task",
        args='["legacy"]',
        kwargs='{"retry": false}',
        queue="manual-queue",
        enabled=False,
        crontab=existing_schedule,
    )

    registry = module.TaskRegistry()
    registry.add(
        name="sample-task",
        task="code.task",
        schedule=crontab(minute="*/15"),
        args=("fresh",),
        kwargs={"retry": True},
        queue="code-queue",
        enabled=True,
    )

    registry.apply()

    task.refresh_from_db()
    assert task.task == "legacy.task"
    assert task.args == '["legacy"]'
    assert task.kwargs == '{"retry": false}'
    assert task.queue == "manual-queue"
    assert task.enabled is False
    assert task.crontab_id == existing_schedule.id
    assert task.crontab.minute == "0"
    assert task.interval is None
