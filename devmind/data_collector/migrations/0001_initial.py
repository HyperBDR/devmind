# Generated manually for data_collector

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CollectorConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "uuid",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        help_text="Public identifier for API and Beat tasks",
                        unique=True,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        help_text="Owner of this config",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="data_collector_configs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "platform",
                    models.CharField(
                        db_index=True,
                        help_text="Platform identifier, e.g. jira, feishu",
                        max_length=32,
                    ),
                ),
                (
                    "key",
                    models.CharField(
                        help_text="Config key, e.g. jira_config_collector",
                        max_length=128,
                    ),
                ),
                (
                    "value",
                    models.JSONField(
                        default=dict,
                        help_text=(
                            "Auth, schedule_cron, cleanup_cron, retention_days, "
                            "initial_range, runtime_state (timestamps)"
                        ),
                    ),
                ),
                (
                    "is_enabled",
                    models.BooleanField(
                        db_index=True,
                        default=True,
                        help_text="Whether collection is enabled",
                    ),
                ),
                (
                    "version",
                    models.IntegerField(
                        default=0,
                        help_text="Optimistic lock for concurrent updates",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "data_collector_config",
                "verbose_name": "Collector Config",
                "verbose_name_plural": "Collector Configs",
                "ordering": ["user", "platform"],
            },
        ),
        migrations.CreateModel(
            name="RawDataRecord",
            fields=[
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        help_text="Public identifier",
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="data_collector_records",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("platform", models.CharField(db_index=True, max_length=32)),
                (
                    "source_unique_id",
                    models.CharField(
                        db_index=True,
                        help_text="Platform-side unique id (e.g. issue key, approval id)",
                        max_length=255,
                    ),
                ),
                (
                    "raw_data",
                    models.JSONField(
                        default=dict,
                        help_text="Full raw payload from platform",
                    ),
                ),
                (
                    "filter_metadata",
                    models.JSONField(
                        default=dict,
                        help_text="Key fields for filtering (type, status, project, etc.)",
                    ),
                ),
                (
                    "data_hash",
                    models.CharField(
                        db_index=True,
                        help_text="Hash for change detection (e.g. MD5)",
                        max_length=64,
                    ),
                ),
                (
                    "is_deleted",
                    models.BooleanField(
                        db_index=True,
                        default=False,
                        help_text="True if no longer present on platform (after validate)",
                    ),
                ),
                ("source_created_at", models.DateTimeField(blank=True, null=True)),
                ("source_updated_at", models.DateTimeField(blank=True, null=True)),
                ("first_collected_at", models.DateTimeField(blank=True, null=True)),
                ("last_collected_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "data_collector_raw_data_record",
                "verbose_name": "Raw Data Record",
                "verbose_name_plural": "Raw Data Records",
                "ordering": ["-last_collected_at"],
            },
        ),
        migrations.CreateModel(
            name="RawDataAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "uuid",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        help_text="Public identifier for download API",
                        unique=True,
                    ),
                ),
                (
                    "raw_record",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attachments",
                        to="data_collector.rawdatarecord",
                    ),
                ),
                (
                    "source_file_id",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text="Platform file id for dedup",
                        max_length=255,
                        null=True,
                    ),
                ),
                ("file_name", models.CharField(max_length=512)),
                (
                    "file_path",
                    models.CharField(
                        help_text="Absolute path on server",
                        max_length=1024,
                    ),
                ),
                (
                    "file_url",
                    models.CharField(
                        help_text="HTTP path for download, e.g. /media/storage/data_collector/...",
                        max_length=1024,
                    ),
                ),
                ("file_type", models.CharField(blank=True, max_length=128)),
                ("file_size", models.BigIntegerField(default=0)),
                ("file_md5", models.CharField(blank=True, max_length=32)),
                ("source_created_at", models.DateTimeField(blank=True, null=True)),
                ("source_updated_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("extra", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "db_table": "data_collector_raw_data_attachment",
                "verbose_name": "Raw Data Attachment",
                "verbose_name_plural": "Raw Data Attachments",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="collectorconfig",
            constraint=models.UniqueConstraint(
                fields=("user", "platform"),
                name="data_collector_config_user_platform_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="rawdatarecord",
            constraint=models.UniqueConstraint(
                fields=("user", "platform", "source_unique_id"),
                name="data_collector_record_user_platform_sid_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="rawdatarecord",
            index=models.Index(fields=["user", "platform"], name="data_collect_user_id_platform_idx"),
        ),
        migrations.AddIndex(
            model_name="rawdatarecord",
            index=models.Index(fields=["platform", "is_deleted"], name="data_collect_platform_is_del_idx"),
        ),
        migrations.AddConstraint(
            model_name="rawdataattachment",
            constraint=models.UniqueConstraint(
                condition=models.Q(source_file_id__isnull=False),
                fields=("raw_record", "source_file_id"),
                name="data_collector_attachment_record_source_uniq",
            ),
        ),
    ]
