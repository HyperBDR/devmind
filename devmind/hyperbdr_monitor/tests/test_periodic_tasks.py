import pytest

from core.periodic_registry import TASK_REGISTRY
from hyperbdr_monitor.periodic_tasks import register_periodic_tasks


@pytest.mark.django_db
def test_register_periodic_tasks_adds_hyperbdr_entry():
    TASK_REGISTRY.clear()

    register_periodic_tasks()

    entry = TASK_REGISTRY._entries["hyperbdr_monitor.collect_due_sources"]
    assert entry["task"] == "hyperbdr_monitor.tasks.collect_due_sources"
    assert entry["enabled"] is True
