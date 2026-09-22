from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quotation", "0036_quotation_deduction_amount"),
    ]

    operations = [
        migrations.AlterField(
            model_name="quotation",
            name="quote_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="quotation",
            name="expire_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
