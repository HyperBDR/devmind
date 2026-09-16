from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class ParsedInvoiceItem(BaseModel):
    """Normalized product or service line extracted from an invoice."""

    line_no: int
    product_code: str = ""
    product_name: str = ""
    description: str = ""
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    net_amount: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    total_amount: Decimal = Decimal("0")


class ParsedInvoice(BaseModel):
    """Canonical invoice fields shared by PDF and manual import paths."""

    invoice_no: str = ""
    invoice_date: date | None = None
    due_date: date | None = None
    currency: str = "USD"
    seller_name: str = ""
    seller_tax_id: str = ""
    seller_address: str = ""
    seller_website: str = ""
    seller_email: str = ""
    customer_name: str = ""
    customer_tax_id: str = ""
    customer_address: str = ""
    customer_contact_person: str = ""
    customer_contact_email: str = ""
    customer_contact_phone: str = ""
    contact_person: str = ""
    contact_email: str = ""
    purchase_order_no: str = ""
    payment_terms: str = ""
    region: str = ""
    sales_owner: str = ""
    tax_rate: Decimal = Decimal("0")
    subtotal_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    total_amount: Decimal = Decimal("0")
    notes: str = ""
    additional_notes: str = ""
    remarks: str = ""
    bank_account_name: str = ""
    bank_name: str = ""
    bank_address: str = ""
    bank_account_number: str = ""
    bank_code: str = ""
    bank_branch_code: str = ""
    bank_swift_code: str = ""
    remittance_instruction: str = ""
    signatory_name: str = ""
    signatory_title: str = ""
    items: list[ParsedInvoiceItem] = Field(default_factory=list)


class ParsedInvoiceDocumentData(BaseModel):
    """Reviewable parser output with confidence and validation details."""

    invoice: ParsedInvoice
    document_kind: str = "invoice"
    field_confidence: dict[str, float] = Field(default_factory=dict)
    validation_errors: list[dict] = Field(default_factory=list)
    validation_warnings: list[dict] = Field(default_factory=list)
    confidence: Decimal = Decimal("0")
