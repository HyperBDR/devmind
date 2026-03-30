from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PricingRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("vendor_slug", models.CharField(db_index=True, max_length=100)),
                ("vendor_name", models.CharField(db_index=True, max_length=255)),
                ("vendor_pricing_url", models.URLField(blank=True, max_length=1000, null=True)),
                ("model_slug", models.CharField(db_index=True, max_length=100)),
                ("model_name", models.CharField(db_index=True, max_length=255)),
                ("family", models.CharField(blank=True, max_length=100, null=True)),
                ("role", models.CharField(db_index=True, default="comparison", max_length=50)),
                ("description", models.TextField(blank=True, null=True)),
                ("source_url", models.URLField(blank=True, max_length=1000, null=True)),
                ("input_price_per_million", models.FloatField(blank=True, null=True)),
                ("output_price_per_million", models.FloatField(blank=True, null=True)),
                ("currency", models.CharField(default="USD", max_length=10)),
                ("source_type", models.CharField(default="catalog", max_length=50)),
                ("raw_payload", models.JSONField(blank=True, null=True)),
                ("synced_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["model_name", "id"]},
        ),
        migrations.AddConstraint(
            model_name="pricingrecord",
            constraint=models.UniqueConstraint(
                fields=("vendor_slug", "model_slug"),
                name="uq_ai_pricehub_vendor_model",
            ),
        ),
    ]
