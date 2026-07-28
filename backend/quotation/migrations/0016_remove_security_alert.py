from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("quotation", "0015_remote_file_cleanup"),
    ]

    operations = [
        migrations.DeleteModel(
            name="SecurityAlert",
        ),
    ]
