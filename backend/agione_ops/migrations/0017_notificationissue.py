"""Track active tenant issues independently from delivery attempts."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agione_ops", "0016_notificationrules_last_scheduled_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationIssue",
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
                ("customer_id", models.CharField(max_length=160)),
                ("reason", models.CharField(max_length=32)),
                ("active", models.BooleanField(db_index=True, default=True)),
                ("finding", models.JSONField(default=dict)),
                ("first_seen_at", models.DateTimeField()),
                ("last_seen_at", models.DateTimeField()),
                (
                    "last_alerted_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "rules",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="issues",
                        to="agione_ops.notificationrules",
                    ),
                ),
            ],
            options={
                "db_table": "devmind_agione_notification_issue",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("rules", "customer_id", "reason"),
                        name="dm_agione_issue_reason_uq",
                    )
                ],
            },
        ),
    ]
