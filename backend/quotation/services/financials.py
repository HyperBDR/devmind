"""Model-independent monetary calculations for sales documents."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable


def round_money(value: Decimal) -> Decimal:
    """Round one monetary value to cents using half-up rounding."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _item_type_value(raw: Any) -> str:
    return str(getattr(raw, "value", raw) or "")


def calculate_document_totals(
    items: Iterable[Any],
    vat_rate: Decimal,
    software_type: str = "Software",
    tax_mode: str = "add",
    deduction_amount: Decimal = Decimal("0"),
) -> dict[str, Decimal]:
    """Calculate category subtotals, VAT, and the grand total."""
    materialized_items = tuple(items)
    software_subtotal = round_money(
        sum(
            (
                Decimal(str(getattr(item, "extended_price", 0)))
                for item in materialized_items
                if _item_type_value(getattr(item, "type", ""))
                == software_type
            ),
            Decimal("0"),
        )
    )
    others_subtotal = round_money(
        sum(
            (
                Decimal(str(getattr(item, "extended_price", 0)))
                for item in materialized_items
                if _item_type_value(getattr(item, "type", ""))
                != software_type
            ),
            Decimal("0"),
        )
    )
    subtotal_before_vat = round_money(
        software_subtotal + others_subtotal
    )
    vat_amount = round_money(
        subtotal_before_vat * (Decimal(str(vat_rate)) / Decimal("100"))
    )
    tax_adjusted_total = (
        subtotal_before_vat - vat_amount
        if tax_mode == "subtract"
        else subtotal_before_vat + vat_amount
    )
    deduction_amount = min(
        round_money(Decimal(str(deduction_amount or 0))),
        max(Decimal("0"), tax_adjusted_total),
    )
    grand_total = round_money(tax_adjusted_total - deduction_amount)
    return {
        "software_subtotal": software_subtotal,
        "others_subtotal": others_subtotal,
        "subtotal_before_vat": subtotal_before_vat,
        "vat_amount": vat_amount,
        "deduction_amount": deduction_amount,
        "grand_total": grand_total,
    }
