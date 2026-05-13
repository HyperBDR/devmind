"""
Register this app's periodic tasks with the scheduler registry.

Called by the main project's register_periodic_tasks management command.
"""
import os

from celery.schedules import crontab

from core.periodic_registry import TASK_REGISTRY


def register_periodic_tasks():
    # Cloud billing collection interval (default: hourly at minute 10)
    # Set CLOUD_BILLING_INTERVAL_MINUTES=5 for every 5 minutes, etc.
    interval_minutes = os.getenv("CLOUD_BILLING_INTERVAL_MINUTES", "10")
    try:
        minute_schedule = int(interval_minutes)
        if minute_schedule < 1:
            minute_schedule = 10
    except (ValueError, TypeError):
        minute_schedule = 10

    TASK_REGISTRY.add(
        name="cloud_billing_hourly_collection",
        task="cloud_billing.tasks.collect_billing_data",
        schedule=crontab(minute=f"*/{minute_schedule}"),
        args=(),
        kwargs={"user_id": 0},
        queue=None,
        enabled=True,
    )

    # Daily cost report (default 9:00 AM, configurable)
    report_hour = os.getenv("CLOUD_BILLING_REPORT_HOUR", "9")
    report_minute = os.getenv("CLOUD_BILLING_REPORT_MINUTE", "0")

    TASK_REGISTRY.add(
        name="cloud_billing_daily_report",
        task="cloud_billing.tasks.send_daily_cost_report",
        schedule=crontab(
            hour=int(report_hour),
            minute=int(report_minute),
        ),
        args=(),
        kwargs={},
        queue=None,
        enabled=True,
    )
