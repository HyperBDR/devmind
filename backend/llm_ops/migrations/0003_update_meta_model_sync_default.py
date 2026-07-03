from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("llm_ops", "0002_model_sku_offering"),
    ]

    operations = [
        migrations.AlterField(
            model_name="llmopsglobalconfig",
            name="meta_model_sync_source_url",
            field=models.URLField(
                default="https://models.dev/models.json",
                max_length=1000,
            ),
        ),
    ]
