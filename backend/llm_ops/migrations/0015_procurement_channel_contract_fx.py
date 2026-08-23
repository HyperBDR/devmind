from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("llm_ops", "0014_channel_price_discount_dimensions"),
    ]

    operations = [
        migrations.AddField(
            model_name="procurementchannel",
            name="contract_currency",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
        migrations.AddField(
            model_name="procurementchannel",
            name="contract_exchange_rate",
            field=models.DecimalField(
                blank=True,
                decimal_places=8,
                max_digits=18,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="procurementchannel",
            name="exchange_rate_effective_from",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="procurementchannel",
            name="exchange_rate_effective_to",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
