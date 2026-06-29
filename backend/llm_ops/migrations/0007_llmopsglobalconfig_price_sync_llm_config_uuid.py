import json

from django.db import migrations, models
from django.db.utils import OperationalError, ProgrammingError


LEGACY_OFFICIAL_COLLECT_TASK_NAME = "llm_ops_official_collect"
MODEL_PRICE_SYNC_AGENT_TASK_NAME = "llm_ops_model_price_sync_agent"
MODEL_PRICE_SYNC_AGENT_TASK = "llm_ops.tasks.run_model_price_sync_agent"
PRICE_SOURCE_TASK_PREFIX = "llm_ops_price_source_collect_"
ALIYUN_PRICING_SOURCE_URL = (
    "https://help.aliyun.com/zh/model-studio/model-pricing"
)
ALIYUN_LEGACY_PRICING_SOURCE_URLS = (
    "https://help.aliyun.com/zh/model-studio/model-price",
    "https://help.aliyun.com/zh/model-studio/models",
)


def migrate_aliyun_price_source_urls(apps, schema_editor):
    """Move persisted Aliyun official sources to the pricing page."""
    price_source = apps.get_model("llm_ops", "PriceCollectionSource")
    price_source.objects.filter(
        slug__in=("aliyun-official", "aliyun-wanx-official"),
        endpoint_url__in=ALIYUN_LEGACY_PRICING_SOURCE_URLS,
    ).update(endpoint_url=ALIYUN_PRICING_SOURCE_URL)


def migrate_legacy_price_sync_beat_tasks(apps, schema_editor):
    """Disable legacy price sync beat rows during the Agent migration."""
    try:
        periodic_task = apps.get_model("django_celery_beat", "PeriodicTask")
    except LookupError:
        return

    try:
        delete_legacy_price_source_tasks(periodic_task)
        legacy = periodic_task.objects.filter(
            name=LEGACY_OFFICIAL_COLLECT_TASK_NAME,
        ).first()
    except (OperationalError, ProgrammingError):
        return

    if legacy is not None:
        defaults = {
            "task": MODEL_PRICE_SYNC_AGENT_TASK,
            "args": json.dumps([]),
            "kwargs": json.dumps({"source_ids": None, "verify_source": True}),
            "queue": legacy.queue,
            "enabled": legacy.enabled,
        }
        for field in ("crontab", "interval", "solar", "clocked"):
            field_id = f"{field}_id"
            if hasattr(legacy, field_id) and getattr(legacy, field_id):
                defaults[field_id] = getattr(legacy, field_id)
        periodic_task.objects.get_or_create(
            name=MODEL_PRICE_SYNC_AGENT_TASK_NAME,
            defaults=defaults,
        )

        legacy.enabled = False
        legacy.save(update_fields=["enabled"])

    update_periodic_tasks_changed(apps)


def delete_legacy_price_source_tasks(periodic_task):
    """Delete managed per-source price sync tasks from old config saves."""
    task_names = periodic_task.objects.filter(
        name__startswith=PRICE_SOURCE_TASK_PREFIX,
    ).values_list("name", flat=True)
    obsolete_task_names = []
    for task_name in task_names:
        suffix = task_name[len(PRICE_SOURCE_TASK_PREFIX) :]
        try:
            int(suffix)
        except ValueError:
            continue
        obsolete_task_names.append(task_name)
    if obsolete_task_names:
        periodic_task.objects.filter(name__in=obsolete_task_names).delete()


def update_periodic_tasks_changed(apps):
    """Notify django-celery-beat that migration changed beat rows."""
    try:
        periodic_tasks = apps.get_model(
            "django_celery_beat",
            "PeriodicTasks",
        )
        periodic_tasks.update_changed()
    except (AttributeError, LookupError, OperationalError, ProgrammingError):
        return


class Migration(migrations.Migration):

    dependencies = [
        ("llm_ops", "0006_alter_llmopsglobalconfig_feishu_app_secret"),
    ]

    operations = [
        migrations.AddField(
            model_name="llmopsglobalconfig",
            name="price_sync_llm_config_uuid",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.RunPython(
            migrate_aliyun_price_source_urls,
            migrations.RunPython.noop,
        ),
        migrations.RunPython(
            migrate_legacy_price_sync_beat_tasks,
            migrations.RunPython.noop,
        ),
    ]
