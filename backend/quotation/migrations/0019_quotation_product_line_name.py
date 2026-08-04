from django.db import migrations, models

PRODUCT_LINE_NAMES = {
    "agione": "AGIOne",
    "bdr": "HyperBDR",
    "motion": "HyperMotion",
    "service": "General Service",
}


def backfill_product_line_names(apps, schema_editor):
    """Backfill official names while preserving legacy custom prefixes."""
    quotation = apps.get_model("quotation", "Quotation")
    for prefix, name in PRODUCT_LINE_NAMES.items():
        quotation.objects.filter(product_line__iexact=prefix).update(
            product_line_name=name
        )


class Migration(migrations.Migration):
    dependencies = [
        ("quotation", "0018_quotation_list_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="quotation",
            name="product_line_name",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.RunPython(
            backfill_product_line_names,
            migrations.RunPython.noop,
        ),
    ]
