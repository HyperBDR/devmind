import pytest

from hyperbdr_dashboard import periodic_tasks


def test_no_periodic_tasks_registered():
    """hyperbdr_dashboard does not register any periodic tasks."""
    assert not hasattr(periodic_tasks, "register_periodic_tasks")
