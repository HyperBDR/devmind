"""
Task tracking service for unified task management.
"""
import logging
import traceback as tb
from typing import Any, Dict, Optional

from celery.result import AsyncResult
from django.contrib.auth.models import User
from django.utils import timezone

from ..constants import TaskStatus
from ..models import TaskExecution

logger = logging.getLogger(__name__)


class TaskTracker:
    """
    Service for tracking and managing task executions.

    This service provides methods to register tasks, update their status,
    and query task information. It integrates with django_celery_results
    to sync task status from Celery.
    """

    @staticmethod
    def register_task(
        task_id: str,
        task_name: str,
        module: str,
        task_args: Optional[list] = None,
        task_kwargs: Optional[dict] = None,
        created_by: Optional[User] = None,
        metadata: Optional[dict] = None
    ) -> TaskExecution:
        """
        Register a new task execution record.

        Args:
            task_id: Celery task ID
            task_name: Task name
            (e.g., 'cloud_billing.tasks.collect_billing_data')
            module: Module name that owns this task
            task_args: Task arguments
            task_kwargs: Task keyword arguments
            created_by: User who triggered the task
            metadata: Additional metadata

        Returns:
            TaskExecution instance
        """
        task_execution, created = TaskExecution.objects.get_or_create(
            task_id=task_id,
            defaults={
                'task_name': task_name,
                'module': module,
                'status': TaskStatus.PENDING,
                'task_args': task_args or [],
                'task_kwargs': task_kwargs or {},
                'created_by': created_by,
                'metadata': metadata or {},
            }
        )

        if created:
            logger.info(
                f"Registered new task: {task_name} ({task_id}) "
                f"in module {module}"
            )
        else:
            logger.debug(
                f"Task already registered: {task_name} ({task_id})"
            )

        return task_execution

    @staticmethod
    def update_task_status(
        task_id: str,
        status: str,
        result: Optional[Any] = None,
        error: Optional[str] = None,
        traceback: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[TaskExecution]:
        """
        Update task execution status.

        Args:
            task_id: Celery task ID
            status: New status
            result: Task result data
            error: Error message if failed
            traceback: Error traceback if failed
            metadata: Additional metadata to update
            (will be merged with existing)

        Returns:
            Updated TaskExecution instance or None if not found
        """
        try:
            task_execution = TaskExecution.objects.get(task_id=task_id)

            old_status = task_execution.status
            task_execution.status = status

            if status == TaskStatus.STARTED and not task_execution.started_at:
                task_execution.started_at = timezone.now()
            elif status in TaskStatus.get_completed_statuses():
                if not task_execution.finished_at:
                    task_execution.finished_at = timezone.now()

            if result is not None:
                task_execution.result = result

            if error is not None:
                task_execution.error = error

            if traceback is not None:
                task_execution.traceback = traceback

            if metadata is not None:
                if task_execution.metadata is None:
                    task_execution.metadata = {}
                task_execution.metadata.update(metadata)

            task_execution.save()

            if old_status != status:
                logger.info(
                    f"Updated task status: {task_execution.task_name} "
                    f"({task_id}) {old_status} -> {status}"
                )

            return task_execution

        except TaskExecution.DoesNotExist:
            logger.warning(f"Task execution not found: {task_id}")
            return None

    @staticmethod
    def sync_task_from_celery(task_id: str) -> Optional[TaskExecution]:
        """
        Sync task status from Celery result backend.

        Args:
            task_id: Celery task ID

        Returns:
            Updated TaskExecution instance or None if not found
        """
        try:
            task_execution = TaskExecution.objects.get(task_id=task_id)
            async_result = AsyncResult(task_id)

            status_mapping = {
                'PENDING': TaskStatus.PENDING,
                'STARTED': TaskStatus.STARTED,
                'SUCCESS': TaskStatus.SUCCESS,
                'FAILURE': TaskStatus.FAILURE,
                'RETRY': TaskStatus.RETRY,
                'REVOKED': TaskStatus.REVOKED,
            }

            celery_status = async_result.status
            new_status = status_mapping.get(celery_status, TaskStatus.PENDING)

            if task_execution.status != new_status:
                result = None
                error = None
                traceback = None

                if async_result.ready():
                    if celery_status == 'SUCCESS':
                        result = async_result.result
                    elif celery_status == 'FAILURE':
                        try:
                            result = async_result.result
                            if isinstance(result, Exception):
                                error = str(result)
                        except Exception as e:
                            error = str(e)
                            traceback = getattr(result, '__traceback__', None)
                            if traceback:
                                traceback = ''.join(
                                    tb.format_tb(traceback)
                                )

                return TaskTracker.update_task_status(
                    task_id=task_id,
                    status=new_status,
                    result=result,
                    error=error,
                    traceback=traceback
                )

            return task_execution

        except TaskExecution.DoesNotExist:
            logger.warning(f"Task execution not found: {task_id}")
            return None
        except Exception as e:
            logger.error(
                f"Error syncing task from Celery: {task_id}, error: {str(e)}"
            )
            return None

    @staticmethod
    def get_task(task_id: str, sync: bool = True) -> Optional[TaskExecution]:
        """
        Get task execution by task ID.

        Args:
            task_id: Celery task ID
            sync: Whether to sync status from Celery before returning

        Returns:
            TaskExecution instance or None if not found
        """
        try:
            task_execution = TaskExecution.objects.get(task_id=task_id)

            if sync:
                TaskTracker.sync_task_from_celery(task_id)
                task_execution.refresh_from_db()

            return task_execution

        except TaskExecution.DoesNotExist:
            return None

    @staticmethod
    def get_task_stats(
        module: Optional[str] = None,
        task_name: Optional[str] = None,
        created_by: Optional[User] = None
    ) -> Dict[str, Any]:
        """
        Get task execution statistics.

        Args:
            module: Filter by module name
            task_name: Filter by task name
            created_by: Filter by user who created the task

        Returns:
            Dictionary with statistics
        """
        queryset = TaskExecution.objects.all()

        if module:
            queryset = queryset.filter(module=module)

        if task_name:
            queryset = queryset.filter(task_name=task_name)

        if created_by:
            queryset = queryset.filter(created_by=created_by)

        total = queryset.count()

        stats = {
            'total': total,
            'pending': queryset.filter(status=TaskStatus.PENDING).count(),
            'started': queryset.filter(status=TaskStatus.STARTED).count(),
            'success': queryset.filter(status=TaskStatus.SUCCESS).count(),
            'failure': queryset.filter(status=TaskStatus.FAILURE).count(),
            'retry': queryset.filter(status=TaskStatus.RETRY).count(),
            'revoked': queryset.filter(status=TaskStatus.REVOKED).count(),
            'by_module': {},
            'by_task_name': {},
        }

        # Statistics by module
        module_stats = {}
        for module_name in queryset.values_list('module', flat=True).distinct():
            module_queryset = queryset.filter(module=module_name)
            module_stats[module_name] = {
                'total': module_queryset.count(),
                'pending': module_queryset.filter(status=TaskStatus.PENDING).count(),
                'started': module_queryset.filter(status=TaskStatus.STARTED).count(),
                'success': module_queryset.filter(status=TaskStatus.SUCCESS).count(),
                'failure': module_queryset.filter(status=TaskStatus.FAILURE).count(),
                'retry': module_queryset.filter(status=TaskStatus.RETRY).count(),
                'revoked': module_queryset.filter(status=TaskStatus.REVOKED).count(),
            }
        stats['by_module'] = module_stats

        # Statistics by task name
        task_name_stats = {}
        for name in queryset.values_list('task_name', flat=True).distinct():
            task_queryset = queryset.filter(task_name=name)
            pending = task_queryset.filter(
                status=TaskStatus.PENDING
            ).count()
            started = task_queryset.filter(
                status=TaskStatus.STARTED
            ).count()
            success = task_queryset.filter(
                status=TaskStatus.SUCCESS
            ).count()
            failure = task_queryset.filter(
                status=TaskStatus.FAILURE
            ).count()
            retry = task_queryset.filter(
                status=TaskStatus.RETRY
            ).count()
            revoked = task_queryset.filter(
                status=TaskStatus.REVOKED
            ).count()
            task_name_stats[name] = {
                'total': task_queryset.count(),
                'pending': pending,
                'started': started,
                'success': success,
                'failure': failure,
                'retry': retry,
                'revoked': revoked,
            }
        stats['by_task_name'] = task_name_stats

        return stats
