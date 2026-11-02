"""Persist automatic refresh scheduling and inspection progress."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agione_ops", "0017_notificationissue")]

    operations = [
        migrations.AddField(
            model_name="notificationrules",
            name="last_auto_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notificationrules",
            name="last_auto_success_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notificationrules",
            name="next_auto_refresh_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notificationrules",
            name="last_inspection_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notificationrules",
            name="last_auto_status",
            field=models.CharField(default="idle", max_length=24),
        ),
        migrations.AddField(
            model_name="notificationrules",
            name="last_auto_error_code",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="notificationdelivery",
            name="kind",
            field=models.CharField(
                choices=[
                    ("alert", "Alert"),
                    ("recovery", "Recovery"),
                    ("recovered_history", "Recovered history"),
                ],
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="nativeaccountscope",
            name="error_code",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
    ]
