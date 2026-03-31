from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ai_pricehub", "0004_multi_primary_source_configs"),
    ]

    operations = [
        migrations.AddField(
            model_name="pricesourceconfig",
            name="parser_llm_config_uuid",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
