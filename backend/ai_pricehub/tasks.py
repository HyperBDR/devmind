import logging

from celery import current_task, shared_task

from agentcore_task.adapters.django import (
    TaskStatus,
    TaskTracker,
    register_task_execution,
)

from .services import ai_pricehub_service


logger = logging.getLogger(__name__)

MODULE_NAME = "ai_pricehub"
TASK_NAME = "ai_pricehub.tasks.run_pricing_sync"


def enqueue_pricing_sync(
    *,
    platform_slug: str | None = None,
    created_by=None,
) -> str:
    task_kwargs = {}
    if platform_slug:
        task_kwargs["platform_slug"] = platform_slug
    task = run_pricing_sync.delay(**task_kwargs)
    register_task_execution(
        task_id=task.id,
        task_name=TASK_NAME,
        module=MODULE_NAME,
        task_kwargs=task_kwargs,
        created_by=created_by,
        metadata={
            "platform_slug": platform_slug or "",
            "task_type": "pricing_sync",
        },
        initial_status=TaskStatus.PENDING,
    )
    return task.id


@shared_task(name=TASK_NAME)
def run_pricing_sync(platform_slug: str | None = None):
    task_id = current_task.request.id if current_task else None
    metadata = {
        "platform_slug": platform_slug or "",
        "task_type": "pricing_sync",
    }
    if task_id:
        TaskTracker.update_task_status(
            task_id,
            TaskStatus.STARTED,
            metadata=metadata,
        )
    logger.info(
        "[ai_pricehub] run_pricing_sync started task_id=%s platform_slug=%s",
        task_id,
        platform_slug,
    )
    try:
        result = ai_pricehub_service.sync_configured_sources(
            platform_slug=platform_slug,
            task_id=task_id,
        )
        if task_id:
            TaskTracker.update_task_status(
                task_id,
                TaskStatus.SUCCESS,
                result=result,
                metadata=metadata,
            )
        return result
    except Exception as exc:
        logger.exception(
            "[ai_pricehub] run_pricing_sync failed task_id=%s platform_slug=%s",
            task_id,
            platform_slug,
        )
        if task_id:
            TaskTracker.update_task_status(
                task_id,
                TaskStatus.FAILURE,
                error=str(exc),
                metadata=metadata,
            )
        raise
