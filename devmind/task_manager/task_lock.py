"""
Task Lock Management

Provides utilities for managing task locks to prevent duplicate execution.
"""

import hashlib
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Default timeout: 1 hour (3600 seconds)
DEFAULT_TASK_TIMEOUT = 3600
LOCK_KEY_PREFIX = "task_manager_task_lock"


def acquire_task_lock(
    lock_name: str,
    timeout: int = DEFAULT_TASK_TIMEOUT
) -> bool:
    """
    Acquire task lock.

    Args:
        lock_name: Lock name (e.g., 'collect_billing_data')
        timeout: Lock timeout in seconds (default: 3600)

    Returns:
        True if lock acquired successfully, False if already locked
    """
    lock_key = f"{LOCK_KEY_PREFIX}:{lock_name}"

    try:
        acquired = cache.add(lock_key, "locked", timeout=timeout)

        if acquired:
            logger.info(f"Acquired task lock: {lock_name}")
        else:
            logger.warning(f"Task lock already exists: {lock_name}")

        return acquired

    except Exception as exc:
        logger.error(f"Failed to acquire task lock {lock_name}: {exc}")
        return False


def release_task_lock(lock_name: str) -> bool:
    """
    Release task lock.

    Args:
        lock_name: Lock name to release

    Returns:
        True if lock released successfully
    """
    lock_key = f"{LOCK_KEY_PREFIX}:{lock_name}"

    try:
        cache.delete(lock_key)
        logger.info(f"Released task lock: {lock_name}")
        return True

    except Exception as exc:
        logger.error(f"Failed to release task lock {lock_name}: {exc}")
        return False


def is_task_locked(lock_name: str) -> bool:
    """
    Check if task is locked.

    Args:
        lock_name: Lock name to check

    Returns:
        True if task is locked
    """
    lock_key = f"{LOCK_KEY_PREFIX}:{lock_name}"

    try:
        return cache.get(lock_key) is not None

    except Exception as exc:
        logger.error(f"Failed to check task lock {lock_name}: {exc}")
        return False


def _extract_lock_param_value(args, kwargs, lock_param):
    """
    Extract lock parameter value from function arguments.

    Args:
        args: Function positional arguments
        kwargs: Function keyword arguments
        lock_param: Parameter name to extract

    Returns:
        Parameter value or None if not found
    """
    param_value = kwargs.get(lock_param)

    # If not in kwargs, check args
    # Skip args[0] if it's 'self' (for @shared_task(bind=True))
    if not param_value and args:
        # Check if args[0] looks like a Celery task instance
        if hasattr(args[0], 'request'):
            # args[0] is self (Celery task), use args[1]
            param_value = args[1] if len(args) > 1 else None
        else:
            # args[0] is the actual parameter
            param_value = args[0]

    return param_value


def _build_task_lock_name(lock_name, lock_param, param_value):
    """
    Build task lock name from base lock name and parameter value.

    Args:
        lock_name: Base lock name
        lock_param: Parameter name
        param_value: Parameter value

    Returns:
        str: Full lock name
    """
    if not param_value:
        return lock_name

    # For long values, use MD5 hash to keep lock key under 250 characters
    param_str = str(param_value)
    use_hash = len(param_str) > 200

    if use_hash:
        param_hash = hashlib.md5(
            param_str.encode('utf-8')
        ).hexdigest()[:16]
        task_lock_name = f"{lock_name}_{param_hash}"
        logger.debug(
            f"Built lock name with {lock_param} hash "
            f"(original length: {len(param_str)}): "
            f"{task_lock_name}"
        )
    else:
        task_lock_name = f"{lock_name}_{param_value}"
        logger.debug(
            f"Built lock name with "
            f"{lock_param}={param_value}: "
            f"{task_lock_name}"
        )

    return task_lock_name


def prevent_duplicate_task(
    lock_name: str,
    timeout: int = DEFAULT_TASK_TIMEOUT,
    lock_param: str = None
):
    """
    Decorator to prevent duplicate task execution.

    Args:
        lock_name: Base lock name for the task
        timeout: Lock timeout in seconds
        lock_param: Parameter name to use for generating unique lock
            (e.g., 'user_id', 'provider_id')
            If provided, the lock name will be: {lock_name}_{param_value}
            If not provided, all tasks share the same lock

    Examples:
        # Single global lock for the task
        @shared_task(name='myapp.tasks.my_task')
        @prevent_duplicate_task("my_task", timeout=3600)
        def my_task():
            pass

        # Per-user lock
        @shared_task(name='myapp.tasks.my_task')
        @prevent_duplicate_task("my_task", lock_param="user_id", timeout=3600)
        def my_task(user_id):
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            task_lock_name = lock_name

            if lock_param:
                param_value = _extract_lock_param_value(
                    args, kwargs, lock_param
                )

                if param_value is not None:
                    task_lock_name = _build_task_lock_name(
                        lock_name, lock_param, param_value
                    )
                else:
                    logger.warning(
                        f"Could not extract {lock_param} from task "
                        f"arguments, using base lock name: {lock_name}"
                    )

            logger.info(
                f"Task {task_lock_name} received, checking lock status"
            )

            if is_task_locked(task_lock_name):
                logger.warning(
                    f"Task {task_lock_name} is already running, skipping"
                )
                return {
                    'success': False,
                    'status': 'skipped',
                    'reason': 'task_already_running',
                    'error': f'Task {task_lock_name} is already running'
                }

            if not acquire_task_lock(task_lock_name, timeout):
                logger.warning(
                    f"Failed to acquire lock for {task_lock_name}"
                )
                return {
                    'success': False,
                    'status': 'skipped',
                    'reason': 'lock_acquisition_failed',
                    'error': f'Failed to acquire lock for {task_lock_name}'
                }

            try:
                result = func(*args, **kwargs)
                return result

            finally:
                release_task_lock(task_lock_name)

        wrapper.__name__ = func.__name__
        wrapper.__module__ = func.__module__
        wrapper.__doc__ = func.__doc__

        return wrapper
    return decorator
