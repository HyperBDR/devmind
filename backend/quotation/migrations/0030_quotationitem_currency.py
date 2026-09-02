from django.db import migrations, models


def copy_quote_currency(apps, schema_editor):
    quotation_item = apps.get_model("quotation", "QuotationItem")
    pending = []
    queryset = quotation_item.objects.select_related("quotation").iterator(
        chunk_size=500
    )
    for item in queryset:
        item.currency = item.quotation.currency or "USD"
        pending.append(item)
        if len(pending) == 500:
            quotation_item.objects.bulk_update(
                pending,
                ["currency"],
                batch_size=500,
            )
            pending = []
    if pending:
        quotation_item.objects.bulk_update(
            pending,
            ["currency"],
            batch_size=500,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("quotation", "0026_quotation_access_request"),
    ]

    operations = [
        migrations.AddField(
            model_name="quotationitem",
            name="currency",
            field=models.CharField(default="USD", max_length=3),
        ),
        migrations.RunPython(
            copy_quote_currency,
            migrations.RunPython.noop,
        ),
    ]
