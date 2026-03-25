from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cloud_billing", "0009_add_volcengine_provider_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="alertrecord",
            name="balance_threshold",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Balance threshold that triggered the alert",
                max_digits=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="alertrecord",
            name="current_balance",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Current account balance when alert triggered",
                max_digits=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="alertrule",
            name="balance_threshold",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Balance threshold, e.g., 100.00 means alert when account balance drops below 100.00",
                max_digits=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="billingdata",
            name="balance",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Account cash balance at collection time",
                max_digits=20,
                null=True,
            ),
        ),
    ]
