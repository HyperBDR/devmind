import pytest

from core.periodic_registry import TASK_REGISTRY
from hyperbdr_dashboard.periodic_tasks import register_periodic_tasks


def test_no_periodic_tasks_registered():
    """hyperbdr_dashboard does not register any periodic tasks."""
    TASK_REGISTRY.clear()

    register_periodic_tasks()

    # Empty registry since periodic_tasks.py is intentionally empty
    assert len(TASK_REGISTRY._entries) == 0
