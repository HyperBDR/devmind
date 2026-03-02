"""
Celery tasks for data_collector: run_collect, run_cleanup, run_validate.
All use agentcore-task TaskTracker and report progress/counts in metadata.
"""
import hashlib
import logging
import os
import uuid as uuid_module
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import translation
from django.utils.translation import gettext as _

from celery import current_task
from celery import shared_task
from django.db.models import Prefetch
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from agentcore_task.adapters.django import (
    TaskStatus,
    TaskTracker,
    prevent_duplicate_task,
)

from .models import CollectorConfig, RawDataAttachment, RawDataRecord
from .services.providers import get_provider
from .services.storage import (
    attachment_file_path,
    attachment_file_url,
    ensure_attachment_dir,
)

logger = logging.getLogger(__name__)

MODULE_NAME = "data_collector"


def _sync_attachments_for_record(provider, auth_config, raw_record):
    """
    Sync attachments for a raw record: download new/updated, remove obsolete.
    Returns (synced_count, removed_count).
    """
    try:
        att_list = provider.fetch_attachments(auth_config, raw_record)
    except Exception as e:
        rec_id = raw_record.uuid
        logger.warning(
            f"[data_collector] fetch_attachments failed record={rec_id}: {e}"
        )
        return 0, 0

    current_source_ids = set()
    for att_meta in att_list:
        sid = att_meta.get("source_file_id")
        if sid is not None:
            current_source_ids.add(str(sid)[:255])

    synced = 0
    for att_meta in att_list:
        source_file_id = att_meta.get("source_file_id")
        if source_file_id is not None:
            source_file_id = str(source_file_id)[:255]
        content = provider.download_attachment_content(auth_config, att_meta)
        if not content:
            continue
        file_name = (
            (att_meta.get("file_name") or "attachment").strip()
            or "attachment"
        )
        file_name = file_name[:512]
        file_md5 = hashlib.md5(content).hexdigest()
        file_size = att_meta.get("file_size")
        if file_size is None:
            file_size = len(content)
        file_type = (att_meta.get("file_type") or "")[:128]
        src_created = att_meta.get("source_created_at")
        src_updated = att_meta.get("source_updated_at")
        if isinstance(src_created, str):
            src_created = parse_datetime(src_created)
        if isinstance(src_updated, str):
            src_updated = parse_datetime(src_updated)

        ensure_attachment_dir(raw_record)
        attachment_uuid = None
        existing_att = None
        if source_file_id:
            existing_att = RawDataAttachment.objects.filter(
                raw_record=raw_record,
                source_file_id=source_file_id,
            ).first()
            if existing_att:
                attachment_uuid = str(existing_att.uuid)
        if attachment_uuid is None:
            attachment_uuid = str(uuid_module.uuid4())

        path = attachment_file_path(raw_record, attachment_uuid)
        try:
            with open(path, "wb") as f:
                f.write(content)
        except OSError as e:
            p = path[:80]
            logger.warning(
                f"[data_collector] write attachment failed path={p}: {e}"
            )
            continue
        url = attachment_file_url(raw_record, attachment_uuid)

        defaults = {
            "file_name": file_name,
            "file_path": path[:1024],
            "file_url": url[:1024],
            "file_type": file_type,
            "file_size": file_size,
            "file_md5": file_md5,
            "source_created_at": src_created,
            "source_updated_at": src_updated,
        }
        if source_file_id:
            if existing_att:
                RawDataAttachment.objects.filter(
                    pk=existing_att.pk
                ).update(**defaults)
            else:
                RawDataAttachment.objects.create(
                    raw_record=raw_record,
                    source_file_id=source_file_id,
                    uuid=attachment_uuid,
                    **defaults,
                )
        else:
            RawDataAttachment.objects.create(
                raw_record=raw_record,
                source_file_id=None,
                uuid=attachment_uuid,
                **defaults,
            )
        synced += 1

    if current_source_ids:
        qs = RawDataAttachment.objects.filter(raw_record=raw_record)
        to_remove = qs.exclude(
            source_file_id__in=current_source_ids
        ).exclude(
            source_file_id__isnull=True
        ).exclude(source_file_id="")
    else:
        to_remove = RawDataAttachment.objects.filter(raw_record=raw_record)
    removed = 0
    for att in to_remove:
        if att.file_path and os.path.isfile(att.file_path):
            try:
                os.remove(att.file_path)
            except OSError as e:
                logger.warning(
                    f"[data_collector] remove attachment file failed "
                    f"path={att.file_path[:80]}: {e}"
                )
        att.delete()
        removed += 1
    if removed:
        rec_id = raw_record.uuid
        logger.info(
            f"[data_collector] attachments removed for record={rec_id}: "
            f"count={removed}"
        )

    return synced, removed


def _register_and_start(task_id, config_uuid, lang=None):
    if task_id:
        TaskTracker.register_task(
            task_id=task_id,
            task_name=MODULE_NAME + ".tasks.run_collect",
            module=MODULE_NAME,
            task_kwargs={"config_uuid": config_uuid},
            metadata={"config_uuid": config_uuid},
            initial_status=TaskStatus.STARTED,
        )
        with translation.override(lang or settings.LANGUAGE_CODE):
            msg = _("Start collection")
        TaskTracker.update_task_status(
            task_id,
            TaskStatus.STARTED,
            metadata={
                "progress_percent": 0,
                "progress_message": msg,
                "progress_step": "start",
                "config_uuid": config_uuid,
            },
        )


@shared_task(name="data_collector.tasks.run_collect")
@prevent_duplicate_task(
    "data_collector_run_collect", lock_param="config_uuid", timeout=3600
)
def run_collect(
    config_uuid: str,
    start_time: str | None = None,
    end_time: str | None = None,
):
    """
    Collect raw data for config. Optional start_time/end_time (ISO); else
    first run uses initial_range, later last_success_collect_at (1d
    lookback).
    """
    task_id = current_task.request.id if current_task else None
    logger.info(
        f"[data_collector] run_collect started, config_uuid={config_uuid}, "
        f"task_id={task_id}, start_time={start_time}, end_time={end_time}"
    )
    try:
        config = CollectorConfig.objects.get(uuid=config_uuid)
    except CollectorConfig.DoesNotExist:
        logger.warning(
            f"[data_collector] run_collect config not found: "
            f"config_uuid={config_uuid}"
        )
        if task_id:
            TaskTracker.update_task_status(
                task_id,
                TaskStatus.FAILURE,
                error="CollectorConfig not found",
                metadata={"config_uuid": config_uuid},
            )
        return {"success": False, "error": "Config not found"}

    value = config.value or {}
    lang = value.get("language") or settings.LANGUAGE_CODE
    _register_and_start(task_id, config_uuid, lang)

    logger.info(
        f"[data_collector] run_collect config loaded: "
        f"platform={config.platform}, user_id={config.user_id}, "
        f"config_uuid={config_uuid}"
    )
    runtime = value.get("runtime_state") or {}
    initial_range = value.get("initial_range") or "1m"
    now = timezone.now()

    if start_time and end_time:
        start_dt = parse_datetime(start_time)
        end_dt = parse_datetime(end_time)
        if start_dt is None or end_dt is None:
            if task_id:
                err = "Invalid start_time or end_time format."
                TaskTracker.update_task_status(
                    task_id,
                    TaskStatus.FAILURE,
                    error=err,
                    metadata={"config_uuid": config_uuid},
                )
            return {
                "success": False,
                "error": "Invalid start_time or end_time format.",
            }
        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt)
        if timezone.is_naive(end_dt):
            end_dt = timezone.make_aware(end_dt)
        if start_dt >= end_dt:
            if task_id:
                err = "start_time must be before end_time."
                TaskTracker.update_task_status(
                    task_id,
                    TaskStatus.FAILURE,
                    error=err,
                    metadata={"config_uuid": config_uuid},
                )
            return {
                "success": False,
                "error": "start_time must be before end_time.",
            }
        logger.info(
            f"[data_collector] run_collect manual range, "
            f"start={start_dt}, end={end_dt}"
        )
        start_time = start_dt
        end_time = end_dt
    elif runtime.get("first_collect_at") is None:
        if initial_range == "1m":
            start_time = now - timedelta(days=30)
        elif initial_range == "3m":
            start_time = now - timedelta(days=90)
        else:
            start_time = now - timedelta(days=30)
        end_time = now
        logger.info(
            f"[data_collector] run_collect first run, "
            f"initial_range={initial_range}, start={start_time}, "
            f"end={end_time}"
        )
    else:
        last_ok = runtime.get("last_success_collect_at")
        if last_ok:
            start_time = (
                parse_datetime(last_ok)
                if isinstance(last_ok, str)
                else last_ok
            )
        else:
            start_time = now - timedelta(days=30)
        min_lookback_days = 1
        min_start = now - timedelta(days=min_lookback_days)
        if start_time > min_start:
            start_time = min_start
            logger.info(
                f"[data_collector] run_collect incremental: start capped "
                f"min lookback {min_lookback_days}d, start_time={start_time}"
            )
        end_time = now
        logger.info(
            f"[data_collector] run_collect incremental, "
            f"start_time={start_time}, end_time={end_time}"
        )

    if task_id:
        with translation.override(lang):
            msg = _("Fetching raw data")
        TaskTracker.update_task_status(
            task_id,
            TaskStatus.STARTED,
            metadata={
                "progress_percent": 10,
                "progress_message": msg,
                "progress_step": "collect",
                "config_uuid": config_uuid,
            },
        )

    provider_cls = get_provider(config.platform)
    records_created = 0
    records_updated = 0
    records_skipped_no_sid = 0
    records_skipped_unchanged = 0
    if provider_cls:
        provider = provider_cls()
        auth_config = value.get("auth") or {}
        logger.info(
            f"[data_collector] run_collect calling provider.collect "
            f"platform={config.platform}, start={start_time}, end={end_time}"
        )
        try:
            proj_keys = value.get("project_keys") or []
            items = provider.collect(
                auth_config,
                start_time,
                end_time,
                config.user_id,
                config.platform,
                project_keys=proj_keys,
            )
        except Exception as e:
            logger.exception(
                f"[data_collector] run_collect provider.collect failed: {e}"
            )
            if task_id:
                TaskTracker.update_task_status(
                    task_id,
                    TaskStatus.FAILURE,
                    error=str(e),
                    metadata={"config_uuid": config_uuid},
                )
            raise

        n_items = len(items) if items is not None else 0
        logger.info(
            f"[data_collector] run_collect provider returned count="
            f"{n_items}, config_uuid={config_uuid}"
        )
        if not items:
            logger.info(
                "[data_collector] run_collect no items to persist "
                "(provider returned empty list)"
            )

        persisted_records = []
        with transaction.atomic():
            for item in items:
                sid = item.get("source_unique_id")
                if not sid:
                    records_skipped_no_sid += 1
                    continue
                raw_data = item.get("raw_data") or {}
                filter_metadata = item.get("filter_metadata") or {}
                data_hash = item.get("data_hash") or ""
                source_created_at = item.get("source_created_at")
                source_updated_at = item.get("source_updated_at")

                rec, created = RawDataRecord.objects.get_or_create(
                    user_id=config.user_id,
                    platform=config.platform,
                    source_unique_id=sid,
                    defaults={
                        "raw_data": raw_data,
                        "filter_metadata": filter_metadata,
                        "data_hash": data_hash,
                        "source_created_at": source_created_at,
                        "source_updated_at": source_updated_at,
                        "first_collected_at": now,
                        "last_collected_at": now,
                    },
                )
                if created:
                    records_created += 1
                    persisted_records.append(rec)
                else:
                    if rec.data_hash != data_hash:
                        rec.raw_data = raw_data
                        rec.filter_metadata = filter_metadata
                        rec.data_hash = data_hash
                        rec.source_created_at = source_created_at
                        rec.source_updated_at = source_updated_at
                        rec.save(
                            update_fields=[
                                "raw_data",
                                "filter_metadata",
                                "data_hash",
                                "source_created_at",
                                "source_updated_at",
                                "updated_at",
                            ]
                        )
                        records_updated += 1
                        persisted_records.append(rec)
                    else:
                        records_skipped_unchanged += 1
                    rec.last_collected_at = now
                    rec.save(
                        update_fields=["last_collected_at", "updated_at"]
                    )

            runtime["last_collect_start_at"] = now.isoformat()
            runtime["last_collect_end_at"] = now.isoformat()
            runtime["last_success_collect_at"] = now.isoformat()
            if runtime.get("first_collect_at") is None:
                runtime["first_collect_at"] = now.isoformat()
            value["runtime_state"] = runtime
            config.value = value
            config.save(update_fields=["value", "updated_at"])

        attachments_synced = 0
        attachments_removed = 0
        for rec in persisted_records:
            s, r = _sync_attachments_for_record(provider, auth_config, rec)
            attachments_synced += s
            attachments_removed += r

        backfill_records = []
        persisted_ids = {rec.pk for rec in persisted_records}
        if provider and getattr(
            provider, "download_attachment_content", None
        ):
            qs = RawDataRecord.objects.filter(
                user_id=config.user_id,
                platform=config.platform,
            ).prefetch_related(
                Prefetch(
                    "attachments",
                    queryset=RawDataAttachment.objects.only("id"),
                )
            )
            for rec in qs:
                raw_data = rec.raw_data
                raw_attachments = (
                    raw_data.get("attachments")
                    if isinstance(raw_data, dict)
                    else []
                )
                is_list = isinstance(raw_attachments, list)
                if not is_list or len(raw_attachments) == 0:
                    continue
                if rec.pk in persisted_ids:
                    continue
                if rec.attachments.count() < len(raw_attachments):
                    backfill_records.append(rec)
            for rec in backfill_records:
                s, r = _sync_attachments_for_record(
                    provider, auth_config, rec
                )
                attachments_synced += s
                attachments_removed += r

        if attachments_synced or attachments_removed:
            n_bf = len(backfill_records)
            logger.info(
                f"[data_collector] run_collect attachments: "
                f"synced={attachments_synced}, "
                f"removed={attachments_removed}, backfill={n_bf}, "
                f"config_uuid={config_uuid}"
            )

        logger.info(
            f"[data_collector] run_collect persist done: "
            f"created={records_created}, updated={records_updated}, "
            f"skipped_no_sid={records_skipped_no_sid}, "
            f"skipped_unchanged={records_skipped_unchanged}, "
            f"config_uuid={config_uuid}"
        )
    else:
        logger.warning(
            f"[data_collector] run_collect no provider for platform="
            f"{config.platform}, config_uuid={config_uuid}"
        )

    if task_id:
        n_collected = records_created + records_updated
        with translation.override(lang):
            msg = _("Collection done")
        TaskTracker.update_task_status(
            task_id,
            TaskStatus.SUCCESS,
            result={
                "records_created": records_created,
                "records_updated": records_updated,
                "records_collected": n_collected,
            },
            metadata={
                "progress_percent": 100,
                "progress_message": msg,
                "progress_step": "done",
                "config_uuid": config_uuid,
                "records_created": records_created,
                "records_updated": records_updated,
                "records_collected": n_collected,
            },
        )

    logger.info(
        f"[data_collector] run_collect finished success: "
        f"created={records_created}, updated={records_updated}, "
        f"config_uuid={config_uuid}"
    )
    return {
        "success": True,
        "records_created": records_created,
        "records_updated": records_updated,
    }


@shared_task(name="data_collector.tasks.run_cleanup")
@prevent_duplicate_task(
    "data_collector_run_cleanup", lock_param="config_uuid", timeout=3600
)
def run_cleanup(config_uuid: str):
    """
    Delete expired RawDataRecords and attachments for this config;
    update runtime_state.last_cleanup_at. Uses TaskTracker and metadata.
    """
    task_id = current_task.request.id if current_task else None
    if task_id:
        TaskTracker.register_task(
            task_id=task_id,
            task_name="data_collector.tasks.run_cleanup",
            module=MODULE_NAME,
            task_kwargs={"config_uuid": config_uuid},
            metadata={"config_uuid": config_uuid},
            initial_status=TaskStatus.STARTED,
        )
        with translation.override(settings.LANGUAGE_CODE):
            msg = _("Start cleanup")
        TaskTracker.update_task_status(
            task_id,
            TaskStatus.STARTED,
            metadata={
                "progress_percent": 0,
                "progress_message": msg,
                "progress_step": "cleanup",
                "config_uuid": config_uuid,
            },
        )

    try:
        config = CollectorConfig.objects.get(uuid=config_uuid)
    except CollectorConfig.DoesNotExist:
        if task_id:
            TaskTracker.update_task_status(
                task_id,
                TaskStatus.FAILURE,
                error="CollectorConfig not found",
            )
        return {"success": False, "error": "Config not found"}

    value = config.value or {}
    lang = value.get("language") or settings.LANGUAGE_CODE
    retention_days = value.get("retention_days") or 180
    cutoff = timezone.now() - timedelta(days=retention_days)
    runtime = value.get("runtime_state") or {}

    with transaction.atomic():
        to_delete = RawDataRecord.objects.filter(
            user_id=config.user_id,
            platform=config.platform,
            last_collected_at__lt=cutoff,
        )
        count = to_delete.count()
        for rec in to_delete:
            for att in rec.attachments.all():
                if att.file_path:
                    try:
                        if os.path.isfile(att.file_path):
                            os.remove(att.file_path)
                    except OSError:
                        pass
            rec.delete()
        runtime["last_cleanup_at"] = timezone.now().isoformat()
        value["runtime_state"] = runtime
        config.value = value
        config.save(update_fields=["value", "updated_at"])

    if task_id:
        with translation.override(lang):
            msg = _("Cleanup done")
        TaskTracker.update_task_status(
            task_id,
            TaskStatus.SUCCESS,
            result={"records_deleted": count},
            metadata={
                "progress_percent": 100,
                "progress_message": msg,
                "records_deleted": count,
                "config_uuid": config_uuid,
            },
        )

    return {"success": True, "records_deleted": count}


@shared_task(name="data_collector.tasks.run_validate")
def run_validate(config_uuid: str, start_time: str, end_time: str):
    """
    Validate records in time range; mark missing on platform as is_deleted.
    Uses TaskTracker and metadata.
    """
    task_id = current_task.request.id if current_task else None
    if task_id:
        TaskTracker.register_task(
            task_id=task_id,
            task_name="data_collector.tasks.run_validate",
            module=MODULE_NAME,
            task_kwargs={
                "config_uuid": config_uuid,
                "start_time": start_time,
                "end_time": end_time,
            },
            metadata={"config_uuid": config_uuid},
            initial_status=TaskStatus.STARTED,
        )

    try:
        config = CollectorConfig.objects.get(uuid=config_uuid)
    except CollectorConfig.DoesNotExist:
        if task_id:
            TaskTracker.update_task_status(
                task_id,
                TaskStatus.FAILURE,
                error="CollectorConfig not found",
            )
        return {"success": False, "error": "Config not found"}

    st = (
        parse_datetime(start_time)
        if isinstance(start_time, str)
        else start_time
    )
    et = (
        parse_datetime(end_time)
        if isinstance(end_time, str)
        else end_time
    )
    records = list(
        RawDataRecord.objects.filter(
            user_id=config.user_id,
            platform=config.platform,
            last_collected_at__gte=st,
            last_collected_at__lte=et,
            is_deleted=False,
        ).values_list("source_unique_id", flat=True)
    )

    provider_cls = get_provider(config.platform)
    missing = []
    if provider_cls:
        provider = provider_cls()
        auth_config = (config.value or {}).get("auth") or {}
        missing = provider.validate(
            auth_config,
            st,
            et,
            config.user_id,
            config.platform,
            list(records),
        )

    with transaction.atomic():
        RawDataRecord.objects.filter(
            user_id=config.user_id,
            platform=config.platform,
            source_unique_id__in=missing,
        ).update(is_deleted=True)

    if task_id:
        TaskTracker.update_task_status(
            task_id,
            TaskStatus.SUCCESS,
            result={
                "records_validated": len(records),
                "records_marked_deleted": len(missing),
            },
            metadata={
                "progress_percent": 100,
                "records_validated": len(records),
                "records_marked_deleted": len(missing),
                "config_uuid": config_uuid,
            },
        )

    return {
        "success": True,
        "records_validated": len(records),
        "records_marked_deleted": len(missing),
    }
