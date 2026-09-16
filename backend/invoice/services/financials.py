"""Monetary calculations for manually created invoices."""

from __future__ import annotations

from decimal import Decimal

from quotation.services.financials import round_money


def calculate_invoice_amounts(
    items: list[dict],
    tax_rate: Decimal,
) -> tuple[list[dict], dict[str, Decimal]]:
    """Calculate trusted line and invoice totals from quantity and price."""
    calculated_items = []
    subtotal = Decimal("0")
    tax_amount = Decimal("0")
    for item in items:
        calculated = dict(item)
        net_amount = round_money(
            Decimal(item["quantity"]) * Decimal(item["unit_price"])
        )
        line_tax = round_money(
            net_amount * Decimal(tax_rate) / Decimal("100")
        )
        calculated.update(
            discount_amount=Decimal("0"),
            net_amount=net_amount,
            tax_rate=tax_rate,
            tax_amount=line_tax,
            total_amount=round_money(net_amount + line_tax),
        )
        calculated_items.append(calculated)
        subtotal += net_amount
        tax_amount += line_tax
    subtotal = round_money(subtotal)
    tax_amount = round_money(tax_amount)
    return calculated_items, {
        "subtotal_amount": subtotal,
        "tax_amount": tax_amount,
        "total_amount": round_money(subtotal + tax_amount),
    }
