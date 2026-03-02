"""
Sync CollectorConfig to django_celery_beat PeriodicTasks.
Create/update/disable periodic tasks when config is saved or deleted.
"""
import json
import logging

logger = logging.getLogger(__name__)

COLLECT_TASK_NAME_PREFIX = "data_collector_collect_config_"
CLEANUP_TASK_NAME_PREFIX = "data_collector_cleanup_config_"
COLLECT_TASK = "data_collector.tasks.run_collect"
CLEANUP_TASK = "data_collector.tasks.run_cleanup"


def _crontab_from_string(cron_expr: str):
    """
    Parse 5-field cron string (minute hour day_of_month month day_of_week)
    and return django_celery_beat CrontabSchedule or None.
    """
    # Defer import to avoid circular import at module load.
    from django_celery_beat.models import CrontabSchedule

    parts = (cron_expr or "").strip().split()
    if len(parts) != 5:
        return None
    minute, hour, day_of_month, month_of_year, day_of_week = parts
    obj, _ = CrontabSchedule.objects.get_or_create(
        minute=minute,
        hour=hour,
        day_of_week=day_of_week,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
    )
    return obj


def sync_config_to_beat(config) -> None:
    """
    Create or update Beat periodic tasks for this CollectorConfig.
    Call inside transaction.atomic() with config save.
    """
    # Defer import to avoid circular import at module load.
    from django_celery_beat.models import PeriodicTask, PeriodicTasks

    config_uuid_str = str(config.uuid)
    value = config.value or {}
    schedule_cron = value.get("schedule_cron") or "0 */2 * * *"
    cleanup_cron = value.get("cleanup_cron") or "0 3 * * *"
    enabled = config.is_enabled

    collect_name = f"{COLLECT_TASK_NAME_PREFIX}{config_uuid_str}"
    cleanup_name = f"{CLEANUP_TASK_NAME_PREFIX}{config_uuid_str}"
    kwargs = json.dumps({"config_uuid": config_uuid_str})

    crontab_collect = _crontab_from_string(schedule_cron)
    crontab_cleanup = _crontab_from_string(cleanup_cron)
    if not crontab_collect or not crontab_cleanup:
        logger.warning(
            f"data_collector: invalid cron for config {config_uuid_str}, "
            "using defaults"
        )
        default_c = _crontab_from_string("0 */2 * * *") or crontab_collect
        default_clean = _crontab_from_string("0 3 * * *") or crontab_cleanup
        crontab_collect = default_c
        crontab_cleanup = default_clean

    for name, task_name, crontab in [
        (collect_name, COLLECT_TASK, crontab_collect),
        (cleanup_name, CLEANUP_TASK, crontab_cleanup),
    ]:
        obj, created = PeriodicTask.objects.update_or_create(
            name=name,
            defaults={
                "task": task_name,
                "kwargs": kwargs,
                "crontab": crontab,
                "enabled": enabled,
            },
        )
        if created:
            logger.info(f"data_collector: created Beat task {name}")
        else:
            logger.debug(f"data_collector: updated Beat task {name}")

    PeriodicTasks.update_changed()


def unsync_config_from_beat(config) -> None:
    """
    Disable or remove Beat periodic tasks for this config.
    Call when config is disabled or deleted.
    """
    # Defer import to avoid circular import at module load.
    from django_celery_beat.models import PeriodicTask, PeriodicTasks

    config_uuid_str = str(config.uuid)
    for prefix in (COLLECT_TASK_NAME_PREFIX, CLEANUP_TASK_NAME_PREFIX):
        name = f"{prefix}{config_uuid_str}"
        PeriodicTask.objects.filter(name=name).delete()
    PeriodicTasks.update_changed()
    logger.info(
        f"data_collector: removed Beat tasks for config {config_uuid_str}"
    )
