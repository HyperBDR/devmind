from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("data_ops", "0003_source_records_is_active"),
    ]

    operations = [
        migrations.CreateModel(
            name="DataOpsGlobalConfig",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "singleton_key",
                    models.PositiveSmallIntegerField(default=1, unique=True),
                ),
                (
                    "feishu_app_id",
                    models.CharField(blank=True, max_length=255),
                ),
                (
                    "feishu_app_secret",
                    models.CharField(blank=True, max_length=255),
                ),
                (
                    "feishu_date_timezone",
                    models.CharField(
                        default="Asia/Shanghai",
                        max_length=64,
                    ),
                ),
                (
                    "active_sync_job_timeout_hours",
                    models.PositiveIntegerField(default=3),
                ),
                (
                    "created_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Data Ops Global Configuration",
                "verbose_name_plural": "Data Ops Global Configuration",
            },
        ),
    ]
