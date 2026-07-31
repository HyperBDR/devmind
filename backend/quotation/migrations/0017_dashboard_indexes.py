from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quotation", "0016_remove_security_alert"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="quotation",
            index=models.Index(
                fields=["currency", "status", "created_at"],
                name="quote_dash_curr_stat_created",
            ),
        ),
        migrations.AddIndex(
            model_name="quotation",
            index=models.Index(
                fields=["created_by_email", "currency", "status"],
                name="quote_dash_owner_curr_stat",
            ),
        ),
        migrations.AddIndex(
            model_name="quotation",
            index=models.Index(
                fields=["-created_at", "-id"],
                name="quote_list_created_id",
            ),
        ),
        migrations.AddIndex(
            model_name="quotationversion",
            index=models.Index(
                fields=["quotation", "status", "created_at"],
                name="quote_ver_quote_stat_created",
            ),
        ),
    ]
