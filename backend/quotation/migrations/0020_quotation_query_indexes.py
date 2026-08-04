from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quotation", "0019_quotation_product_line_name"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="quotation",
            index=models.Index(
                fields=["quote_date"],
                name="quote_list_quote_date",
            ),
        ),
        migrations.AddIndex(
            model_name="quotation",
            index=models.Index(
                fields=["product_line_name"],
                name="quote_list_product_name",
            ),
        ),
    ]
