from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cloud_billing", "0018_alert_rule_auto_recharge_amount"),
    ]

    operations = [
        migrations.AddField(
            model_name="rechargeapprovalrecord",
            name="fulfilled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="rechargeapprovalrecord",
            name="fulfillment_evidence",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Evidence used to mark the recharge objective as "
                    "recovered."
                ),
            ),
        ),
        migrations.AddField(
            model_name="rechargeapprovalrecord",
            name="fulfillment_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("recovered", "Recovered"),
                ],
                db_index=True,
                default="pending",
                help_text=(
                    "Business fulfillment state independent from the "
                    "Feishu approval workflow status."
                ),
                max_length=20,
            ),
        ),
    ]
