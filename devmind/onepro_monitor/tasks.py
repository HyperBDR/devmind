import logging

from celery import current_task, shared_task

from .services.collector import collect_data_source, collect_due_data_sources

logger = logging.getLogger(__name__)


@shared_task(name="onepro_monitor.tasks.run_collection_for_data_source")
def run_collection_for_data_source(data_source_id, task_id=None, trigger_mode="manual"):
    celery_task_id = current_task.request.id if current_task else ""
    logger.info(
        "Running OnePro Monitor collection for data_source_id=%s task_id=%s trigger_mode=%s",
        data_source_id,
        task_id,
        trigger_mode,
    )
    return collect_data_source(
        data_source_id=data_source_id,
        task_id=task_id,
        trigger_mode=trigger_mode,
        celery_task_id=celery_task_id,
    )


@shared_task(name="onepro_monitor.tasks.collect_due_sources")
def collect_due_sources():
    due_source_ids = collect_due_data_sources()
    scheduled = []
    for data_source_id in due_source_ids:
        result = run_collection_for_data_source.delay(data_source_id, None, "scheduled")
        scheduled.append({"data_source_id": data_source_id, "celery_task_id": result.id})
    return {"scheduled": scheduled, "count": len(scheduled)}
