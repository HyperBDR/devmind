from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("quotation", "0027_publicattachment")]

    operations = [
        migrations.AddField(
            model_name="exportjob",
            name="attachment_selection",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name="documentasset",
            name="doc_type",
            field=models.CharField(
                choices=[
                    ("excel", "excel"),
                    ("pdf", "pdf"),
                    ("merged_pdf", "merged_pdf"),
                    ("signature", "signature"),
                    ("attachment", "attachment"),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
    ]
