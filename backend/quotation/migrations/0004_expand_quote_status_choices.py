from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quotation", "0003_documentasset_feishu_url"),
    ]

    operations = [
        migrations.AlterField(
            model_name="quotation",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "draft"),
                    ("generated", "generated"),
                    ("uploaded", "uploaded"),
                    ("sent", "sent"),
                    ("accepted", "accepted"),
                    ("rejected", "rejected"),
                    ("expired", "expired"),
                    ("cancelled", "cancelled"),
                ],
                db_index=True,
                default="draft",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="quotationversion",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "draft"),
                    ("generated", "generated"),
                    ("uploaded", "uploaded"),
                    ("sent", "sent"),
                    ("accepted", "accepted"),
                    ("rejected", "rejected"),
                    ("expired", "expired"),
                    ("cancelled", "cancelled"),
                ],
                max_length=20,
            ),
        ),
    ]
