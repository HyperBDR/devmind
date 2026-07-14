import hashlib
import json
import uuid

import django.utils.timezone
from django.db import migrations, models

SOURCE_RECORD_MODELS = (
    "Contract",
    "DomesticLedger",
    "OverseaProject",
    "OverseaSettlement",
    "Project",
    "ProjectInit",
    "SalesRecord",
)


def _content_hash(raw_data):
    payload = json.dumps(
        raw_data or {},
        default=str,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def backfill_source_content_hashes(apps, schema_editor):
    for model_name in SOURCE_RECORD_MODELS:
        model = apps.get_model("data_ops", model_name)
        pending = []
        queryset = model.objects.filter(source_content_hash="")
        for record in queryset.iterator(chunk_size=500):
            record.source_content_hash = _content_hash(record.raw_data)
            pending.append(record)
            if len(pending) == 500:
                model.objects.bulk_update(
                    pending,
                    ["source_content_hash"],
                    batch_size=500,
                )
                pending = []
        if pending:
            model.objects.bulk_update(
                pending,
                ["source_content_hash"],
                batch_size=500,
            )


def clear_source_content_hashes(apps, schema_editor):
    for model_name in SOURCE_RECORD_MODELS:
        model = apps.get_model("data_ops", model_name)
        model.objects.update(source_content_hash="")


class Migration(migrations.Migration):

    dependencies = [
        ("data_ops", "0002_owner_identity_collection"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="source_content_hash",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="contract",
            name="source_modified_time",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="domesticledger",
            name="source_content_hash",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="domesticledger",
            name="source_modified_time",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="overseaproject",
            name="source_content_hash",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="overseaproject",
            name="source_modified_time",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="overseasettlement",
            name="source_content_hash",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="overseasettlement",
            name="source_modified_time",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="source_content_hash",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="project",
            name="source_modified_time",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="projectinit",
            name="source_content_hash",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="projectinit",
            name="source_modified_time",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="salesrecord",
            name="source_content_hash",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="salesrecord",
            name="source_modified_time",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="SourceRecordChange",
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
                (
                    "source_key",
                    models.CharField(db_index=True, max_length=50),
                ),
                (
                    "table_key",
                    models.CharField(db_index=True, max_length=100),
                ),
                (
                    "model_name",
                    models.CharField(db_index=True, max_length=100),
                ),
                (
                    "source_record_id",
                    models.CharField(db_index=True, max_length=255),
                ),
                (
                    "change_type",
                    models.CharField(
                        choices=[
                            ("created", "Created"),
                            ("updated", "Updated"),
                            ("deleted", "Deleted"),
                            ("restored", "Restored"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                (
                    "changed_fields",
                    models.JSONField(blank=True, default=list),
                ),
                (
                    "source_changed_fields",
                    models.JSONField(blank=True, default=list),
                ),
                (
                    "before_values",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "after_values",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "source_modified_time",
                    models.BigIntegerField(blank=True, null=True),
                ),
                (
                    "detected_at",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=[
                            "source_key",
                            "table_key",
                            "detected_at",
                        ],
                        name="data_ops_src_change_table_idx",
                    ),
                    models.Index(
                        fields=[
                            "model_name",
                            "source_record_id",
                            "detected_at",
                        ],
                        name="data_ops_src_change_record_idx",
                    ),
                ],
            },
        ),
        migrations.RunPython(
            backfill_source_content_hashes,
            clear_source_content_hashes,
        ),
    ]
