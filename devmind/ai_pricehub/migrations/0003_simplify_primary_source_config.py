from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ai_pricehub", "0002_primary_source_config_and_hourly_snapshots"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="pricesourceconfig",
            name="pricing_url",
        ),
        migrations.AddField(
            model_name="pricesourceconfig",
            name="points_per_currency_unit",
            field=models.FloatField(default=10.0),
        ),
    ]
