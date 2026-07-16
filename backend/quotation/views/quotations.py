from __future__ import annotations

from decimal import Decimal

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.models import Quotation, QuoteStatus
from quotation.permissions import can_view_all_quotations, user_display_email
from quotation.serializers import (
    QuotationCreateSerializer,
    QuotationGenerateSerializer,
    QuotationSerializer,
    QuotationUpdateSerializer,
)
from quotation.services.quotation_service import (
    build_quotation,
    calculate_totals,
    create_version_snapshot,
    replace_items,
)
from quotation.services.storage import delete_documents_after_commit


def _ensure_access(user, quotation: Quotation) -> Response | None:
    if can_view_all_quotations(user):
        return None
    if (
        quotation.created_by_email
        and quotation.created_by_email.lower() == user_display_email(user)
    ):
        return None
    return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)


class QuotationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Quotation.objects.prefetch_related(
            "items", "documents", "versions"
        ).all()
        if not can_view_all_quotations(request.user):
            qs = qs.filter(
                created_by_email__iexact=user_display_email(request.user)
            )
        status_value = request.query_params.get("status")
        if status_value:
            if status_value not in QuoteStatus.values:
                return Response({"detail": "invalid status"}, status=400)
            qs = qs.filter(status=status_value)
        try:
            page = max(int(request.query_params.get("page", 1)), 1)
            page_size = min(
                max(int(request.query_params.get("page_size", 20)), 1), 200
            )
        except (TypeError, ValueError):
            return Response({"detail": "invalid pagination"}, status=400)
        total = qs.count()
        items = qs[(page - 1) * page_size : page * page_size]
        return Response(
            {
                "items": QuotationSerializer(items, many=True).data,
                "total": total,
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
            "items", "documents", "versions"
        ).get(pk=quotation.pk)
        return Response(QuotationSerializer(quotation).data, status=201)


class QuotationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, quotation_id: str) -> Quotation | None:
        return (
            Quotation.objects.prefetch_related(
                "items", "documents", "versions"
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
        return Response(QuotationSerializer(quotation).data)

    def put(self, request, quotation_id: str):
        quotation = self.get_object(quotation_id)
        if not quotation:
            return Response({"detail": "quotation not found"}, status=404)
        denied = _ensure_access(request.user, quotation)
        if denied:
            return denied
        ser = QuotationUpdateSerializer(
            data=request.data,
            context={"quotation": quotation},
        )
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        previous_status = quotation.status
        for field in (
            "quote_no",
            "project_name",
            "product_line",
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
        ):
            if field in data:
                setattr(quotation, field, data[field])
        try:
            with transaction.atomic():
                if "items" in data:
                    replace_items(quotation, data["items"])
                    cache = getattr(
                        quotation, "_prefetched_objects_cache", None
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
                    "status" in data and data["status"] != previous_status
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
        return Response(QuotationSerializer(quotation).data)

    def delete(self, request, quotation_id: str):
        quotation = self.get_object(quotation_id)
        if not quotation:
            return Response({"detail": "quotation not found"}, status=404)
        denied = _ensure_access(request.user, quotation)
        if denied:
            return denied
        storage_keys = list(
            quotation.documents.exclude(storage_key="").values_list(
                "storage_key",
                flat=True,
            )
        )
        with transaction.atomic():
            quotation.delete()
            delete_documents_after_commit(storage_keys)
        return Response(status=status.HTTP_204_NO_CONTENT)


class QuotationGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quotation_id: str):
        quotation = (
            Quotation.objects.prefetch_related(
                "items", "documents", "versions"
            )
            .filter(pk=quotation_id)
            .first()
        )
        if not quotation:
            return Response({"detail": "quotation not found"}, status=404)
        denied = _ensure_access(request.user, quotation)
        if denied:
            return denied
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
            "items", "documents", "versions"
        ).get(pk=quotation_id)
        return Response(QuotationSerializer(quotation).data)
