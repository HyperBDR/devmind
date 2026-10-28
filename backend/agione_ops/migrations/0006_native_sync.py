"""Persist sanitized native shards, staging and immutable publication."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agione_ops", "0005_snapshot_store")]

    operations = [
        migrations.CreateModel(
            name="NativeSyncState",
            fields=[
                ("run", models.OneToOneField(
                    to="agione_ops.syncrun", primary_key=True, serialize=False,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="native_state",
                )),
                ("directory", models.JSONField(default=dict)),
                ("model_names", models.JSONField(default=dict)),
                ("directory_complete", models.BooleanField(default=False)),
                ("directory_count", models.PositiveIntegerField(default=0)),
                ("role_state", models.CharField(
                    max_length=32, default="not_verified",
                )),
                ("watermark", models.DateTimeField(null=True, blank=True)),
            ],
            options={"db_table": "devmind_agione_native_sync_state"},
        ),
        migrations.CreateModel(
            name="NativeSyncShard",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID",
                )),
                ("run", models.ForeignKey(
                    to="agione_ops.syncrun",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="native_shards",
                )),
                ("window_start", models.DateTimeField()),
                ("window_end", models.DateTimeField()),
                ("status", models.CharField(max_length=16, default="pending")),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("pages_read", models.PositiveIntegerField(default=0)),
                ("record_count", models.PositiveBigIntegerField(default=0)),
                ("excluded_count", models.PositiveBigIntegerField(default=0)),
                ("error_code", models.CharField(
                    max_length=80, default="", blank=True,
                )),
                ("completed_at", models.DateTimeField(null=True, blank=True)),
            ],
            options={
                "db_table": "devmind_agione_native_sync_shard",
                "ordering": ["window_start", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("run", "window_start", "window_end"),
                        name="dm_agione_native_shard_uq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            window_end__gt=models.F("window_start"),
                        ), name="dm_agione_native_shard_window",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="NativeStagedRecord",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID",
                )),
                ("run", models.ForeignKey(
                    to="agione_ops.syncrun",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="native_staging",
                )),
                ("shard", models.ForeignKey(
                    to="agione_ops.nativesyncshard",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="records",
                )),
                ("record_id", models.CharField(max_length=40)),
                ("occurred_at", models.DateTimeField()),
                ("content_digest", models.CharField(max_length=64)),
                ("data", models.JSONField()),
            ],
            options={
                "db_table": "devmind_agione_native_staged_record",
                "constraints": [models.UniqueConstraint(
                    fields=("run", "record_id"),
                    name="dm_agione_native_stage_uq",
                )],
            },
        ),
        migrations.CreateModel(
            name="NativePublishedSnapshot",
            fields=[
                ("version", models.OneToOneField(
                    to="agione_ops.datasetversion", primary_key=True,
                    serialize=False,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="native_snapshot",
                )),
                ("data", models.JSONField()),
                ("content_digest", models.CharField(max_length=64)),
            ],
            options={"db_table": "devmind_agione_native_published_snapshot"},
        ),
    ]
