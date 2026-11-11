from django.db import migrations

from quotation.services.description_label_cleanup import (
    apply_cleanup_plans,
    build_cleanup_plans,
)

QUOTE_NUMBERS = (
    "BDR111126",
    "BDR101126",
    "BDR061126",
    "BDR051126.1_R1",
    "BDR051126_R1",
    "BDR031126.1",
    "BDR031126_R1",
)


def strip_labels(apps, schema_editor):
    """Strip legacy description labels from the listed quotations only."""
    plans = build_cleanup_plans(
        apps.get_model("quotation", "Quotation"),
        QUOTE_NUMBERS,
        log=lambda message: None,
    )
    apply_cleanup_plans(
        apps.get_model("quotation", "Quotation"),
        apps.get_model("quotation", "QuotationItem"),
        apps.get_model("quotation", "QuotationVersion"),
        plans,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("quotation", "0037_imported_quote_dates_nullable"),
    ]

    operations = [
        migrations.RunPython(strip_labels, migrations.RunPython.noop),
    ]
