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
        app_secret = config.get_feishu_app_secret()
        if app_secret:
            return config.feishu_app_id, app_secret

    environment_pairs = (
        ("DATA_OPS_FEISHU_APP_ID", "DATA_OPS_FEISHU_APP_SECRET"),
        ("FEISHU_APP_ID", "FEISHU_APP_SECRET"),
        ("APP_ID", "APP_SECRET"),
    )
    for app_id_name, app_secret_name in environment_pairs:
        app_id = os.getenv(app_id_name, "")
        app_secret = os.getenv(app_secret_name, "")
        if app_id and app_secret:
            return app_id, app_secret

    return "", ""


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
