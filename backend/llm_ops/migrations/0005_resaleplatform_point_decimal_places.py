import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("llm_ops", "0004_llmopsglobalconfig_feishu_approval_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="resaleplatform",
            name="point_decimal_places",
            field=models.PositiveSmallIntegerField(
                default=0,
                validators=[django.core.validators.MaxValueValidator(6)],
            ),
        ),
    ]
