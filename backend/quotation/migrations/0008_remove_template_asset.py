from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("quotation", "0007_remove_create_only_versions"),
    ]

    operations = [
        migrations.DeleteModel(
            name="TemplateAsset",
        ),
    ]
