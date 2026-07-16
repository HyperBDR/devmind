from decimal import Decimal

from django.db import migrations


def _decimal_str(value) -> str:
    return str(Decimal(str(value or 0)))


def _build_snapshot(quotation) -> dict:
    items = list(quotation.items.all())
    return {
        "id": quotation.id,
        "quote_no": quotation.quote_no,
        "status": quotation.status,
        "product_line": quotation.product_line,
        "project_name": quotation.project_name,
        "currency": quotation.currency,
        "payment_term_option": quotation.payment_term_option,
        "payment_terms": quotation.payment_terms,
        "quote_date": (
            quotation.quote_date.isoformat() if quotation.quote_date else None
        ),
        "expire_date": (
            quotation.expire_date.isoformat()
            if quotation.expire_date
            else None
        ),
        "tax_label": quotation.tax_label,
        "vat_rate": _decimal_str(quotation.vat_rate),
        "vat_amount": _decimal_str(quotation.vat_amount),
        "software_subtotal": _decimal_str(quotation.software_subtotal),
        "others_subtotal": _decimal_str(quotation.others_subtotal),
        "subtotal_before_vat": _decimal_str(quotation.subtotal_before_vat),
        "grand_total": _decimal_str(quotation.grand_total),
        "remarks_disclaimer": quotation.remarks_disclaimer or "",
        "issuer_company_name": quotation.issuer_company_name,
        "issuer_contact_name": quotation.issuer_contact_name,
        "issuer_contact_email": quotation.issuer_contact_email,
        "issuer_contact_title": quotation.issuer_contact_title or "",
        "issuer_signature": quotation.issuer_signature or "",
        "client_company": quotation.client_company,
        "contact_person": quotation.contact_person,
        "email": quotation.email,
        "billing_company": quotation.billing_company or "",
        "billing_contact": quotation.billing_contact or "",
        "billing_email": quotation.billing_email or "",
        "created_by_email": quotation.created_by_email,
        "items": [
            {
                "id": item.id,
                "line_no": item.line_no,
                "type": item.type,
                "item_id": item.item_id,
                "name": item.name,
                "description": item.description,
                "qty": _decimal_str(item.qty),
                "list_price": _decimal_str(item.list_price),
                "discount_percent": _decimal_str(item.discount_percent),
                "net_unit_price": _decimal_str(item.net_unit_price),
                "extended_price": _decimal_str(item.extended_price),
            }
            for item in items
        ],
    }


def backfill_versions(apps, schema_editor):
    Quotation = apps.get_model("quotation", "Quotation")
    QuotationVersion = apps.get_model("quotation", "QuotationVersion")
    for quotation in Quotation.objects.all().iterator():
        if QuotationVersion.objects.filter(quotation=quotation).exists():
            continue
        QuotationVersion.objects.create(
            quotation=quotation,
            version_no=1,
            status=quotation.status,
            notes="Backfilled initial version",
            snapshot_json=_build_snapshot(quotation),
            operator_email=quotation.created_by_email,
        )
        if quotation.version_current < 1:
            quotation.version_current = 1
            quotation.save(update_fields=["version_current"])


def noop_reverse(apps, schema_editor):
    """Keep historical version rows on reverse."""


class Migration(migrations.Migration):

    dependencies = [
        ("quotation", "0005_expand_version_notes"),
    ]

    operations = [
        migrations.RunPython(backfill_versions, noop_reverse),
    ]
