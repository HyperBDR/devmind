"""
Celery tasks for SALS: ETL sync from OneProCloud API with agentcore-task tracking.
"""
import logging

from celery import shared_task
from django.utils.translation import gettext as _

from agentcore_task.adapters.django import TaskTracker, TaskStatus

logger = logging.getLogger(__name__)

MODULE_NAME = "sals"


@shared_task(name="sals.tasks.sync_incidents", bind=True, max_retries=3)
def sync_incidents(self, full_sync: bool = True, user_id=None):
    """
    异步同步工单数据，支持任务追踪。

    Args:
        full_sync: True 时全量同步（先清空再写入），False 时增量更新
        user_id: 触发任务的用户 ID
    """
    task_id = self.request.id if self.request else None
    logger.info(
        "[sals.tasks] sync_incidents started, task_id=%s, full_sync=%s",
        task_id,
        full_sync,
    )

    if task_id:
        TaskTracker.register_task(
            task_id=task_id,
            task_name="sals.tasks.sync_incidents",
            module=MODULE_NAME,
            task_kwargs={"full_sync": full_sync},
            metadata={"full_sync": full_sync, "type": "incidents"},
            initial_status=TaskStatus.STARTED,
            created_by=user_id,
        )
        TaskTracker.update_task_status(
            task_id,
            TaskStatus.STARTED,
            metadata={
                "progress_percent": 5,
                "progress_message": _("Starting sync..."),
                "progress_step": "start",
                "full_sync": full_sync,
            },
        )

    try:
        from .services import etl

        if task_id:
            TaskTracker.update_task_status(
                task_id,
                TaskStatus.STARTED,
                metadata={
                    "progress_percent": 10,
                    "progress_message": _("Authenticating..."),
                    "progress_step": "auth",
                },
            )

        result = etl.sync_from_api(full_sync=full_sync)

        if task_id:
            TaskTracker.update_task_status(
                task_id,
                TaskStatus.SUCCESS,
                result=result,
                metadata={
                    "progress_percent": 100,
                    "progress_message": _("Sync completed"),
                    "progress_step": "done",
                    "full_sync": full_sync,
                    "result": result,
                },
            )

        logger.info(
            "[sals.tasks] sync_incidents completed, task_id=%s, result=%s",
            task_id,
            result,
        )
        return result

    except Exception as exc:
        logger.exception("[sals.tasks] sync_incidents failed, task_id=%s", task_id)
        if task_id:
            TaskTracker.update_task_status(
                task_id,
                TaskStatus.FAILURE,
                error=str(exc),
                metadata={
                    "progress_percent": 0,
                    "progress_message": _("Sync failed"),
                    "progress_step": "error",
                    "error": str(exc),
                },
            )
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="sals.tasks.sync_companies", bind=True, max_retries=3)
def sync_companies(self, user_id=None):
    """
    异步同步公司数据，支持任务追踪。
    """
    task_id = self.request.id if self.request else None
    logger.info(
        "[sals.tasks] sync_companies started, task_id=%s",
        task_id,
    )

    if task_id:
        TaskTracker.register_task(
            task_id=task_id,
            task_name="sals.tasks.sync_companies",
            module=MODULE_NAME,
            task_kwargs={},
            metadata={"type": "companies"},
            initial_status=TaskStatus.STARTED,
            created_by=user_id,
        )

    try:
        from .services import etl

        result = etl.sync_companies_from_api()

        if task_id:
            TaskTracker.update_task_status(
                task_id,
                TaskStatus.SUCCESS,
                result=result,
                metadata={
                    "progress_percent": 100,
                    "progress_message": _("Company sync completed"),
                    "progress_step": "done",
                },
            )

        return result

    except Exception as exc:
        logger.exception("[sals.tasks] sync_companies failed")
        if task_id:
            TaskTracker.update_task_status(
                task_id,
                TaskStatus.FAILURE,
                error=str(exc),
            )
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="sals.tasks.sync_users", bind=True, max_retries=3)
def sync_users(self, user_id=None):
    """
    异步同步用户数据，支持任务追踪。
    """
    task_id = self.request.id if self.request else None
    logger.info(
        "[sals.tasks] sync_users started, task_id=%s",
        task_id,
    )

    if task_id:
        TaskTracker.register_task(
            task_id=task_id,
            task_name="sals.tasks.sync_users",
            module=MODULE_NAME,
            task_kwargs={},
            metadata={"type": "users"},
            initial_status=TaskStatus.STARTED,
            created_by=user_id,
        )

    try:
        from .services import etl

        result = etl.sync_users_from_api()

        if task_id:
            TaskTracker.update_task_status(
                task_id,
                TaskStatus.SUCCESS,
                result=result,
                metadata={
                    "progress_percent": 100,
                    "progress_message": _("User sync completed"),
                    "progress_step": "done",
                },
            )

        return result

    except Exception as exc:
        logger.exception("[sals.tasks] sync_users failed")
        if task_id:
            TaskTracker.update_task_status(
                task_id,
                TaskStatus.FAILURE,
                error=str(exc),
            )
        raise self.retry(exc=exc, countdown=60)
