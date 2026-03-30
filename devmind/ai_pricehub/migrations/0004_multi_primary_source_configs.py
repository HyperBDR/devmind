from django.db import migrations, models


def populate_platform_slugs(apps, schema_editor):
    PriceSourceConfig = apps.get_model("ai_pricehub", "PriceSourceConfig")
    for config in PriceSourceConfig.objects.all().order_by("id"):
        base = (config.vendor_slug or "agione").strip() or "agione"
        candidate = base
        counter = 2
        while (
            PriceSourceConfig.objects.exclude(pk=config.pk)
            .filter(platform_slug=candidate)
            .exists()
        ):
            candidate = f"{base}-{counter}"
            counter += 1
        config.platform_slug = candidate
        config.save(update_fields=["platform_slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("ai_pricehub", "0003_simplify_primary_source_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="pricesourceconfig",
            name="platform_slug",
            field=models.CharField(
                default="agione",
                max_length=100,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(populate_platform_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="pricesourceconfig",
            name="vendor_slug",
            field=models.CharField(
                db_index=True,
                default="agione",
                max_length=100,
            ),
        ),
        migrations.AlterField(
            model_name="pricesourceconfig",
            name="platform_slug",
            field=models.CharField(
                max_length=100,
                unique=True,
            ),
        ),
    ]
