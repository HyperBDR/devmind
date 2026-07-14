from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cloud_billing", "0019_recharge_approval_fulfillment"),
    ]

    operations = [
        migrations.AddField(
            model_name="alertrule",
            name="enable_recharge_recovery_detection",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Whether account health recovery should release "
                    "recovered automatic approvals from blocking new "
                    "submissions."
                ),
            ),
        ),
    ]
