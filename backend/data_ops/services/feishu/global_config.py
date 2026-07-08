from __future__ import annotations

import os

from django.db.utils import OperationalError, ProgrammingError

from data_ops.models import DataOpsGlobalConfig


def get_data_ops_global_config() -> DataOpsGlobalConfig | None:
    try:
        return DataOpsGlobalConfig.get_solo()
    except (OperationalError, ProgrammingError, RuntimeError):
        return None


def get_feishu_credentials() -> tuple[str, str]:
    config = get_data_ops_global_config()
    if config and config.feishu_app_id and config.feishu_app_secret:
        return config.feishu_app_id, config.get_feishu_app_secret()

    return (
        os.getenv("DATA_OPS_FEISHU_APP_ID", ""),
        os.getenv("DATA_OPS_FEISHU_APP_SECRET", ""),
    )


def get_feishu_date_timezone_name() -> str:
    config = get_data_ops_global_config()
    if config and config.feishu_date_timezone:
        return config.feishu_date_timezone
    return os.getenv("DATA_OPS_FEISHU_DATE_TIMEZONE", "Asia/Shanghai")


def get_active_sync_job_timeout_hours() -> int:
    config = get_data_ops_global_config()
    if config and config.active_sync_job_timeout_hours:
        return config.active_sync_job_timeout_hours
    try:
        return int(os.getenv("DATA_OPS_ACTIVE_SYNC_JOB_TIMEOUT_HOURS", "3"))
    except ValueError:
        return 3
