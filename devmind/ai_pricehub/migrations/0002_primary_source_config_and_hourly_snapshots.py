from django.db import migrations, models
import django.utils.timezone


def seed_collected_hour(apps, schema_editor):
    PricingRecord = apps.get_model("ai_pricehub", "PricingRecord")
    for record in PricingRecord.objects.all().iterator():
        synced_at = record.synced_at or django.utils.timezone.now()
        collected_hour = synced_at.replace(minute=0, second=0, microsecond=0)
        PricingRecord.objects.filter(pk=record.pk).update(
            collected_at=synced_at,
            collected_hour=collected_hour,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("ai_pricehub", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PriceSourceConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("vendor_slug", models.CharField(db_index=True, max_length=100, unique=True)),
                ("vendor_name", models.CharField(max_length=255)),
                ("region", models.CharField(blank=True, default="", max_length=100)),
                ("endpoint_url", models.URLField(max_length=1000)),
                ("pricing_url", models.URLField(blank=True, max_length=1000, null=True)),
                ("currency", models.CharField(default="CNY", max_length=10)),
                ("is_enabled", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["vendor_slug", "id"]},
        ),
        migrations.AddField(
            model_name="pricingrecord",
            name="collected_at",
            field=models.DateTimeField(
                auto_now_add=True,
                db_index=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="pricingrecord",
            name="collected_hour",
            field=models.DateTimeField(
                db_index=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="pricingrecord",
            name="synced_at",
            field=models.DateTimeField(auto_now=True, db_index=True),
        ),
        migrations.AlterModelOptions(
            name="pricingrecord",
            options={"ordering": ["-collected_hour", "model_name", "id"]},
        ),
        migrations.RunPython(seed_collected_hour, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="pricingrecord",
            name="uq_ai_pricehub_vendor_model",
        ),
        migrations.AddConstraint(
            model_name="pricingrecord",
            constraint=models.UniqueConstraint(
                fields=("vendor_slug", "model_slug", "collected_hour"),
                name="uq_ai_pricehub_vendor_model_hour",
            ),
        ),
    ]
