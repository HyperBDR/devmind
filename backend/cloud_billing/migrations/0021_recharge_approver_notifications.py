import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cloud_billing", "0020_alert_rule_recharge_recovery_detection"),
    ]

    operations = [
        migrations.CreateModel(
            name="RechargeApprovalApproverNotification",
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
                ("recipient_user_id", models.CharField(max_length=128)),
                (
                    "notification_key",
                    models.CharField(default="pending", max_length=64),
                ),
                (
                    "node_id",
                    models.CharField(blank=True, default="", max_length=128),
                ),
                (
                    "node_name",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "task_id",
                    models.CharField(blank=True, default="", max_length=128),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("sending", "Sending"),
                            ("sent", "Sent"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                (
                    "message_id",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("error_message", models.TextField(blank=True, default="")),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "record",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approver_notifications",
                        to="cloud_billing.rechargeapprovalrecord",
                    ),
                ),
            ],
            options={
                "verbose_name": (
                    "Recharge Approval Approver Notification"
                ),
                "verbose_name_plural": (
                    "Recharge Approval Approver Notifications"
                ),
                "db_table": (
                    "cloud_billing_recharge_approver_notification"
                ),
            },
        ),
        migrations.AddConstraint(
            model_name="rechargeapprovalapprovernotification",
            constraint=models.UniqueConstraint(
                fields=(
                    "record",
                    "recipient_user_id",
                    "notification_key",
                ),
                name="cloud_billing_unique_approver_notice",
            ),
        ),
        migrations.AddIndex(
            model_name="rechargeapprovalapprovernotification",
            index=models.Index(
                fields=["status", "updated_at"],
                name="cloud_billi_status_d5c2e5_idx",
            ),
        ),
    ]
