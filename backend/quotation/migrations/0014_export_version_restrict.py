import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quotation", "0013_quotation_exports"),
    ]

    operations = [
        migrations.AlterField(
            model_name="documentasset",
            name="quotation_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="document_assets",
                to="quotation.quotationversion",
            ),
        ),
        migrations.AlterField(
            model_name="exportjob",
            name="quotation_version",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="export_jobs",
                to="quotation.quotationversion",
            ),
        ),
    ]
