from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("llm_ops", "0006_resaleplatform_point_ratio_precision"),
    ]

    operations = [
        migrations.AddField(
            model_name="resaleplatform",
            name="tax_rate",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                default=None,
                max_digits=8,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="resaleplatform",
            name="settlement_rate",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                default=None,
                max_digits=8,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="resaleplatform",
            name="yield_warning",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                default=None,
                max_digits=8,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="resaleplatform",
            name="yield_target",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                default=None,
                max_digits=8,
                null=True,
            ),
        ),
    ]
