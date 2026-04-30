import logging

from django.db import transaction
from django.utils import timezone

from ..client import HyperBDRClient, parse_remote_datetime
from ..models import CollectionTask, DataSource, License, Tenant

logger = logging.getLogger(__name__)


def _to_int(value, default=0):
    try:
        v = int(value)
        return max(v, 0)
    except Exception:
        return default


def _tenant_defaults(payload):
    configs = payload.get("configs") or {}
    return {
        "name": payload.get("name") or payload.get("tenant_name") or "",
        "description": payload.get("description") or "",
        "status": payload.get("status") or "",
        "agent_enabled": configs.get("agent") == "enabled",
        "trialed": bool(configs.get("trialed", False)),
        "migration_way": configs.get("migration_way") or "",
        "created_at": parse_remote_datetime(payload.get("created_at")),
        "last_collected_at": timezone.now(),
    }


def _license_entries(payload):
    entries = (payload.get("data") or {}).get("pages") or (payload.get("data") or {}).get("licenses") or payload.get("data") or []
    if isinstance(entries, dict):
        entries = [entries]
    return entries


def _collect_all_licenses_for_scene(client, scene, page_size=500):
    """
    Collect all licenses for a scene in batch, without filtering by enterprise_id.
    Returns a dict mapping enterprise_id -> list of license items.
    """
    all_licenses_by_tenant = {}
    page = 1
    while True:
        payload = client.get_all_licenses_statistics(scene=scene, page=page, page_size=page_size)
        data = payload.get("data") or {}
        entries = data.get("pages") or data.get("licenses") or data.get("list") or []
        if isinstance(entries, dict):
            entries = [entries]
        if not entries:
            break
        for item in entries:
            enterprise_id = str(item.get("enterprise_id") or item.get("id") or "")
            if not enterprise_id:
                continue
            if enterprise_id not in all_licenses_by_tenant:
                all_licenses_by_tenant[enterprise_id] = []
            all_licenses_by_tenant[enterprise_id].append(item)
        if len(entries) < page_size:
            break
        page += 1
    logger.info(
        "[HyperBDR Collect] Batch licenses collected: scene=%s, tenant_count=%s",
        scene,
        len(all_licenses_by_tenant),
    )
    return all_licenses_by_tenant


def collect_data_source(data_source_id, task_id=None, trigger_mode="manual", celery_task_id=""):
    logger.info(
        "[HyperBDR Collect] Starting: data_source_id=%s, task_id=%s, trigger_mode=%s",
        data_source_id,
        task_id,
        trigger_mode,
    )
    source = DataSource.objects.get(pk=data_source_id)
    task = None
    if task_id:
        task = CollectionTask.objects.get(pk=task_id)
        task.status = CollectionTask.STATUS_RUNNING
        task.celery_task_id = celery_task_id or task.celery_task_id
        task.trigger_mode = trigger_mode
        task.save(update_fields=["status", "celery_task_id", "trigger_mode", "updated_at"])
    else:
        task = CollectionTask.objects.create(
            data_source=source,
            status=CollectionTask.STATUS_RUNNING,
            celery_task_id=celery_task_id,
            trigger_mode=trigger_mode,
            start_time=timezone.now(),
        )

    password = source.password
    tenant_count = 0
    license_count = 0
    try:
        with HyperBDRClient(
            api_url=source.api_url,
            username=source.username,
            password=password,
            timeout=source.api_timeout,
            retry_count=source.api_retry_count,
            retry_delay=source.api_retry_delay,
        ) as client:
            # Step 1: Get all tenants (with pagination)
            all_tenant_rows = []
            page = 1
            while True:
                payload = client.get_tenants(page=page, page_size=1000)
                tenant_rows = ((payload.get("data") or {}).get("pages") or [])
                if not tenant_rows:
                    break
                all_tenant_rows.extend(tenant_rows)
                if len(tenant_rows) < 1000:
                    break
                page += 1
            current_tenant_ids = set()

            # Step 2: Batch collect all licenses for both DR and Migration scenes
            all_dr_licenses = _collect_all_licenses_for_scene(client, "dr")
            all_migration_licenses = _collect_all_licenses_for_scene(client, "migration")

            # Step 3: Process all data in a single transaction
            with transaction.atomic():
                for tenant_payload in all_tenant_rows:
                    source_tenant_id = str(tenant_payload.get("id") or "").strip()
                    if not source_tenant_id:
                        continue
                    current_tenant_ids.add(source_tenant_id)
                    tenant, _ = Tenant.objects.update_or_create(
                        data_source=source,
                        source_tenant_id=source_tenant_id,
                        defaults=_tenant_defaults(tenant_payload),
                    )
                    tenant_count += 1

                    seen_license_scenes = set()
                    now = timezone.now()

                    # Process DR licenses
                    for item in all_dr_licenses.get(source_tenant_id, []):
                        seen_license_scenes.add("dr")
                        License.objects.update_or_create(
                            data_source=source,
                            tenant=tenant,
                            scene="dr",
                            defaults={
                                "total_amount": _to_int(item.get("total_amount", item.get("amount", 0))),
                                "total_used": _to_int(item.get("total_used", item.get("used", 0))),
                                "total_unused": _to_int(item.get("total_unused", item.get("unused", 0))),
                                "start_at": parse_remote_datetime(item.get("start_at")),
                                "expire_at": parse_remote_datetime(item.get("expire_at")),
                                "last_collected_at": now,
                            },
                        )
                        license_count += 1

                    # Process Migration licenses
                    for item in all_migration_licenses.get(source_tenant_id, []):
                        seen_license_scenes.add("migration")
                        License.objects.update_or_create(
                            data_source=source,
                            tenant=tenant,
                            scene="migration",
                            defaults={
                                "total_amount": _to_int(item.get("total_amount", item.get("amount", 0))),
                                "total_used": _to_int(item.get("total_used", item.get("used", 0))),
                                "total_unused": _to_int(item.get("total_unused", item.get("unused", 0))),
                                "start_at": parse_remote_datetime(item.get("start_at")),
                                "expire_at": parse_remote_datetime(item.get("expire_at")),
                                "last_collected_at": now,
                            },
                        )
                        license_count += 1

                    # Delete licenses for scenes not in seen_license_scenes
                    if seen_license_scenes:
                        License.objects.filter(
                            data_source=source,
                            tenant=tenant,
                        ).exclude(scene__in=seen_license_scenes).delete()

                # Delete tenants no longer in the remote data
                Tenant.objects.filter(data_source=source).exclude(
                    source_tenant_id__in=current_tenant_ids
                ).delete()

        end_time = timezone.now()
        duration = round((end_time - task.start_time).total_seconds(), 2)
        CollectionTask.objects.filter(pk=task.pk).update(
            status=CollectionTask.STATUS_COMPLETED,
            end_time=end_time,
            duration_seconds=duration,
            total_tenants=tenant_count,
            total_licenses=license_count,
            error_message="",
        )
        return {
            "task_id": task.pk,
            "status": CollectionTask.STATUS_COMPLETED,
            "total_tenants": tenant_count,
            "total_licenses": license_count,
        }
    except Exception as exc:
        end_time = timezone.now()
        duration = round((end_time - task.start_time).total_seconds(), 2)
        CollectionTask.objects.filter(pk=task.pk).update(
            status=CollectionTask.STATUS_FAILED,
            end_time=end_time,
            duration_seconds=duration,
            total_tenants=tenant_count,
            total_licenses=license_count,
            error_message=str(exc),
        )
        logger.exception("HyperBDR data collection failed for data source %s", data_source_id)
        raise


def collect_due_data_sources():
    """
    Return all active data source IDs for full data collection.
    Ignores time interval check to force full sync on every run.
    """
    return list(DataSource.objects.filter(is_active=True).values_list("id", flat=True))
