"""
Celery tasks for SALS: ETL sync from OneProCloud API.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def sync_incidents_task(self, full_sync: bool = False):
    """
    从 OneProCloud API 同步工单数据。
    full_sync=True 时先清空再全量写入，False 时增量更新。
    """
    from .services import etl

    try:
        result = etl.sync_from_api(full_sync=full_sync)
        logger.info("sync_incidents_task result: %s", result)
        return result
    except Exception as exc:
        logger.exception("sync_incidents_task failed")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def sync_companies_task(self):
    """从 OneProCloud API 同步公司数据（按需/增量）"""
    from .services import etl

    try:
        result = etl.sync_companies_from_api()
        logger.info("sync_companies_task result: %s", result)
        return result
    except Exception as exc:
        logger.exception("sync_companies_task failed")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def sync_users_task(self):
    """从 OneProCloud API 同步用户数据（按需/增量）"""
    from .services import etl

    try:
        result = etl.sync_users_from_api()
        logger.info("sync_users_task result: %s", result)
        return result
    except Exception as exc:
        logger.exception("sync_users_task failed")
        raise self.retry(exc=exc, countdown=60)
