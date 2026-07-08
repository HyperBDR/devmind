import json
import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "tests.core_periodic_registry_settings",
)

import django
from celery.schedules import crontab
from django.test import TestCase

django.setup()

from core.periodic_registry import TaskRegistry
from django_celery_beat.models import CrontabSchedule
from django_celery_beat.models import PeriodicTask


class TaskRegistryForceApplyTests(TestCase):
    """Periodic registry force mode restores code-defined defaults."""

    def test_existing_task_is_skipped_without_force(self):
        existing_schedule = CrontabSchedule.objects.create(
            minute="*",
            hour="*",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="UTC",
        )
        PeriodicTask.objects.create(
            name="llm_ops_model_price_sync_agent",
            task="legacy.task",
            crontab=existing_schedule,
            args=json.dumps(["legacy"]),
            kwargs=json.dumps({"source_ids": [1]}),
            queue="legacy",
            enabled=False,
        )

        registry = TaskRegistry()
        registry.add(
            name="llm_ops_model_price_sync_agent",
            task="llm_ops.tasks.run_model_price_sync_agent",
            schedule=crontab(minute="15", hour="1,7,13,19"),
            kwargs={"source_ids": None, "verify_source": True},
            queue="backend",
            enabled=True,
        )

        registry.apply()

        task = PeriodicTask.objects.get(
            name="llm_ops_model_price_sync_agent"
        )
        self.assertEqual(task.task, "legacy.task")
        self.assertEqual(task.crontab.minute, "*")
        self.assertEqual(task.crontab.hour, "*")
        self.assertEqual(json.loads(task.kwargs), {"source_ids": [1]})
        self.assertEqual(task.queue, "legacy")
        self.assertFalse(task.enabled)

    def test_force_updates_existing_task_to_registry_definition(self):
        existing_schedule = CrontabSchedule.objects.create(
            minute="*",
            hour="*",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="UTC",
        )
        PeriodicTask.objects.create(
            name="llm_ops_model_price_sync_agent",
            task="legacy.task",
            crontab=existing_schedule,
            args=json.dumps(["legacy"]),
            kwargs=json.dumps({"source_ids": [1]}),
            queue="legacy",
            enabled=False,
        )

        registry = TaskRegistry()
        registry.add(
            name="llm_ops_model_price_sync_agent",
            task="llm_ops.tasks.run_model_price_sync_agent",
            schedule=crontab(minute="15", hour="1,7,13,19"),
            kwargs={"source_ids": None, "verify_source": True},
            queue="backend",
            enabled=True,
        )

        registry.apply(force=True)

        task = PeriodicTask.objects.get(
            name="llm_ops_model_price_sync_agent"
        )
        self.assertEqual(
            task.task,
            "llm_ops.tasks.run_model_price_sync_agent",
        )
        self.assertEqual(task.crontab.minute, "15")
        self.assertEqual(task.crontab.hour, "1,7,13,19")
        self.assertEqual(json.loads(task.args), [])
        self.assertEqual(
            json.loads(task.kwargs),
            {"source_ids": None, "verify_source": True},
        )
        self.assertEqual(task.queue, "backend")
        self.assertTrue(task.enabled)
