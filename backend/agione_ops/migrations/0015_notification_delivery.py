"""Persist durable AGIOne notification delivery attempts."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("agione_ops", "0014_notification_analysis"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationDelivery",
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
                ("event_key", models.CharField(max_length=64, unique=True)),
                (
                    "issue_signature",
                    models.CharField(db_index=True, max_length=64),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[("alert", "Alert"), ("recovery", "Recovery")],
                        max_length=16,
                    ),
                ),
                ("payload", models.JSONField(default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("sending", "Sending"),
                            ("retrying", "Retrying"),
                            ("sent", "Sent"),
                            ("failed", "Failed"),
                            ("silenced", "Silenced"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("error_message", models.TextField(blank=True, default="")),
                ("response", models.JSONField(blank=True, null=True)),
                ("next_retry_at", models.DateTimeField(blank=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "rules",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deliveries",
                        to="agione_ops.notificationrules",
                    ),
                ),
            ],
            options={
                "db_table": "devmind_agione_notification_delivery",
                "ordering": ["-created_at", "-pk"],
            },
        ),
    ]
