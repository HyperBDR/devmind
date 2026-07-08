from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data_ops", "0004_data_ops_global_config"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dataopsglobalconfig",
            name="feishu_app_secret",
            field=models.TextField(blank=True),
        ),
    ]
