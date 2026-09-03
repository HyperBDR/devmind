from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quotation", "0033_unique_auto_draft_quote_number"),
    ]

    operations = [
        migrations.AlterField(
            model_name="quotationitem",
            name="discount_percent",
            field=models.DecimalField(
                decimal_places=4,
                default=0,
                max_digits=7,
            ),
        ),
    ]
