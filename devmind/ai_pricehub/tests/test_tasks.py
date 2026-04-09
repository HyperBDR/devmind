from types import SimpleNamespace

import pytest

from ai_pricehub import tasks


@pytest.mark.unit
def test_enqueue_pricing_sync_registers_task(monkeypatch):
    registered = {}

    def fake_delay(**kwargs):
        assert kwargs == {"platform_slug": "cn-main"}
        return SimpleNamespace(id="task-123")

    def fake_register_task_execution(**kwargs):
        registered.update(kwargs)

    monkeypatch.setattr(tasks.run_pricing_sync, "delay", fake_delay)
    monkeypatch.setattr(tasks, "register_task_execution", fake_register_task_execution)

    task_id = tasks.enqueue_pricing_sync(platform_slug="cn-main", created_by="user-1")

    assert task_id == "task-123"
    assert registered["task_id"] == "task-123"
    assert registered["task_name"] == tasks.TASK_NAME
    assert registered["module"] == tasks.MODULE_NAME
    assert registered["task_kwargs"] == {"platform_slug": "cn-main"}
    assert registered["metadata"]["platform_slug"] == "cn-main"


@pytest.mark.unit
def test_run_pricing_sync_updates_task_status(monkeypatch):
    updates = []

    monkeypatch.setattr(
        tasks.ai_pricehub_service,
        "sync_configured_sources",
        lambda platform_slug=None, task_id=None: {
            "accepted": True,
            "platform_slug": platform_slug,
            "task_id": task_id,
        },
    )
    monkeypatch.setattr(
        tasks,
        "current_task",
        SimpleNamespace(request=SimpleNamespace(id="task-456")),
    )
    monkeypatch.setattr(
        tasks.TaskTracker,
        "update_task_status",
        lambda *args, **kwargs: updates.append((args, kwargs)),
    )

    result = tasks.run_pricing_sync(platform_slug="cn-main")

    assert result == {
        "accepted": True,
        "platform_slug": "cn-main",
        "task_id": "task-456",
    }
    assert updates[0][0][0] == "task-456"
    assert updates[0][0][1] == tasks.TaskStatus.STARTED
    assert updates[1][0][0] == "task-456"
    assert updates[1][0][1] == tasks.TaskStatus.SUCCESS
