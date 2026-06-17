from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("llm_ops", "0002_resale_listing_dual_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="resalelisting",
            name="retail_cache_input_price_per_million",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=14,
                null=True,
            ),
        ),
    ]
