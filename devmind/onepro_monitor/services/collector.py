import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from ..client import OneProClient, parse_remote_datetime
from ..encryption import encryption_service
from ..models import CollectionTask, DataSource, Host, License, Tenant

logger = logging.getLogger(__name__)


def _to_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _to_decimal(value, default="0"):
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def _tenant_defaults(payload):
    configs = payload.get("configs") or {}
    return {
        "name": payload.get("name") or payload.get("tenant_name") or "",
        "description": payload.get("description") or "",
        "status": payload.get("status") or "",
        "agent_enabled": configs.get("agent") == "enabled",
        "trialed": bool(configs.get("trialed", False)),
        "migration_way": configs.get("migration_way") or "",
        "last_collected_at": timezone.now(),
    }


def _license_entries(payload):
    entries = (payload.get("data") or {}).get("pages") or (payload.get("data") or {}).get("licenses") or payload.get("data") or []
    if isinstance(entries, dict):
        entries = [entries]
    return entries


def _host_entries(payload):
    return ((payload.get("data") or {}).get("hosts") or [])


def _collect_hosts_for_tenant(client, source, tenant):
    detail = client.get_tenant_detail(tenant.source_tenant_id)
    users = ((detail.get("data") or {}).get("users") or [])
    for user in users:
        user_id = user.get("id")
        if not user_id:
            continue
        try:
            page = 1
            page_size = 200
            collected_hosts = []
            seen_host_ids = set()

            while True:
                payload = client.get_tenant_hosts(
                    project_id=tenant.source_tenant_id,
                    user_id=user_id,
                    scene="dr",
                    page=page,
                    page_size=page_size,
                )
                hosts = _host_entries(payload)
                if not hosts:
                    break

                new_host_count = 0
                for host in hosts:
                    source_host_id = str(host.get("id") or "").strip()
                    if source_host_id and source_host_id in seen_host_ids:
                        continue
                    if source_host_id:
                        seen_host_ids.add(source_host_id)
                    collected_hosts.append(host)
                    new_host_count += 1

                if len(hosts) < page_size or new_host_count == 0:
                    break
                page += 1

            if collected_hosts:
                return collected_hosts
        except Exception as exc:
            logger.warning("Failed to fetch hosts for tenant %s via user %s: %s", tenant.source_tenant_id, user_id, exc)
    return []


def collect_data_source(data_source_id, task_id=None, trigger_mode="manual", celery_task_id=""):
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

    password = encryption_service.decrypt(source.password)
    tenant_count = 0
    license_count = 0
    host_count = 0
    try:
        with OneProClient(
            api_url=source.api_url,
            username=source.username,
            password=password,
            timeout=source.api_timeout,
            retry_count=source.api_retry_count,
            retry_delay=source.api_retry_delay,
        ) as client:
            payload = client.get_tenants(page=1, page_size=1000)
            tenant_rows = ((payload.get("data") or {}).get("pages") or [])
            current_tenant_ids = set()
            current_host_ids = set()

            for tenant_payload in tenant_rows:
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
                license_payload = client.get_tenant_licenses_details(
                    enterprise_id=source_tenant_id,
                    scene="dr",
                    page=1,
                    page_size=100,
                )
                for item in _license_entries(license_payload):
                    scene = item.get("scene") or item.get("apply_scene") or "dr"
                    seen_license_scenes.add(scene)
                    License.objects.update_or_create(
                        data_source=source,
                        tenant=tenant,
                        scene=scene,
                        defaults={
                            "total_amount": _to_int(item.get("total_amount", item.get("amount", 0))),
                            "total_used": _to_int(item.get("total_used", item.get("used", 0))),
                            "total_unused": _to_int(item.get("total_unused", item.get("unused", 0))),
                            "start_at": parse_remote_datetime(item.get("start_at")),
                            "expire_at": parse_remote_datetime(item.get("expire_at")),
                            "last_collected_at": timezone.now(),
                        },
                    )
                    license_count += 1
                if seen_license_scenes:
                    License.objects.filter(
                        data_source=source,
                        tenant=tenant,
                    ).exclude(scene__in=seen_license_scenes).delete()

                hosts = _collect_hosts_for_tenant(client, source, tenant)
                seen_host_ids = set()
                for host_payload in hosts:
                    source_host_id = str(host_payload.get("id") or "").strip()
                    if not source_host_id:
                        continue
                    seen_host_ids.add(source_host_id)
                    current_host_ids.add(source_host_id)
                    Host.objects.update_or_create(
                        data_source=source,
                        source_host_id=source_host_id,
                        defaults={
                            "tenant": tenant,
                            "name": host_payload.get("name") or "",
                            "status": host_payload.get("status") or "",
                            "boot_status": host_payload.get("boot_status") or "",
                            "health_status": host_payload.get("health_status") or "",
                            "os_type": host_payload.get("os_type") or "",
                            "host_type": host_payload.get("host_type") or "",
                            "cpu_num": _to_int(host_payload.get("cpu_num")),
                            "ram_size": _to_decimal(host_payload.get("ram_size", 0)),
                            "license_valid": bool(host_payload.get("license_valid", False)),
                            "error_message": host_payload.get("task_error_description") or host_payload.get("error_message") or "",
                            "last_collected_at": timezone.now(),
                        },
                    )
                    host_count += 1
                Host.objects.filter(
                    data_source=source,
                    tenant=tenant,
                ).exclude(source_host_id__in=seen_host_ids).delete()

            Tenant.objects.filter(data_source=source).exclude(
                source_tenant_id__in=current_tenant_ids
            ).delete()
            source.last_collected_at = timezone.now()
            source.save(update_fields=["last_collected_at", "updated_at"])

        end_time = timezone.now()
        duration = round((end_time - task.start_time).total_seconds(), 2)
        CollectionTask.objects.filter(pk=task.pk).update(
            status=CollectionTask.STATUS_COMPLETED,
            end_time=end_time,
            duration_seconds=duration,
            total_tenants=tenant_count,
            total_licenses=license_count,
            total_hosts=host_count,
            error_message="",
        )
        return {
            "task_id": task.pk,
            "status": CollectionTask.STATUS_COMPLETED,
            "total_tenants": tenant_count,
            "total_licenses": license_count,
            "total_hosts": host_count,
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
            total_hosts=host_count,
            error_message=str(exc),
        )
        logger.exception("OnePro data collection failed for data source %s", data_source_id)
        raise


def collect_due_data_sources():
    now = timezone.now()
    due_source_ids = []
    for source in DataSource.objects.filter(is_active=True):
        if not source.last_collected_at:
            due_source_ids.append(source.id)
            continue
        elapsed = (now - source.last_collected_at).total_seconds()
        if elapsed >= source.collect_interval:
            due_source_ids.append(source.id)
    return due_source_ids
