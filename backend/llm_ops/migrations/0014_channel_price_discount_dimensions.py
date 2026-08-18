from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("llm_ops", "0013_channel_price_contracts"),
    ]

    operations = [
        migrations.AddField(
            model_name="channelpriceversion",
            name="discount_dimensions",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
