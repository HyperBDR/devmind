from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cloud_billing", "0023_add_yunce_provider_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="billingdata",
            name="is_available",
            field=models.BooleanField(
                blank=True,
                help_text=(
                    "Provider-reported account availability at collection "
                    "time"
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="cloudprovider",
            name="consecutive_collection_failures",
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    "Number of billing collection failures since last "
                    "success"
                ),
            ),
        ),
        migrations.AddField(
            model_name="cloudprovider",
            name="last_collection_attempt_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When billing collection was last attempted",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="cloudprovider",
            name="last_collection_status",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Most recent billing collection result",
                max_length=20,
            ),
        ),
    ]
