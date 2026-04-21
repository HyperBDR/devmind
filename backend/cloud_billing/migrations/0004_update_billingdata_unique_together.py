"""
Update unique_together constraint to include account_id.

This ensures that billing data is unique per provider, account_id, period, and hour,
allowing multiple accounts for the same provider to have separate billing records.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cloud_billing', '0003_add_growth_amount_threshold_to_alert_rule'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='billingdata',
            unique_together={('provider', 'account_id', 'period', 'hour')},
        ),
    ]
