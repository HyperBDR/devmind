"""
Add hourly_cost field to BillingData model.

This field stores the incremental cost for each hour,
calculated as: current hour total_cost - previous hour total_cost.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cloud_billing', '0003_add_growth_amount_threshold_to_alert_rule'),
    ]

    operations = [
        migrations.AddField(
            model_name='billingdata',
            name='hourly_cost',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Incremental cost for this hour (current - previous hour)',
                max_digits=20,
                null=True
            ),
        ),
    ]
