from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable

from django.db import transaction

from quotation.models import (
    ItemType,
    Quotation,
    QuotationItem,
    QuotationVersion,
    QuoteStatus,
)


def round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _item_type_value(raw: Any) -> str:
    if hasattr(raw, "value"):
        return str(raw.value)
    return str(raw or "")


def _decimal_str(value: Any) -> str:
    return str(Decimal(str(value or 0)))


def _date_iso(value: Any) -> str | None:
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def calculate_totals(
    items: Iterable[Any], vat_rate: Decimal
) -> dict[str, Decimal]:
    software_subtotal = round_money(
        sum(
            (
                Decimal(str(getattr(item, "extended_price", 0)))
                for item in items
                if _item_type_value(getattr(item, "type", ""))
                == ItemType.SOFTWARE
            ),
            Decimal("0"),
        )
    )
    others_subtotal = round_money(
        sum(
            (
                Decimal(str(getattr(item, "extended_price", 0)))
                for item in items
                if _item_type_value(getattr(item, "type", ""))
                != ItemType.SOFTWARE
            ),
            Decimal("0"),
        )
    )
    subtotal_before_vat = round_money(software_subtotal + others_subtotal)
    vat_amount = round_money(
        subtotal_before_vat * (Decimal(str(vat_rate)) / Decimal("100"))
    )
    grand_total = round_money(subtotal_before_vat + vat_amount)
    return {
        "software_subtotal": software_subtotal,
        "others_subtotal": others_subtotal,
        "subtotal_before_vat": subtotal_before_vat,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
    }


def coerce_item_type(raw_type: str) -> str:
    normalized = (raw_type or "").strip()
    for candidate in ItemType:
        if (
            normalized == candidate.value
            or normalized.lower() == candidate.name.lower()
        ):
            return candidate.value
    return ItemType.OTHER


def _clear_prefetched(quotation: Quotation, related: str) -> None:
    cache = getattr(quotation, "_prefetched_objects_cache", None)
    if cache is not None:
        cache.pop(related, None)


def build_quotation_snapshot(
    quotation: Quotation,
    items: list[QuotationItem] | None = None,
) -> dict[str, Any]:
    """Full quote snapshot for version history UI."""
    line_items = items if items is not None else list(quotation.items.all())
    return {
        "id": quotation.id,
        "quote_no": quotation.quote_no,
        "status": quotation.status,
        "product_line": quotation.product_line,
        "project_name": quotation.project_name,
        "currency": quotation.currency,
        "payment_term_option": quotation.payment_term_option,
        "payment_terms": quotation.payment_terms,
        "quote_date": _date_iso(quotation.quote_date),
        "expire_date": _date_iso(quotation.expire_date),
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
            for item in line_items
        ],
    }


def build_quotation(
    *, data: dict[str, Any], items_data: list[dict[str, Any]]
) -> Quotation:
    totals = calculate_totals(
        [type("I", (), item)() for item in items_data],
        Decimal(str(data.get("vat_rate", 0))),
    )
    quotation = Quotation(
        quote_no=data["quote_no"],
        status=QuoteStatus.DRAFT,
        product_line=data.get("product_line") or "BDR",
        project_name=data["project_name"],
        currency=data.get("currency") or "USD",
        payment_term_option=data.get("payment_term_option") or "CIA",
        payment_terms=data.get("payment_terms") or "",
        quote_date=data["quote_date"],
        expire_date=data["expire_date"],
        tax_label=data.get("tax_label") or "VAT",
        vat_rate=data.get("vat_rate") or 0,
        remarks_disclaimer=data.get("remarks_disclaimer") or "",
        issuer_company_name=data.get("issuer_company_name")
        or "OnePro Cloud Limited",
        issuer_contact_name=data["issuer_contact_name"],
        issuer_contact_email=data["issuer_contact_email"],
        issuer_contact_title=data.get("issuer_contact_title") or "",
        issuer_signature=data.get("issuer_signature") or "",
        client_company=data["client_company"],
        contact_person=data["contact_person"],
        email=data["email"],
        billing_company=data.get("billing_company") or data["client_company"],
        billing_contact=data.get("billing_contact") or data["contact_person"],
        billing_email=data.get("billing_email") or data["email"],
        created_by_email=data.get("created_by_email"),
        version_current=0,
        **totals,
    )
    quotation.save()
    for item in items_data:
        QuotationItem.objects.create(
            quotation=quotation,
            line_no=item["line_no"],
            type=coerce_item_type(item.get("type", "")),
            item_id=item.get("item_id"),
            name=item.get("name"),
            description=item.get("description"),
            qty=item.get("qty") or 0,
            list_price=item.get("list_price") or 0,
            discount_percent=item.get("discount_percent") or 0,
            net_unit_price=item.get("net_unit_price") or 0,
            extended_price=item.get("extended_price") or 0,
        )
    return quotation


def replace_items(
    quotation: Quotation, items_data: list[dict[str, Any]]
) -> None:
    quotation.items.all().delete()
    for item in items_data:
        QuotationItem.objects.create(
            quotation=quotation,
            line_no=item["line_no"],
            type=coerce_item_type(item.get("type", "")),
            item_id=item.get("item_id"),
            name=item.get("name"),
            description=item.get("description"),
            qty=item.get("qty") or 0,
            list_price=item.get("list_price") or 0,
            discount_percent=item.get("discount_percent") or 0,
            net_unit_price=item.get("net_unit_price") or 0,
            extended_price=item.get("extended_price") or 0,
        )


def create_version_snapshot(
    quotation: Quotation,
    operator_email: str | None,
    notes: str,
) -> QuotationVersion:
    """Persist a full quote snapshot as the next version row."""
    with transaction.atomic():
        locked = Quotation.objects.select_for_update().get(pk=quotation.pk)
        line_items = list(locked.items.all())
        totals = calculate_totals(
            line_items, Decimal(str(locked.vat_rate or 0))
        )
        for key, value in totals.items():
            setattr(locked, key, value)
        locked.save(update_fields=[*totals.keys(), "updated_at"])

        latest = (
            QuotationVersion.objects.filter(quotation=locked)
            .order_by("-version_no")
            .first()
        )
        snapshot = build_quotation_snapshot(locked, items=line_items)
        if (
            latest
            and latest.status == locked.status
            and latest.snapshot_json == snapshot
        ):
            locked.version_current = latest.version_no
            locked.save(update_fields=["version_current", "updated_at"])
            version = latest
        else:
            next_version_no = (latest.version_no + 1) if latest else 1
            version = QuotationVersion.objects.create(
                quotation=locked,
                version_no=next_version_no,
                status=locked.status,
                notes=(notes or "")[:2000],
                snapshot_json=snapshot,
                operator_email=operator_email,
            )
            locked.version_current = next_version_no
            locked.save(update_fields=["version_current", "updated_at"])

        quotation.version_current = locked.version_current
        for key, value in totals.items():
            setattr(quotation, key, value)
        return version
