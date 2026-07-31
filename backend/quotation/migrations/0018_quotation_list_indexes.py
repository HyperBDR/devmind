from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quotation", "0017_dashboard_indexes"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="quotation",
            index=models.Index(
                fields=["created_by_email", "-created_at", "-id"],
                name="quote_list_owner_created",
            ),
        ),
        migrations.AddIndex(
            model_name="quotation",
            index=models.Index(
                fields=["product_line", "-created_at", "-id"],
                name="quote_list_product_created",
            ),
        ),
        migrations.AddIndex(
            model_name="documentasset",
            index=models.Index(
                fields=["quotation", "doc_type", "-created_at", "-id"],
                name="quote_doc_quote_type_created",
            ),
        ),
        migrations.AddIndex(
            model_name="documentreplica",
            index=models.Index(
                fields=[
                    "asset",
                    "sync_status",
                    "revoked_at",
                    "-version",
                ],
                name="quote_replica_asset_status",
            ),
        ),
    ]
