from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PriceSourceConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("vendor_slug", models.CharField(db_index=True, default="agione", max_length=100)),
                ("platform_slug", models.CharField(db_index=True, max_length=100, unique=True)),
                ("vendor_name", models.CharField(max_length=255)),
                ("region", models.CharField(blank=True, default="", max_length=100)),
                ("endpoint_url", models.URLField(max_length=1000)),
                ("parser_llm_config_uuid", models.UUIDField(blank=True, db_index=True, null=True)),
                ("currency", models.CharField(default="CNY", max_length=10)),
                ("points_per_currency_unit", models.FloatField(default=10.0)),
                ("is_enabled", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["vendor_slug", "region", "vendor_name", "id"]},
        ),
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
                ("collected_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("collected_hour", models.DateTimeField(db_index=True)),
                ("synced_at", models.DateTimeField(auto_now=True, db_index=True)),
            ],
            options={"ordering": ["-collected_hour", "model_name", "id"]},
        ),
        migrations.AddConstraint(
            model_name="pricingrecord",
            constraint=models.UniqueConstraint(
                fields=("vendor_slug", "model_slug", "collected_hour"),
                name="uq_ai_pricehub_vendor_model_hour",
            ),
        ),
    ]
