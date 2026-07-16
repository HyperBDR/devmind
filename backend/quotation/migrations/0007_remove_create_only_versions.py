from django.db import migrations, models

CREATE_ONLY_NOTES = (
    "Created quotation",
    "Backfilled initial version",
)


def remove_create_only_versions(apps, schema_editor):
    Quotation = apps.get_model("quotation", "Quotation")
    QuotationVersion = apps.get_model("quotation", "QuotationVersion")
    QuotationVersion.objects.filter(notes__in=CREATE_ONLY_NOTES).delete()
    for quotation in Quotation.objects.all().iterator():
        versions = list(
            QuotationVersion.objects.filter(
                quotation_id=quotation.id
            ).order_by("version_no", "created_at")
        )
        for index, version in enumerate(versions, start=1):
            version.version_no = 100000 + index
            version.save(update_fields=["version_no"])
        for index, version in enumerate(versions, start=1):
            version.version_no = index
            version.save(update_fields=["version_no"])
        quotation.version_current = len(versions)
        quotation.save(update_fields=["version_current"])


def noop_reverse(apps, schema_editor):
    """Create-only draft versions are not restored."""


class Migration(migrations.Migration):

    dependencies = [
        ("quotation", "0006_backfill_quotation_versions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="quotation",
            name="version_current",
            field=models.IntegerField(default=0),
        ),
        migrations.RunPython(remove_create_only_versions, noop_reverse),
    ]
