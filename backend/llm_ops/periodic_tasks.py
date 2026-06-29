"""Register llm_ops periodic tasks with the global scheduler registry.

This module is imported by ``manage.py register_periodic_tasks`` (see
``backend/core/management/commands/register_periodic_tasks.py``) which
walks ``settings.INSTALLED_APPS`` and calls ``register_periodic_tasks``
on any app that exposes one. Existing rows in ``django_celery_beat``
are never overwritten, so operators can pause / reschedule entries
from the admin without losing them on the next deploy.
"""
from __future__ import annotations

import os

from celery.schedules import crontab

from core.periodic_registry import TASK_REGISTRY


# Cadence for the model price sync Agent. The defaults are deliberately
# conservative: 4 times a day is enough for LLM providers whose prices
# change at most weekly, and a single nightly run is plenty for the
# supplementary snapshots used by the UI.
DEFAULT_OFFICIAL_COLLECT_HOUR = os.getenv(
    "LLM_OPS_OFFICIAL_COLLECT_HOURS",
    "1,7,13,19",
)
DEFAULT_OFFICIAL_COLLECT_MINUTE = os.getenv(
    "LLM_OPS_OFFICIAL_COLLECT_MINUTE",
    "15",
)
DEFAULT_META_MODEL_SYNC_HOUR = os.getenv(
    "LLM_OPS_META_MODEL_SYNC_HOUR",
    "2",
)
DEFAULT_META_MODEL_SYNC_MINUTE = os.getenv(
    "LLM_OPS_META_MODEL_SYNC_MINUTE",
    "35",
)


def _parse_int_list(raw: str, fallback: list[int]) -> list[int]:
    """Parse a comma-separated list of integers, falling back on error."""
    try:
        values = [int(part.strip()) for part in raw.split(",") if part.strip()]
    except (TypeError, ValueError):
        return fallback
    return [value for value in values if 0 <= value <= 23] or fallback


def register_periodic_tasks() -> None:
    """Add llm_ops periodic tasks to the global registry.

    Adds a single ``llm_ops_model_price_sync_agent`` task that calls
    :func:`llm_ops.tasks.run_model_price_sync_agent`. The Agent reads
    ``LLMOpsGlobalConfig`` at runtime and delegates persistence to the
    platform collectors. The schedule is a crontab; cadence is read
    from the ``LLM_OPS_OFFICIAL_COLLECT_HOURS`` and
    ``LLM_OPS_OFFICIAL_COLLECT_MINUTE`` env vars so operators can tune
    it without a code change.
    """
    hours = _parse_int_list(
        DEFAULT_OFFICIAL_COLLECT_HOUR,
        fallback=[1, 7, 13, 19],
    )
    try:
        minute = int(DEFAULT_OFFICIAL_COLLECT_MINUTE)
    except (TypeError, ValueError):
        minute = 15
    minute = max(0, min(minute, 59))

    TASK_REGISTRY.add(
        name="llm_ops_model_price_sync_agent",
        task="llm_ops.tasks.run_model_price_sync_agent",
        schedule=crontab(hour=",".join(str(h) for h in hours), minute=minute),
        args=(),
        kwargs={"source_ids": None, "verify_source": True},
        queue=None,
        enabled=True,
    )

    try:
        meta_hour = int(DEFAULT_META_MODEL_SYNC_HOUR)
    except (TypeError, ValueError):
        meta_hour = 2
    try:
        meta_minute = int(DEFAULT_META_MODEL_SYNC_MINUTE)
    except (TypeError, ValueError):
        meta_minute = 35
    TASK_REGISTRY.add(
        name="llm_ops_meta_models_dev_sync",
        task="llm_ops.tasks.sync_meta_models_from_models_dev",
        schedule=crontab(
            hour=max(0, min(meta_hour, 23)),
            minute=max(0, min(meta_minute, 59)),
        ),
        args=(),
        kwargs={},
        queue=None,
        enabled=True,
    )
