from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.access import (
    can_access_quotation,
    filter_accessible_quotations,
    forbidden_response,
)
from quotation.audit import (
    set_request_audit_change_details,
    set_request_audit_changed_fields,
    set_request_audit_target,
)
from quotation.models import Quotation, QuotationSourceType, QuoteStatus
from quotation.permissions import user_display_email
from quotation.serializers import (
    QuotationCreateSerializer,
    QuotationFormContextQuerySerializer,
    QuotationFormContextSerializer,
    QuotationGenerateSerializer,
    QuotationLineItemHistorySerializer,
    QuotationListQuerySerializer,
    QuotationListSerializer,
    QuotationSerializer,
    QuotationUpdateSerializer,
)
from quotation.services.form_context import (
    build_line_item_description_history,
    parsed_quotation_queryset,
)
from quotation.services.quotation_queries import (
    annotate_quotation_list,
    attach_quotation_document_summaries,
    quotation_currency_facets,
    filter_quotation_list,
    quotation_product_line_facets,
    quotation_currency_facets,
)
from quotation.services.quotation_service import (
    build_quotation,
    calculate_totals,
    create_version_snapshot,
    replace_items,
)


def _ensure_access(user, quotation: Quotation) -> Response | None:
    if can_access_quotation(user, quotation):
        return None
    return forbidden_response()


QUOTATION_UPDATE_FIELDS = (
    "quote_no",
    "project_name",
    "product_line",
    "product_line_name",
    "currency",
    "payment_term_option",
    "payment_terms",
    "quote_date",
    "expire_date",
    "tax_label",
    "vat_rate",
    "remarks_disclaimer",
    "issuer_company_name",
    "issuer_contact_name",
    "issuer_contact_email",
    "issuer_contact_title",
    "issuer_signature",
    "client_company",
    "contact_person",
    "email",
    "billing_company",
    "billing_contact",
    "billing_email",
    "status",
)
QUOTATION_ITEM_FIELDS = (
    "line_no",
    "type",
    "item_id",
    "name",
    "description",
    "qty",
    "list_price",
    "discount_percent",
    "net_unit_price",
    "extended_price",
)


def _item_audit_snapshot(item) -> tuple:
    """Return a stable comparable representation of one quotation item."""
    values = []
    for field in QUOTATION_ITEM_FIELDS:
        value = (
            item.get(field)
            if isinstance(item, dict)
            else getattr(item, field)
        )
        if field in {"item_id", "name", "description"}:
            value = value or ""
        values.append(value)
    return tuple(values)


def _audit_json_value(value):
    """Return a stable JSON-safe value for audit old/new details."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): _audit_json_value(raw_value)
            for key, raw_value in value.items()
        }
    if isinstance(value, list):
        return [_audit_json_value(item) for item in value]
    return value


def _item_audit_detail(item) -> dict:
    """Return a JSON-safe quotation item snapshot for audit details."""
    return {
        field: _audit_json_value(
            item.get(field) if isinstance(item, dict) else getattr(item, field)
        )
        for field in QUOTATION_ITEM_FIELDS
    }


def _quotation_changed_fields(quotation: Quotation, data: dict) -> list[str]:
    """Return only fields whose persisted business values will change."""
    fields = [
        field
        for field in QUOTATION_UPDATE_FIELDS
        if field in data and getattr(quotation, field) != data[field]
    ]
    if "items" in data:
        current_items = [
            _item_audit_snapshot(item)
            for item in quotation.items.all()
        ]
        incoming_items = [
            _item_audit_snapshot(item)
            for item in data["items"]
        ]
        if current_items != incoming_items:
            fields.append("items")
    return fields


def _quotation_change_details(quotation: Quotation, data: dict) -> dict:
    """Return JSON-style old/new details for changed quotation fields."""
    changes = {}
    for field in QUOTATION_UPDATE_FIELDS:
        if field not in data:
            continue
        current = getattr(quotation, field)
        incoming = data[field]
        if current != incoming:
            changes[field] = {
                "old": _audit_json_value(current),
                "new": _audit_json_value(incoming),
            }

    if "items" in data:
        current_items = [
            _item_audit_snapshot(item)
            for item in quotation.items.all()
        ]
        incoming_items = [
            _item_audit_snapshot(item)
            for item in data["items"]
        ]
        if current_items != incoming_items:
            changes["items"] = {
                "old": [
                    _item_audit_detail(item)
                    for item in quotation.items.all()
                ],
                "new": [
                    _item_audit_detail(item)
                    for item in data["items"]
                ],
            }
    return changes


class QuotationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query_serializer = QuotationListQuerySerializer(
            data=request.query_params
        )
        if not query_serializer.is_valid():
            pagination_errors = {"page", "page_size"} & set(
                query_serializer.errors
            )
            if pagination_errors:
                return Response(
                    {"detail": "invalid pagination"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                query_serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )
        filters = query_serializer.validated_data
        page = filters["page"]
        page_size = int(filters["page_size"])
        queryset = filter_accessible_quotations(
            request.user,
            Quotation.objects.all(),
        )
        product_lines = quotation_product_line_facets(queryset, filters)
        currencies = quotation_currency_facets(queryset)
        queryset = filter_quotation_list(queryset, filters)
        total = queryset.count()
        page_start = (page - 1) * page_size
        items = list(
            annotate_quotation_list(queryset).order_by(
                "-created_at",
                "-id",
            )[page_start : page_start + page_size]
        )
        attach_quotation_document_summaries(items)
        total_pages = (total + page_size - 1) // page_size
        return Response(
            {
                "items": QuotationListSerializer(items, many=True).data,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "facets": {
                    "product_lines": product_lines,
                    "currencies": currencies,
                },
            }
        )

    def post(self, request):
        ser = QuotationCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        data["created_by_email"] = user_display_email(request.user)
        items = data.pop("items", [])
        try:
            with transaction.atomic():
                quotation = build_quotation(data=data, items_data=items)
        except IntegrityError:
            return Response({"detail": "quote_no already exists"}, status=409)
        quotation = Quotation.objects.prefetch_related(
            "items", "documents__replicas", "versions"
        ).get(pk=quotation.pk)
        return Response(QuotationSerializer(quotation).data, status=201)


class QuotationFormContextView(APIView):
    """Return paginated parsed quotation history used by the create form."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        query_serializer = QuotationFormContextQuerySerializer(
            data=request.query_params,
        )
        query_serializer.is_valid(raise_exception=True)
        page = query_serializer.validated_data["page"]
        page_size = int(query_serializer.validated_data["page_size"])
        queryset = parsed_quotation_queryset().order_by(
            "-created_at",
            "-id",
        )
        total = queryset.count()
        page_start = (page - 1) * page_size
        page_queryset = queryset[page_start : page_start + page_size]
        items = QuotationFormContextSerializer(
            page_queryset,
            many=True,
        ).data
        line_item_history = QuotationLineItemHistorySerializer(
            build_line_item_description_history(page_queryset),
            many=True,
        ).data
        return Response(
            {
                "items": items,
                "line_item_history": line_item_history,
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_more": page_start + page_size < total,
            }
        )


class QuotationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, quotation_id: str) -> Quotation | None:
        return (
            Quotation.objects.prefetch_related(
                "items",
                "documents__replicas",
                "versions",
            )
            .filter(pk=quotation_id)
            .first()
        )

    def get(self, request, quotation_id: str):
        quotation = self.get_object(quotation_id)
        if not quotation:
            return Response({"detail": "quotation not found"}, status=404)
        denied = _ensure_access(request.user, quotation)
        if denied:
            return denied
        set_request_audit_target(request, target_label=quotation.quote_no)
        return Response(QuotationSerializer(quotation).data)

    def put(self, request, quotation_id: str):
        quotation = self.get_object(quotation_id)
        if not quotation:
            return Response({"detail": "quotation not found"}, status=404)
        denied = _ensure_access(request.user, quotation)
        if denied:
            return denied
        if quotation.source_type == QuotationSourceType.DOCUMENT_IMPORT:
            return Response(
                {"detail": "document-imported quotations are read-only"},
                status=409,
            )
        set_request_audit_target(request, target_label=quotation.quote_no)
        ser = QuotationUpdateSerializer(
            data=request.data,
            context={"quotation": quotation},
        )
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        changed_fields = _quotation_changed_fields(quotation, data)
        change_details = _quotation_change_details(quotation, data)
        previous_status = quotation.status
        for field in QUOTATION_UPDATE_FIELDS:
            if field in data:
                setattr(quotation, field, data[field])
        try:
            with transaction.atomic():
                if "items" in data:
                    replace_items(quotation, data["items"])
                    cache = getattr(
                        quotation,
                        "_prefetched_objects_cache",
                        None,
                    )
                    if cache is not None:
                        cache.pop("items", None)
                if "items" in data or "vat_rate" in data:
                    items_for_totals = (
                        data["items"]
                        if "items" in data
                        else [
                            {
                                "type": item.type,
                                "extended_price": item.extended_price,
                            }
                            for item in quotation.items.all()
                        ]
                    )
                    totals = calculate_totals(
                        [type("I", (), item)() for item in items_for_totals],
                        Decimal(str(quotation.vat_rate)),
                    )
                    for k, v in totals.items():
                        setattr(quotation, k, v)
                status_changed = (
                    "status" in data
                    and data["status"] != previous_status
                )
                items_changed = "items" in data
                quotation.save()
                skip_version = bool(data.get("skip_version"))
                if not skip_version and (status_changed or items_changed):
                    default_notes = (
                        f"Updated status to {data['status']}"
                        if status_changed
                        else "Updated quotation content"
                    )
                    create_version_snapshot(
                        quotation,
                        operator_email=user_display_email(request.user),
                        notes=data.get("notes") or default_notes,
                    )
        except IntegrityError:
            return Response({"detail": "quote_no already exists"}, status=409)
        quotation = self.get_object(quotation_id)
        set_request_audit_target(request, target_label=quotation.quote_no)
        set_request_audit_changed_fields(request, changed_fields)
        set_request_audit_change_details(request, change_details)
        return Response(QuotationSerializer(quotation).data)

    def delete(self, request, quotation_id: str):
        quotation = self.get_object(quotation_id)
        if not quotation:
            return Response({"detail": "quotation not found"}, status=404)
        denied = _ensure_access(request.user, quotation)
        if denied:
            return denied
        if quotation.source_type == QuotationSourceType.DOCUMENT_IMPORT:
            return Response(
                {"detail": "document-imported quotations cannot be deleted"},
                status=409,
            )
        set_request_audit_target(request, target_label=quotation.quote_no)
        try:
            with transaction.atomic():
                quotation.delete()
        except ProtectedError:
            return Response(
                {"detail": "quotation has active export jobs"},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class QuotationGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quotation_id: str):
        quotation = (
            Quotation.objects.prefetch_related(
                "items",
                "documents__replicas",
                "versions",
            )
            .filter(pk=quotation_id)
            .first()
        )
        if not quotation:
            return Response({"detail": "quotation not found"}, status=404)
        denied = _ensure_access(request.user, quotation)
        if denied:
            return denied
        set_request_audit_target(request, target_label=quotation.quote_no)
        changed_fields = (
            ["status"]
            if quotation.status != QuoteStatus.GENERATED
            else []
        )
        ser = QuotationGenerateSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        quotation.status = QuoteStatus.GENERATED
        quotation.save(update_fields=["status", "updated_at"])
        create_version_snapshot(
            quotation,
            operator_email=ser.validated_data.get("operator_email")
            or user_display_email(request.user),
            notes=ser.validated_data.get("notes") or "Generated quotation",
        )
        quotation = Quotation.objects.prefetch_related(
            "items", "documents__replicas", "versions"
        ).get(pk=quotation_id)
        set_request_audit_changed_fields(request, changed_fields)
        return Response(QuotationSerializer(quotation).data)
