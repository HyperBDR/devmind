from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class ParsedQuotationItem(BaseModel):
    line_no: int
    type: str
    item_id: str | None = None
    name: str | None = None
    description: str | None = None
    qty: Decimal = Decimal("0")
    list_price: Decimal = Decimal("0")
    discount_percent: Decimal = Decimal("0")
    net_unit_price: Decimal = Decimal("0")
    extended_price: Decimal = Decimal("0")


class ParsedQuotation(BaseModel):
    quote_no: str = ""
    product_line: str = "BDR"
    project_name: str = ""
    currency: str = "USD"
    payment_term_option: str = "CIA"
    payment_terms: str = ""
    quote_date: date | None = None
    expire_date: date | None = None
    tax_label: str = "VAT"
    vat_rate: Decimal = Decimal("0")
    remarks_disclaimer: str = ""
    issuer_company_name: str = "OnePro Cloud Limited"
    issuer_contact_name: str = ""
    issuer_contact_email: str = ""
    issuer_contact_title: str = ""
    client_company: str = ""
    contact_person: str = ""
    email: str = ""
    billing_company: str = ""
    billing_contact: str = ""
    billing_email: str = ""
    items: list[ParsedQuotationItem] = Field(default_factory=list)


class ParsedDocumentData(BaseModel):
    quotation: ParsedQuotation
    document_kind: str = "quotation"
    source_totals: dict[str, str] = Field(default_factory=dict)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    validation_errors: list[dict] = Field(default_factory=list)
    validation_warnings: list[dict] = Field(default_factory=list)
    confidence: Decimal = Decimal("0")
