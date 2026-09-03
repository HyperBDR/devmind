from django.db import migrations, models


def backfill_access_regions(apps, schema_editor):
    """Keep legacy SKU region values available through the new field."""
    model_sku = apps.get_model("llm_ops", "ModelSku")
    model_sku.objects.exclude(region="").filter(access_region="").update(
        access_region=models.F("region"),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("llm_ops", "0015_procurement_channel_contract_fx"),
    ]

    operations = [
        migrations.AddField(
            model_name="modelsku",
            name="access_region",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="modelsku",
            name="deployment_scope",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="modelpriceitem",
            name="pricing_condition",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(
            backfill_access_regions,
            migrations.RunPython.noop,
        ),
    ]
