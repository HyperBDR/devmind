from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cloud_billing", "0012_add_day_to_billingdata"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="billingdata",
            index=models.Index(
                fields=[
                    "provider",
                    "account_id",
                    "period",
                    "-day",
                    "-hour",
                    "-collected_at",
                ],
                name="cbill_stats_latest_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="billingdata",
            index=models.Index(
                fields=[
                    "provider",
                    "account_id",
                    "-day",
                    "-hour",
                    "-collected_at",
                ],
                name="cbill_list_latest_idx",
            ),
        ),
    ]
