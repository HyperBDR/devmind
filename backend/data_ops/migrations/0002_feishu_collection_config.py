import uuid

import django.utils.timezone
from django.db import migrations, models

from data_ops.models import default_feishu_required_permissions


class Migration(migrations.Migration):
    dependencies = [
        ("data_ops", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FeishuBitableCollectionConfig",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("source_key", models.CharField(max_length=50)),
                ("table_key", models.CharField(max_length=100)),
                (
                    "source_name",
                    models.CharField(blank=True, max_length=255),
                ),
                (
                    "table_name",
                    models.CharField(blank=True, max_length=255),
                ),
                ("app_token", models.CharField(max_length=100)),
                ("table_id", models.CharField(max_length=100)),
                ("is_enabled", models.BooleanField(default=True)),
                (
                    "sync_frequency",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("hourly", "Hourly"),
                            ("daily", "Daily"),
                            ("weekly", "Weekly"),
                        ],
                        default="daily",
                        max_length=20,
                    ),
                ),
                (
                    "required_permissions",
                    models.JSONField(
                        blank=True,
                        default=default_feishu_required_permissions,
                    ),
                ),
                (
                    "expected_min_records",
                    models.IntegerField(blank=True, null=True),
                ),
                (
                    "last_preflight_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "last_manual_trigger_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "last_scheduled_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "created_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["source_key", "table_key"],
                        name="data_ops_fe_source__706c0a_idx",
                    ),
                    models.Index(
                        fields=["is_enabled", "sync_frequency"],
                        name="data_ops_fe_is_enab_76219e_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=["source_key", "table_key"],
                        name="uq_data_ops_feishu_collection_config",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="syncjob",
            name="table_key",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddIndex(
            model_name="syncjob",
            index=models.Index(
                fields=["source_key", "table_key", "started_at"],
                name="data_ops_sy_source__507599_idx",
            ),
        ),
    ]
