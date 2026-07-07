from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("llm_ops", "0003_update_meta_model_sync_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="llmopsglobalconfig",
            name="feishu_approval_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
