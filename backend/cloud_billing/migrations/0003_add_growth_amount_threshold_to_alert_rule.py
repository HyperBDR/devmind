# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cloud_billing', '0002_add_notes_to_cloud_provider'),
    ]

    operations = [
        migrations.AddField(
            model_name='alertrule',
            name='growth_amount_threshold',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Growth amount threshold, e.g., 1000.00 means alert when cost increases by 1000.00',
                max_digits=20,
                null=True
            ),
        ),
    ]
