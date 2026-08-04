from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("llm_ops", "0008_performance_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="usagereconciliationrecord",
            name="cache_input_tokens",
            field=models.PositiveBigIntegerField(default=0),
        ),
    ]
