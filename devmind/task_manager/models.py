"""
Task execution tracking models for unified task management.
"""
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from .constants import TaskStatus


class TaskExecution(models.Model):
    """
    Unified task execution record model.

    This model tracks all task executions across different modules,
    providing a centralized way to monitor and query task status.
    """
    STATUS_CHOICES = [
        (TaskStatus.PENDING, 'Pending'),
        (TaskStatus.STARTED, 'Started'),
        (TaskStatus.SUCCESS, 'Success'),
        (TaskStatus.FAILURE, 'Failure'),
        (TaskStatus.RETRY, 'Retry'),
        (TaskStatus.REVOKED, 'Revoked'),
    ]

    # Task identification
    task_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Celery task ID"
    )
    task_name = models.CharField(
        max_length=255,
        db_index=True,
        help_text=(
            "Task name (e.g., "
            "'cloud_billing.tasks.collect_billing_data')"
        )
    )

    # Module information
    module = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Module name that owns this task (e.g., 'cloud_billing')"
    )

    # Task status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=TaskStatus.PENDING,
        db_index=True,
        help_text="Current task status"
    )

    # Execution timing
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the task was created"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the task started execution"
    )
    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the task finished execution"
    )

    # Task metadata
    task_args = models.JSONField(
        null=True,
        blank=True,
        help_text="Task arguments"
    )
    task_kwargs = models.JSONField(
        null=True,
        blank=True,
        help_text="Task keyword arguments"
    )

    # Result information
    result = models.JSONField(
        null=True,
        blank=True,
        help_text="Task result data"
    )
    error = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if task failed"
    )
    traceback = models.TextField(
        null=True,
        blank=True,
        help_text="Error traceback if task failed"
    )

    # User information
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tasks',
        help_text="User who triggered this task"
    )

    # Additional metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata for the task"
    )

    class Meta:
        db_table = 'task_manager_execution'
        verbose_name = 'Task Execution'
        verbose_name_plural = 'Task Executions'
        indexes = [
            models.Index(fields=['module', 'status']),
            models.Index(fields=['task_name', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['module', 'created_at']),
            models.Index(fields=['created_by', 'status']),
            models.Index(fields=['created_by', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.task_name} ({self.task_id}) - {self.status}"

    @property
    def duration(self):
        """
        Calculate task execution duration in seconds.
        """
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        elif self.started_at:
            return (timezone.now() - self.started_at).total_seconds()
        return None

    @property
    def is_completed(self):
        """
        Check if task is in a completed state.
        """
        return self.status in TaskStatus.get_completed_statuses()

    @property
    def is_running(self):
        """
        Check if task is currently running.
        """
        return self.status in TaskStatus.get_running_statuses()

    @classmethod
    def get_user_tasks(cls, user, **filters):
        """
        Get tasks for a specific user.

        Args:
            user: User instance
            **filters: Additional filter parameters

        Returns:
            QuerySet of tasks for the user
        """
        queryset = cls.objects.filter(created_by=user)
        if filters:
            queryset = queryset.filter(**filters)
        return queryset
