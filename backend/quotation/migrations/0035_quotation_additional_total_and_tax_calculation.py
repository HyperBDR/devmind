from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quotation", "0034_unique_auto_draft_quote_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="quotation",
            name="additional_grand_total_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=18,
            ),
        ),
        migrations.AddField(
            model_name="quotation",
            name="additional_grand_total_currency",
            field=models.CharField(default="USD", max_length=10),
        ),
        migrations.AddField(
            model_name="quotation",
            name="additional_grand_total_label",
            field=models.CharField(default="Grand Total", max_length=80),
        ),
        migrations.AddField(
            model_name="quotation",
            name="tax_calculation",
            field=models.CharField(
                choices=[
                    ("add", "Add to total"),
                    ("subtract", "Deduct from total"),
                ],
                default="add",
                max_length=8,
            ),
        ),
    ]
