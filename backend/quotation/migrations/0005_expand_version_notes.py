from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quotation", "0004_expand_quote_status_choices"),
    ]

    operations = [
        migrations.AlterField(
            model_name="quotationversion",
            name="notes",
            field=models.TextField(blank=True, default=""),
        ),
    ]
