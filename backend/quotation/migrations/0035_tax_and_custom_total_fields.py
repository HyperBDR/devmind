import quotation.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("quotation", "0034_unique_auto_draft_quote_number")]

    operations = [
        migrations.AddField(
            model_name="quotation",
            name="tax_calculation_mode",
            field=models.CharField(
                choices=[("add", "Add"), ("subtract", "Subtract")],
                default="add",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="quotation",
            name="custom_total_label",
            field=models.CharField(
                blank=True,
                default="",
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name="quotation",
            name="custom_total_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=18,
            ),
        ),
        migrations.AddField(
            model_name="quotation",
            name="custom_total_currency",
            field=models.CharField(default="USD", max_length=10),
        ),
        migrations.AlterField(
            model_name="publicattachment",
            name="id",
            field=models.CharField(
                default=quotation.models._uuid,
                editable=False,
                max_length=36,
                primary_key=True,
                serialize=False,
            ),
        ),
    ]
