from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cloud_billing", "0017_add_cost_period_to_alert_record"),
    ]

    operations = [
        migrations.AddField(
            model_name="alertrule",
            name="auto_recharge_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text=(
                    "Manual recharge amount used when alert-triggered "
                    "automatic recharge approval is enabled."
                ),
                max_digits=20,
                null=True,
            ),
        ),
    ]
