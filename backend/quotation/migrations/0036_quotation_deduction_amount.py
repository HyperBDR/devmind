from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("quotation", "0035_tax_and_custom_total_fields")]

    operations = [
        migrations.AddField(
            model_name="quotation",
            name="deduction_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=18,
            ),
        ),
    ]
