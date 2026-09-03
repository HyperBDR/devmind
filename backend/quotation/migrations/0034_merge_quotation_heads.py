from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("quotation", "0033_alter_quotationitem_discount_percent"),
        ("quotation", "0033_unique_auto_draft_quote_number"),
    ]

    operations = []
