from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quotation", "0008_remove_template_asset"),
    ]

    operations = [
        migrations.AddField(
            model_name="feishuconnection",
            name="shared_folder_bookmarks",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
