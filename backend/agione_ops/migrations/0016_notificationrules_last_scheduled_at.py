"""Track the last successful custom-schedule dispatch."""

from django.db import migrations, models
from django.utils import timezone


def mark_existing_rules_scheduled(apps, schema_editor):
    """Avoid an unexpected catch-up run immediately after deployment."""
    rules = apps.get_model("agione_ops", "NotificationRules")
    rules.objects.using(schema_editor.connection.alias).filter(
        last_scheduled_at__isnull=True,
    ).update(
        last_scheduled_at=timezone.now(),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("agione_ops", "0015_notification_delivery"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationrules",
            name="last_scheduled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(
            mark_existing_rules_scheduled,
            migrations.RunPython.noop,
        ),
    ]
