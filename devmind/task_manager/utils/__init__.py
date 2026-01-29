"""
Task manager utility modules.
"""
from typing import Optional

from django.contrib.auth.models import User

from ..models import TaskExecution
from ..services.task_tracker import TaskTracker


def register_task_execution(
    task_id: str,
    task_name: str,
    module: str,
    task_args: Optional[list] = None,
    task_kwargs: Optional[dict] = None,
    created_by: Optional[User] = None,
    metadata: Optional[dict] = None
) -> TaskExecution:
    """
    Helper function to register a task execution.

    This can be called manually when a task is triggered,
    before the task decorator runs.

    Args:
        task_id: Celery task ID
        task_name: Task name
        module: Module name
        task_args: Task arguments
        task_kwargs: Task keyword arguments
        created_by: User who triggered the task
        metadata: Additional metadata

    Returns:
        TaskExecution instance
    """
    return TaskTracker.register_task(
        task_id=task_id,
        task_name=task_name,
        module=module,
        task_args=task_args,
        task_kwargs=task_kwargs,
        created_by=created_by,
        metadata=metadata
    )


__all__ = ['register_task_execution']
