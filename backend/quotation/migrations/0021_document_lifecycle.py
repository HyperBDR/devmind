from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quotation", "0020_exportjob_archive_folder_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="quotation",
            name="archive_reason",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="quotation",
            name="archived_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="quotation",
            name="archived_by_email",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="documentasset",
            name="archive_reason",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="documentasset",
            name="archived_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="documentasset",
            name="archived_by_email",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="documentasset",
            name="legal_hold_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="documentasset",
            name="legal_hold_reason",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="documentasset",
            name="lifecycle_state",
            field=models.CharField(
                choices=[("active", "Active"), ("archived", "Archived")],
                db_index=True,
                default="active",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="documentasset",
            name="purge_after",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddIndex(
            model_name="documentasset",
            index=models.Index(
                fields=["lifecycle_state", "purge_after", "created_at"],
                name="quote_doc_lifecycle_purge",
            ),
        ),
    ]
