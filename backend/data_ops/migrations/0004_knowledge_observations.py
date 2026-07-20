import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data_ops", "0003_source_record_changes"),
    ]

    operations = [
        migrations.CreateModel(
            name="Evidence",
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
                    "source_model",
                    models.CharField(db_index=True, max_length=100),
                ),
                (
                    "source_object_id",
                    models.CharField(db_index=True, max_length=255),
                ),
                (
                    "source_record_id",
                    models.CharField(blank=True, max_length=255),
                ),
                (
                    "source_locator",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "source_content_hash",
                    models.CharField(blank=True, max_length=64),
                ),
                (
                    "snapshot",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "captured_at",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["source_model", "source_record_id"],
                        name="data_ops_evidence_record_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=(
                            "source_model",
                            "source_object_id",
                            "source_content_hash",
                        ),
                        name="uq_data_ops_evidence_source_version",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="KnowledgeProductionRun",
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
                    "producer_key",
                    models.CharField(db_index=True, max_length=100),
                ),
                (
                    "producer_version",
                    models.CharField(max_length=50),
                ),
                (
                    "parameters",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Running"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="running",
                        max_length=20,
                    ),
                ),
                (
                    "started_at",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                    ),
                ),
                (
                    "finished_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "result_counts",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "error_message",
                    models.CharField(blank=True, max_length=2000),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["producer_key", "started_at"],
                        name="data_ops_kp_run_producer_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Observation",
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
                    "observation_type",
                    models.CharField(db_index=True, max_length=100),
                ),
                (
                    "subject_type",
                    models.CharField(db_index=True, max_length=100),
                ),
                (
                    "subject_key",
                    models.CharField(db_index=True, max_length=255),
                ),
                ("statement", models.TextField()),
                (
                    "structured_value",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("low", "Low"),
                            ("medium", "Medium"),
                            ("high", "High"),
                            ("critical", "Critical"),
                        ],
                        db_index=True,
                        default="low",
                        max_length=20,
                    ),
                ),
                (
                    "confidence",
                    models.CharField(default="high", max_length=20),
                ),
                (
                    "producer_key",
                    models.CharField(db_index=True, max_length=100),
                ),
                (
                    "producer_version",
                    models.CharField(max_length=50),
                ),
                (
                    "fingerprint",
                    models.CharField(max_length=64, unique=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("resolved", "Resolved"),
                            ("superseded", "Superseded"),
                            ("invalidated", "Invalidated"),
                        ],
                        db_index=True,
                        default="active",
                        max_length=20,
                    ),
                ),
                ("window_start", models.DateField(blank=True, null=True)),
                ("window_end", models.DateField(blank=True, null=True)),
                (
                    "generated_at",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                    ),
                ),
                (
                    "last_evaluated_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                (
                    "resolved_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="observations",
                        to="data_ops.knowledgeproductionrun",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ObservationEvidence",
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
                    "role",
                    models.CharField(
                        choices=[
                            ("supporting", "Supporting"),
                            ("contradicting", "Contradicting"),
                        ],
                        default="supporting",
                        max_length=20,
                    ),
                ),
                (
                    "linked_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                    ),
                ),
                (
                    "evidence",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="observation_links",
                        to="data_ops.evidence",
                    ),
                ),
                (
                    "observation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evidence_links",
                        to="data_ops.observation",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="observation",
            name="evidence",
            field=models.ManyToManyField(
                related_name="observations",
                through="data_ops.ObservationEvidence",
                to="data_ops.evidence",
            ),
        ),
        migrations.AddConstraint(
            model_name="observationevidence",
            constraint=models.UniqueConstraint(
                fields=("observation", "evidence"),
                name="uq_data_ops_observation_evidence",
            ),
        ),
        migrations.AddIndex(
            model_name="observation",
            index=models.Index(
                fields=["status", "severity", "generated_at"],
                name="data_ops_obs_attention_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="observation",
            index=models.Index(
                fields=["subject_type", "subject_key", "status"],
                name="data_ops_obs_subject_idx",
            ),
        ),
    ]
