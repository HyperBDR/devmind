from __future__ import annotations

from django.db.models import (
    Case,
    CharField,
    Count,
    Exists,
    F,
    OuterRef,
    Q,
    QuerySet,
    When,
)

from quotation.models import (
    DocumentAsset,
    DocumentParseResult,
    DocumentParseStatus,
    DocumentReplica,
    Quotation,
    QuotationSourceType,
    QuotationVersion,
    ReplicaSyncStatus,
)


SEARCH_FIELDS = (
    "quote_no",
    "draft_quote_no",
    "source_quote_no",
    "project_name",
    "client_company",
    "contact_person",
)
PRODUCT_LINE_FACET_LIMIT = 100


def quotation_currency_facets(
    queryset: QuerySet[Quotation],
) -> list[str]:
    """Return all non-empty currencies from accessible quotations."""
    return list(
        queryset.exclude(currency="")
        .values_list("currency", flat=True)
        .order_by("currency")
        .distinct()
    )


def filter_quotation_list(
    queryset: QuerySet[Quotation],
    filters: dict,
) -> QuerySet[Quotation]:
    """Apply index-friendly quotation list filters."""
    search = filters.get("search", "")
    if search:
        search_query = Q()
        for field in SEARCH_FIELDS:
            search_query |= Q(**{f"{field}__icontains": search})
        queryset = queryset.filter(search_query)

    for field in ("status", "product_line", "source_type", "currency"):
        value = filters.get(field)
        if value:
            queryset = queryset.filter(**{field: value})

    product_line_name = filters.get("product_line_name")
    if product_line_name:
        queryset = queryset.filter(
            Q(product_line_name=product_line_name)
            | Q(
                product_line_name="",
                product_line=product_line_name,
            )
        )

    created_from = filters.get("created_from")
    if created_from:
        queryset = queryset.filter(quote_date__gte=created_from)

    created_to = filters.get("created_to")
    if created_to:
        queryset = queryset.filter(quote_date__lte=created_to)

    return queryset


def quotation_product_line_facets(
    queryset: QuerySet[Quotation],
    filters: dict,
) -> list[str]:
    """Return bounded business product lines from accessible matches."""
    facet_filters = {
        key: value
        for key, value in filters.items()
        if key != "product_line_name"
    }
    queryset = filter_quotation_list(queryset, facet_filters)
    product_line = Case(
        When(product_line_name="", then=F("product_line")),
        default=F("product_line_name"),
        output_field=CharField(),
    )
    return list(
        queryset.annotate(facet_product_line=product_line)
        .exclude(facet_product_line="")
        .values_list("facet_product_line", flat=True)
        .order_by("facet_product_line")
        .distinct()[:PRODUCT_LINE_FACET_LIMIT]
    )


def annotate_quotation_list(
    queryset: QuerySet[Quotation],
) -> QuerySet[Quotation]:
    """Add the item count without loading quotation line items."""
    return queryset.annotate(item_count=Count("items", distinct=True))


def attach_quotation_document_summaries(
    quotations: list[Quotation],
) -> None:
    """Attach document summary attributes with one fixed batch query."""
    for quotation in quotations:
        quotation.latest_excel_document_id = None
        quotation.latest_pdf_document_id = None
        quotation.source_document_type = None
        quotation.source_document = None
        quotation.available_versions = []
    if not quotations:
        return

    quotation_ids = [quote.pk for quote in quotations]
    active_replica = DocumentReplica.objects.filter(
        asset_id=OuterRef("pk"),
        sync_status=ReplicaSyncStatus.SYNCED,
        revoked_at__isnull=True,
    ).exclude(remote_file_token="")
    linked_parse = DocumentParseResult.objects.filter(
        asset_id=OuterRef("pk"),
        quotation_id=OuterRef("quotation_id"),
        status__in=(
            DocumentParseStatus.CONFIRMED,
            DocumentParseStatus.REVIEW_REQUIRED,
        ),
    )
    documents = (
        DocumentAsset.objects.filter(
            quotation_id__in=quotation_ids,
            doc_type__in=("excel", "pdf"),
        )
        .annotate(
            has_active_replica=Exists(active_replica),
            has_confirmed_parse=Exists(linked_parse),
        )
        .only(
            "id",
            "quotation_id",
            "doc_type",
            "file_name",
            "source",
            "feishu_file_token",
            "created_at",
        )
        .order_by("quotation_id", "-created_at", "-id")
    )
    quotations_by_id = {quote.pk: quote for quote in quotations}
    for document in documents:
        quotation = quotations_by_id[document.quotation_id]
        if (
            quotation.source_type == QuotationSourceType.DOCUMENT_IMPORT
            and quotation.source_document is None
            and document.source in {"feishu", "local"}
            and document.has_confirmed_parse
        ):
            quotation.source_document_type = document.doc_type
            quotation.source_document = {
                "id": document.pk,
                "doc_type": document.doc_type,
                "file_name": document.file_name,
            }
        field = f"latest_{document.doc_type}_document_id"
        if getattr(quotation, field) is not None:
            continue
        if document.has_active_replica or document.feishu_file_token:
            setattr(quotation, field, document.pk)

    imported_ids = [
        quotation.pk
        for quotation in quotations
        if quotation.source_type == QuotationSourceType.DOCUMENT_IMPORT
    ]
    versions = QuotationVersion.objects.filter(
        quotation_id__in=imported_ids,
    ).values(
        "quotation_id",
        "version_no",
        "status",
        "created_at",
    ).order_by("quotation_id", "-version_no")
    for version in versions:
        quotations_by_id[version["quotation_id"]].available_versions.append(
            {
                "version_no": version["version_no"],
                "status": version["status"],
                "created_at": version["created_at"],
            }
        )
    for quotation in quotations_by_id.values():
        if quotation.source_document and quotation.available_versions:
            quotation.source_document["version_no"] = min(
                version["version_no"]
                for version in quotation.available_versions
            )
