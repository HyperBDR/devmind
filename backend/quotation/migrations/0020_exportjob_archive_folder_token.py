from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quotation", "0019_quotation_product_line_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="exportjob",
            name="archive_folder_token",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
            ),
        ),
    ]
