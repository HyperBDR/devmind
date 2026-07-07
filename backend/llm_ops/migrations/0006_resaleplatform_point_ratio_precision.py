from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("llm_ops", "0005_resaleplatform_point_decimal_places"),
    ]

    operations = [
        migrations.AlterField(
            model_name="resaleplatform",
            name="points_per_currency_unit",
            field=models.DecimalField(
                decimal_places=2,
                default=100,
                max_digits=14,
            ),
        ),
    ]
