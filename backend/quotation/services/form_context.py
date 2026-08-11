from __future__ import annotations

from django.db.models import QuerySet

from quotation.models import (
    Quotation,
    QuotationItem,
    QuotationSourceType,
)


LINE_ITEM_HISTORY_LIMIT = 300
LINE_ITEM_HISTORY_SCAN_LIMIT = 1000


def parsed_quotation_queryset() -> QuerySet[Quotation]:
    """Return all quotations created by document parsing."""
    return Quotation.objects.filter(
        source_type=QuotationSourceType.DOCUMENT_IMPORT,
    )


def build_line_item_description_history(
    quotations: QuerySet[Quotation],
) -> list[dict]:
    """Return bounded, deduplicated parsed line-item descriptions."""
    queryset = (
        QuotationItem.objects.filter(quotation__in=quotations)
        .select_related("quotation")
        .order_by(
            "-quotation__created_at",
            "-quotation_id",
            "line_no",
        )[:LINE_ITEM_HISTORY_SCAN_LIMIT]
    )
    history: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    for item in queryset:
        description = (item.description or item.name or "").strip()
        if not description:
            continue
        item_type = "Software" if item.type == "Software" else "Other"
        currency = item.quotation.currency
        key = (
            currency.casefold(),
            item_type.casefold(),
            description.casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        history.append(
            {
                "type": item_type,
                "description": description,
                "list_price": item.list_price,
                "currency": currency,
            }
        )
        if len(history) >= LINE_ITEM_HISTORY_LIMIT:
            break

    return history
