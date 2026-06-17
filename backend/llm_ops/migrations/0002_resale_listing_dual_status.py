from django.db import migrations, models


def backfill_resale_listing_status(apps, schema_editor):
    ResaleListing = apps.get_model("llm_ops", "ResaleListing")
    ResaleListing.objects.filter(is_active=True).update(
        publish_status="online",
        workflow_status="online",
    )
    ResaleListing.objects.filter(is_active=False).update(
        publish_status="offline",
        workflow_status="offline",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("llm_ops", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="resalelisting",
            name="publish_status",
            field=models.CharField(
                choices=[
                    ("none", "Not Published"),
                    ("online", "Published"),
                    ("offline", "Offline"),
                    ("deleted", "Deleted"),
                ],
                db_index=True,
                default="none",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="resalelisting",
            name="workflow_status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("pending_publish", "Pending Publish"),
                    ("online", "Online"),
                    ("update_draft", "Update Draft"),
                    ("pending_update", "Pending Update"),
                    ("pending_offline", "Pending Offline"),
                    ("offline_exception", "Offline Exception"),
                    ("offline", "Offline"),
                    ("deleted", "Deleted"),
                ],
                db_index=True,
                default="draft",
                max_length=30,
            ),
        ),
        migrations.RunPython(
            backfill_resale_listing_status,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="resalelisting",
            name="is_active",
            field=models.BooleanField(default=False),
        ),
    ]
