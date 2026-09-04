from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth.models import User
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
    quotation_audit_label,
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
    quotation_quoted_by_facets,
    filter_quotation_list,
    quotation_product_line_facets,
)
from quotation.services.quotation_service import (
    FormalQuotationNumberError,
    QuotationNotFoundError,
    build_quotation,
    copy_quotation,
    formalize_quotation,
    get_next_auto_draft_quote_number,
    get_next_auto_quote_number,
    update_quotation,
)


def _ensure_access(user, quotation: Quotation) -> Response | None:
    if can_access_quotation(user, quotation):
        return None
    return forbidden_response()


QUOTATION_UPDATE_FIELDS = (
    "quote_no",
    "draft_quote_no",
    "numbering_mode",
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
        filters = dict(query_serializer.validated_data)
        current_user_email = user_display_email(request.user)
        quoted_by = filters.get("quoted_by")
        quoted_by_user = None
        if quoted_by == "me":
            filters["quoted_by"] = current_user_email
            quoted_by_user = request.user
        elif quoted_by:
            quoted_by_user = User.objects.filter(
                email__iexact=quoted_by,
                is_active=True,
            ).first()
        if quoted_by_user:
            filters["quoted_by_names"] = list(
                {
                    quoted_by_user.get_full_name().strip(),
                    quoted_by_user.username.strip(),
                }
                - {""}
            )
        page = filters["page"]
        page_size = int(filters["page_size"])
        queryset = filter_accessible_quotations(
            request.user,
            Quotation.objects.all(),
        )
        product_lines = quotation_product_line_facets(queryset, filters)
        currencies = quotation_currency_facets(queryset)
        creators = quotation_quoted_by_facets(
            queryset,
            current_user_email,
        )
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
                    "creators": creators,
                },
            }
        )

    def post(self, request):
        ser = QuotationCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        data["created_by_email"] = user_display_email(request.user)
        numbering_mode = data.pop("numbering_mode", "custom")
        draft_quote_no = data.pop("draft_quote_no", None)
        if draft_quote_no is None:
            draft_quote_no = data.pop("quote_no", "")
        else:
            data.pop("quote_no", None)
        data["quote_no"] = None
        data["numbering_mode"] = numbering_mode
        items = data.pop("items", [])
        for attempt in range(3):
            try:
                with transaction.atomic():
                    if numbering_mode == "auto":
                        draft_quote_no = get_next_auto_draft_quote_number(
                            data["product_line"],
                            data["quote_date"],
                        )
                    data["draft_quote_no"] = draft_quote_no or ""
                    quotation = build_quotation(data=data, items_data=items)
                break
            except IntegrityError:
                if attempt == 2:
                    return Response(
                        {"detail": "could not allocate a quotation draft"},
                        status=status.HTTP_409_CONFLICT,
                    )
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
        queryset = filter_accessible_quotations(
            request.user,
            parsed_quotation_queryset(),
        ).order_by(
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
        quote_numbers = list(
            filter_accessible_quotations(
                request.user,
                Quotation.objects.all(),
            )
            .exclude(status=QuoteStatus.DRAFT)
            .exclude(quote_no__isnull=True)
            .exclude(quote_no="")
            .values_list("quote_no", flat=True)
        )
        draft_quote_numbers = list(
            filter_accessible_quotations(
                request.user,
                Quotation.objects.filter(
                    status=QuoteStatus.DRAFT,
                    numbering_mode="auto",
                ),
            )
            .exclude(draft_quote_no="")
            .values_list("draft_quote_no", flat=True)
        )
        quote_numbers.extend(draft_quote_numbers)
        return Response(
            {
                "items": items,
                "line_item_history": line_item_history,
                "quote_numbers": quote_numbers,
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
        set_request_audit_target(
            request,
            target_label=quotation_audit_label(quotation),
        )
        return Response(QuotationSerializer(quotation).data)

    def post(self, request, quotation_id: str):
        quotation = (
            Quotation.objects.prefetch_related("items")
            .filter(pk=quotation_id)
            .first()
        )
        if not quotation:
            return Response({"detail": "quotation not found"}, status=404)
        denied = _ensure_access(request.user, quotation)
        if denied:
            return denied
        if quotation.source_type == QuotationSourceType.DOCUMENT_IMPORT:
            return Response(
                {"detail": "document-imported quotations cannot be copied"},
                status=status.HTTP_409_CONFLICT,
            )
        set_request_audit_target(
            request,
            target_label=quotation_audit_label(quotation),
        )
        for attempt in range(3):
            try:
                with transaction.atomic():
                    locked = Quotation.objects.prefetch_related("items").get(
                        pk=quotation_id,
                    )
                    copied = copy_quotation(
                        locked,
                        created_by_email=user_display_email(request.user),
                    )
                break
            except IntegrityError:
                if attempt == 2:
                    return Response(
                        {"detail": "could not create quotation draft"},
                        status=status.HTTP_409_CONFLICT,
                    )
        copied = self.get_object(copied.pk)
        set_request_audit_target(
            request,
            target_id=copied.pk,
            target_label=quotation_audit_label(copied),
        )
        return Response(QuotationSerializer(copied).data, status=201)

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
        set_request_audit_target(
            request,
            target_label=quotation_audit_label(quotation),
        )
        ser = QuotationUpdateSerializer(
            data=request.data,
            context={"quotation": quotation},
        )
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        changed_fields = _quotation_changed_fields(quotation, data)
        change_details = _quotation_change_details(quotation, data)
        for attempt in range(3):
            try:
                quotation, _version, _content_changed = update_quotation(
                    quotation_id,
                    data,
                    operator_email=user_display_email(request.user),
                    notes=data.get("notes") or "Updated quotation",
                )
                break
            except IntegrityError:
                if attempt == 2:
                    return Response(
                        {"detail": "could not allocate a quotation revision"},
                        status=status.HTTP_409_CONFLICT,
                    )
            except FormalQuotationNumberError as exc:
                return Response(
                    {"detail": str(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except QuotationNotFoundError:
                return Response(
                    {"detail": "quotation not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        quotation = self.get_object(quotation_id)
        set_request_audit_target(
            request,
            target_label=quotation_audit_label(quotation),
        )
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
        set_request_audit_target(
            request,
            target_label=quotation_audit_label(quotation),
        )
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
        set_request_audit_target(
            request,
            target_label=quotation_audit_label(quotation),
        )
        changed_fields = (
            ["status"]
            if quotation.status != QuoteStatus.GENERATED
            else []
        )
        if quotation.status == QuoteStatus.DRAFT or not quotation.quote_no:
            changed_fields.insert(0, "quote_no")
        ser = QuotationGenerateSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        try:
            for attempt in range(5):
                try:
                    formalize_quotation(
                        quotation,
                        operator_email=(
                            ser.validated_data.get("operator_email")
                            or user_display_email(request.user)
                        ),
                        notes=ser.validated_data.get("notes")
                        or "Generated quotation",
                        numbering_mode=ser.validated_data.get(
                            "numbering_mode"
                        ),
                        draft_quote_no=ser.validated_data.get(
                            "draft_quote_no"
                        ),
                    )
                    break
                except IntegrityError:
                    if attempt == 4:
                        raise
        except IntegrityError:
            return Response({"detail": "quote_no already exists"}, status=409)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        quotation = Quotation.objects.prefetch_related(
            "items", "documents__replicas", "versions"
        ).get(pk=quotation_id)
        set_request_audit_target(
            request,
            target_label=quotation_audit_label(quotation),
        )
        set_request_audit_changed_fields(request, changed_fields)
        return Response(QuotationSerializer(quotation).data)
