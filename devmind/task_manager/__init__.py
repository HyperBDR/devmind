"""
Task management app for unified task tracking and management.
"""
from .task_lock import (
    acquire_task_lock,
    is_task_locked,
    prevent_duplicate_task,
    release_task_lock
)

default_app_config = 'task_manager.apps.TaskManagerConfig'

__all__ = [
    'acquire_task_lock',
    'is_task_locked',
    'prevent_duplicate_task',
    'release_task_lock',
]
