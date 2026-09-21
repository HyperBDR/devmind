from __future__ import annotations

from itertools import chain

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from invoice.models import Invoice
from invoice.permissions import has_invoice_access, invoice_visibility_filter
from quotation.access import filter_accessible_quotations
from quotation.models import Quotation


def _customer_record(
    company: str,
    contact_name: str,
    email: str,
    phone: str,
    updated_at,
) -> dict:
    return {
        "company": (company or "").strip(),
        "contact_name": (contact_name or "").strip(),
        "email": (email or "").strip(),
        "phone": (phone or "").strip(),
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


def _build_customer_summary(records) -> list[dict]:
    grouped = {}
    for record in records:
        company = record["company"]
        if not company:
            continue
        key = company.casefold()
        customer = grouped.setdefault(
            key,
            {
                "company": company,
                "contacts": {},
                "record_count": 0,
                "updated_at": record["updated_at"],
            },
        )
        customer["record_count"] += 1
        if record["contact_name"] or record["email"] or record["phone"]:
            contact_key = (
                f"{record['contact_name']}|{record['email']}"
            ).casefold()
            contact = customer["contacts"].setdefault(
                contact_key,
                {
                    "name": record["contact_name"] or "未填写联系人",
                    "email": record["email"] or "-",
                    "phone": record["phone"] or "-",
                    "record_count": 0,
                },
            )
            contact["record_count"] += 1
        updated_at = record["updated_at"]
        if updated_at and (
            not customer["updated_at"]
            or updated_at > customer["updated_at"]
        ):
            customer["updated_at"] = updated_at

    return [
        {
            "company": customer["company"],
            "contacts": list(customer["contacts"].values()),
            "record_count": customer["record_count"],
            "updated_at": customer["updated_at"],
        }
        for customer in sorted(
            grouped.values(),
            key=lambda item: item["company"].casefold(),
        )
    ]


class CustomerSummaryView(APIView):
    """Return a compact, permission-filtered customer aggregation."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        quotation_rows = filter_accessible_quotations(
            request.user,
            Quotation.objects.all(),
        ).filter(
            client_company__gt="",
        ).values(
            "client_company",
            "contact_person",
            "email",
            "created_at",
        )
        quotation_records = (
            _customer_record(
                row["client_company"],
                row["contact_person"],
                row["email"],
                "",
                row["created_at"],
            )
            for row in quotation_rows.iterator(chunk_size=500)
        )
        invoice_records = ()
        if has_invoice_access(request.user):
            invoice_rows = Invoice.objects.filter(
                invoice_visibility_filter(request.user),
            ).filter(
                customer_name__gt="",
            ).values(
                "customer_name",
                "customer_contact_person",
                "customer_contact_email",
                "customer_contact_phone",
                "contact_person",
                "contact_email",
                "created_at",
                "updated_at",
            )
            invoice_records = (
                _customer_record(
                    row["customer_name"],
                    row["customer_contact_person"] or row["contact_person"],
                    row["customer_contact_email"] or row["contact_email"],
                    row["customer_contact_phone"],
                    row["updated_at"] or row["created_at"],
                )
                for row in invoice_rows.iterator(chunk_size=500)
            )
        records = chain(quotation_records, invoice_records)
        return Response({"customers": _build_customer_summary(records)})
