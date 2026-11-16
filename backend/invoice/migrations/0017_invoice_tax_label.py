from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("invoice", "0016_regenerate_bdr111126_pdf")]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="tax_label",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
    ]
