"""
Registry for periodic tasks. Apps register entries via
register_periodic_tasks(); apply_registry() writes them to
django_celery_beat. Existing rows are left untouched.

No Django signals; intended to be called from a CLI so the flow is portable
(e.g. future FastAPI migration).
"""
import json
import logging

logger = logging.getLogger(__name__)


def _is_crontab_schedule(schedule):
    return hasattr(schedule, "_orig_minute")


def _get_or_create_crontab(schedule):
    from django_celery_beat.models import CrontabSchedule
    from django.conf import settings

    try:
        obj, created = CrontabSchedule.from_schedule(schedule)
        if created:
            obj.save()
    except (AttributeError, TypeError):
        tz = getattr(schedule, "tz", None) or getattr(
            settings, "CELERY_TIMEZONE", None
        )
        spec = {
            "minute": getattr(schedule, "_orig_minute", "*"),
            "hour": getattr(schedule, "_orig_hour", "*"),
            "day_of_week": getattr(schedule, "_orig_day_of_week", "*"),
            "day_of_month": getattr(schedule, "_orig_day_of_month", "*"),
            "month_of_year": getattr(schedule, "_orig_month_of_year", "*"),
        }
        if tz:
            spec["timezone"] = tz
        obj, _ = CrontabSchedule.objects.get_or_create(**spec)
    return obj


def _get_or_create_interval_seconds(seconds):
    from django_celery_beat.models import IntervalSchedule

    every = max(int(seconds), 1)
    obj, _ = IntervalSchedule.objects.get_or_create(
        every=every,
        period=IntervalSchedule.SECONDS,
    )
    return obj


class TaskRegistry:
    """
    In-memory registry of periodic task definitions.

    Apps add entries via add(); apply() writes them to django_celery_beat.
    New tasks are created with full defaults. Existing tasks are left
    untouched so database-side customisations are preserved.
    """

    def __init__(self):
        self._entries = {}

    def clear(self):
        self._entries.clear()

    def __len__(self):
        return len(self._entries)

    def add(
        self,
        name,
        task,
        schedule,
        args=(),
        kwargs=None,
        queue=None,
        enabled=True,
    ):
        """
        Register a periodic task.

        name: unique identifier (e.g. "agentcore-task-mark-timed-out")
        task: Celery task name (e.g. agentcore_task.adapters.django.tasks...)
        schedule: celery.schedules.crontab, or number (seconds), or schedule
        args, kwargs: passed to the task
        queue: optional queue name
        enabled: whether the PeriodicTask is enabled
        """
        self._entries[name] = {
            "task": task,
            "schedule": schedule,
            "args": tuple(args) if args else (),
            "kwargs": dict(kwargs) if kwargs else {},
            "queue": queue,
            "enabled": enabled,
        }

    def _apply_one(self, name, entry, force=False):
        from django_celery_beat.models import PeriodicTask, PeriodicTasks

        task_name = entry["task"]
        schedule = entry["schedule"]
        args = entry["args"]
        kwargs = entry["kwargs"]
        queue = entry["queue"]
        enabled = entry["enabled"]

        if _is_crontab_schedule(schedule):
            crontab_schedule = _get_or_create_crontab(schedule)
            interval_schedule = None
        elif isinstance(schedule, (int, float)):
            interval_schedule = _get_or_create_interval_seconds(schedule)
            crontab_schedule = None
        else:
            run_every = getattr(schedule, "run_every", None)
            if run_every is not None:
                secs = run_every.total_seconds()
                interval_schedule = _get_or_create_interval_seconds(secs)
                crontab_schedule = None
            else:
                crontab_schedule = _get_or_create_crontab(schedule)
                interval_schedule = None

        desired_values = {
            "task": task_name,
            "args": json.dumps(list(args)),
            "kwargs": json.dumps(kwargs),
            "queue": queue,
            "enabled": enabled,
        }
        if crontab_schedule is not None:
            desired_values["crontab"] = crontab_schedule
            desired_values["interval"] = None
        else:
            desired_values["interval"] = interval_schedule
            desired_values["crontab"] = None

        obj, created = PeriodicTask.objects.get_or_create(
            name=name, defaults=desired_values
        )
        if not created:
            if force:
                update_fields = []
                for field_name, value in desired_values.items():
                    setattr(obj, field_name, value)
                    update_fields.append(field_name)

                for field_name in ("solar", "clocked"):
                    if hasattr(obj, field_name):
                        setattr(obj, field_name, None)
                        update_fields.append(field_name)

                obj.save(update_fields=update_fields)
                PeriodicTasks.update_changed()
                return "updated"

            logger.debug(
                "Periodic task already exists, skipping update: %s",
                name,
            )
            return "skipped"

        PeriodicTasks.update_changed()
        return "created"

    @staticmethod
    def _ensure_task_module_loaded(task_name):
        """
        Best-effort import of the module that *should* register a Celery
        task named ``task_name``.

        Celery resolves its ``imports`` config only inside the worker
        process. The ``register_periodic_tasks`` management command runs
        in a separate process where those modules may not yet be loaded,
        so we try to import the dotted module path prefix of ``task_name``
        (``a.b.c.task_name`` -> ``a.b.c``) and then re-check whether the
        task landed in ``app.tasks``.
        """
        try:
            from celery import current_app
        except Exception:  # pragma: no cover - celery not importable
            return True
        if task_name in current_app.tasks:
            return True
        module_name = (
            task_name.rsplit(".", 1)[0] if "." in task_name else ""
        )
        if not module_name:
            return task_name in current_app.tasks
        try:
            __import__(module_name)
        except Exception:
            return task_name in current_app.tasks
        return task_name in current_app.tasks

    @staticmethod
    def _is_task_registered(task_name):
        """
        Return whether ``task_name`` is currently known to the active Celery
        app. Used to surface missing task names instead of letting celery
        beat fail with a generic KeyError at dispatch time.
        """
        try:
            from celery import current_app
        except Exception:  # pragma: no cover - celery not importable
            return True
        try:
            if task_name in current_app.tasks:
                return True
            # Celery worker resolves ``imports`` lazily; the management
            # command path runs in a process where those modules may not
            # have been imported yet. Attempt a best-effort import and
            # re-check before declaring the task missing.
            module_name = (
                task_name.rsplit(".", 1)[0] if "." in task_name else ""
            )
            if module_name:
                try:
                    __import__(module_name)
                except Exception:
                    pass
            return task_name in current_app.tasks
        except Exception:
            # If anything goes wrong, don't block registration: the worst
            # case is the same KeyError that motivated this check.
            return True

    def apply(self, force=False):
        """
        Write all registered entries to django_celery_beat.

        Existing rows are skipped so database-side edits are preserved.
        When ``force`` is true, existing rows are overwritten with the
        registry definition so operators can restore code-defined
        schedules after accidental admin-side edits.
        Entries that reference a task name not yet known to the Celery
        app are logged at ERROR level so that missing-task regressions
        show up loudly during ``manage.py register_periodic_tasks``
        rather than only at runtime dispatch.
        """
        for name, entry in self._entries.items():
            task_name = entry.get("task")
            if task_name and not self._is_task_registered(task_name):
                logger.error(
                    "Periodic task '%s' references task '%s' which is not "
                    "registered in the Celery app. Skipping. This usually "
                    "means the task module is missing from "
                    "core.celery 'imports' or its package __init__ does "
                    "not re-export the @shared_task.",
                    name,
                    task_name,
                )
                continue
            try:
                result = self._apply_one(name, entry, force=force)
                if result == "created":
                    logger.debug(f"Registered periodic task: {name}")
                elif result == "updated":
                    logger.debug(f"Updated periodic task: {name}")
                else:
                    logger.debug(f"Skipped existing periodic task: {name}")
            except Exception as e:
                logger.exception(
                    f"Failed to register periodic task {name}: {e}"
                )


TASK_REGISTRY = TaskRegistry()


def apply_registry(force=False):
    """Apply the global TASK_REGISTRY to django_celery_beat."""
    TASK_REGISTRY.apply(force=force)
