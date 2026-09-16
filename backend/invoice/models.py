from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


def _uuid() -> str:
    return str(uuid.uuid4())


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ISSUED = "issued", "Issued"
    PAID = "paid", "Paid"
    VOID = "void", "Void"
    CANCELLED = "cancelled", "Cancelled"


class InvoiceSourceType(models.TextChoices):
    MANUAL = "manual", "Manual"
    PDF_UPLOAD = "pdf_upload", "PDF upload"
    FEISHU = "feishu", "Feishu"


class InvoiceNumberingMode(models.TextChoices):
    AUTO = "auto", "Automatic"
    CUSTOM = "custom", "Custom"


class InvoiceDocumentKind(models.TextChoices):
    INVOICE = "invoice", "Invoice"
    DELIVERY_NOTE = "delivery_note", "Delivery note"
    WITHHOLDING_TAX = "withholding_tax", "Withholding tax"
    PROFORMA_INVOICE = "proforma_invoice", "Proforma invoice"
    REFUND = "refund", "Refund"


class InvoiceDocumentType(models.TextChoices):
    PDF = "pdf", "PDF"
    IMAGE = "image", "Image"


class InvoiceDocumentPurpose(models.TextChoices):
    SOURCE = "source", "Source"
    SUPPORTING = "supporting", "Supporting document"
    ISSUED = "issued", "Issued invoice"


class InvoiceDocumentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class InvoiceParseStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    READY = "ready", "Ready"
    REVIEW_REQUIRED = "review_required", "Review required"
    CONFIRMED = "confirmed", "Confirmed"
    NOT_INVOICE = "not_invoice", "Not an invoice"
    FAILED = "failed", "Failed"


class InvoiceSyncStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class InvoiceSyncTrigger(models.TextChoices):
    MANUAL = "manual", "Manual"
    PERIODIC = "periodic", "Periodic"


class InvoiceAccessRole(models.TextChoices):
    USER = "invoice_user", "Invoice user"
    ADMIN = "invoice_admin", "Invoice administrator"


class InvoiceAccessGrant(models.Model):
    """Administrator-granted access to the Sales and Invoice workspace."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invoice_access_grants",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="granted_invoice_access",
    )
    role = models.CharField(
        max_length=20,
        choices=InvoiceAccessRole.choices,
        default=InvoiceAccessRole.ADMIN,
    )
    expires_at = models.DateTimeField(blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "invoice_access_grants"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_active=True),
                name="invoice_active_access_user_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "is_active", "expires_at"],
                name="invoice_access_user_active",
            ),
        ]


class InvoiceNumberSequence(models.Model):
    """Locked product-line and date sequence for automatic numbers."""

    period = models.CharField(max_length=40, unique=True)
    last_value = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "invoice_number_sequences"

    def __str__(self):
        return f"{self.period}: {self.last_value}"


class Invoice(models.Model):
    """Sales invoice record used as the source for sales analytics."""

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=_uuid,
        editable=False,
    )
    invoice_no = models.CharField(max_length=120, blank=True, default="")
    document_kind = models.CharField(
        max_length=30,
        choices=InvoiceDocumentKind.choices,
        default=InvoiceDocumentKind.INVOICE,
        db_index=True,
    )
    numbering_mode = models.CharField(
        max_length=20,
        choices=InvoiceNumberingMode.choices,
        default=InvoiceNumberingMode.CUSTOM,
    )
    product_line = models.CharField(max_length=40, default="BDR")
    invoice_date = models.DateField(blank=True, null=True, db_index=True)
    due_date = models.DateField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.DRAFT,
        db_index=True,
    )
    revision_no = models.PositiveIntegerField(default=0)
    source_type = models.CharField(
        max_length=20,
        choices=InvoiceSourceType.choices,
        default=InvoiceSourceType.MANUAL,
        db_index=True,
    )
    currency = models.CharField(max_length=3, default="USD")
    seller_name = models.CharField(max_length=255, blank=True, default="")
    seller_tax_id = models.CharField(max_length=120, blank=True, default="")
    seller_address = models.TextField(blank=True, default="")
    seller_website = models.CharField(max_length=255, blank=True, default="")
    seller_email = models.EmailField(blank=True, default="")
    customer_name = models.CharField(max_length=255, blank=True, default="")
    customer_tax_id = models.CharField(max_length=120, blank=True, default="")
    customer_address = models.TextField(blank=True, default="")
    customer_contact_person = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )
    customer_contact_email = models.EmailField(blank=True, default="")
    customer_contact_phone = models.CharField(
        max_length=60,
        blank=True,
        default="",
    )
    contact_person = models.CharField(max_length=120, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")
    purchase_order_no = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )
    payment_terms = models.CharField(max_length=255, blank=True, default="")
    region = models.CharField(max_length=120, blank=True, default="")
    sales_owner = models.CharField(max_length=255, blank=True, default="")
    tax_rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=0,
    )
    subtotal_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
    )
    tax_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
    )
    total_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
    )
    notes = models.TextField(blank=True, default="")
    additional_notes = models.TextField(blank=True, default="")
    remarks = models.TextField(blank=True, default="")
    bank_account_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    bank_name = models.CharField(max_length=255, blank=True, default="")
    bank_address = models.TextField(blank=True, default="")
    bank_account_number = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )
    bank_code = models.CharField(max_length=60, blank=True, default="")
    bank_branch_code = models.CharField(
        max_length=60,
        blank=True,
        default="",
    )
    bank_swift_code = models.CharField(
        max_length=60,
        blank=True,
        default="",
    )
    remittance_instruction = models.TextField(blank=True, default="")
    signatory_name = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )
    signatory_title = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )
    issuer_signature = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "invoices"
        ordering = ["-invoice_date", "-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["invoice_no"],
                condition=(
                    models.Q(document_kind=InvoiceDocumentKind.INVOICE)
                    & ~models.Q(invoice_no="")
                ),
                name="invoice_formal_number_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["currency", "status", "invoice_date"],
                name="invoice_dash_curr_stat_date",
            ),
            models.Index(
                fields=["customer_name", "invoice_date"],
                name="invoice_customer_date",
            ),
            models.Index(
                fields=["region", "invoice_date"],
                name="invoice_region_date",
            ),
            models.Index(
                fields=["document_kind", "status", "invoice_date"],
                name="invoice_kind_status_date",
            ),
        ]

    def __str__(self):
        return self.invoice_no


class InvoiceRevision(models.Model):
    """Snapshot of a formal invoice before a later revision."""

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=_uuid,
        editable=False,
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    revision_no = models.PositiveIntegerField()
    invoice_no = models.CharField(max_length=120)
    snapshot_json = models.JSONField(default=dict)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_revisions",
    )
    reason = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "invoice_revisions"
        ordering = ["-revision_no", "-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["invoice", "revision_no"],
                name="invoice_revision_no_unique",
            ),
        ]


class InvoiceItem(models.Model):
    """One product or service line on an invoice."""

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=_uuid,
        editable=False,
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items",
    )
    line_no = models.PositiveIntegerField()
    product_code = models.CharField(max_length=120, blank=True, default="")
    product_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=1,
    )
    unit_price = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=0,
    )
    discount_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
    )
    net_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
    )
    tax_rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=0,
    )
    tax_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
    )
    total_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
    )

    class Meta:
        db_table = "invoice_items"
        ordering = ["line_no", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["invoice", "line_no"],
                name="invoice_item_line_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["product_name", "invoice"],
                name="invoice_item_product",
            ),
        ]


class InvoiceDocument(models.Model):
    """Source or generated document retained with an invoice record."""

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=_uuid,
        editable=False,
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    file_name = models.CharField(max_length=255)
    storage_key = models.CharField(max_length=512, unique=True)
    content_type = models.CharField(max_length=120, blank=True, default="")
    document_type = models.CharField(
        max_length=20,
        choices=InvoiceDocumentType.choices,
        default=InvoiceDocumentType.PDF,
    )
    purpose = models.CharField(
        max_length=20,
        choices=InvoiceDocumentPurpose.choices,
        default=InvoiceDocumentPurpose.SOURCE,
        db_index=True,
    )
    size_bytes = models.PositiveBigIntegerField(default=0)
    content_hash = models.CharField(max_length=64, blank=True, default="")
    feishu_file_token = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    feishu_folder_token = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    feishu_url = models.URLField(max_length=1000, blank=True, default="")
    feishu_file_owned = models.BooleanField(default=False)
    feishu_owner_connection_id = models.CharField(
        max_length=36,
        blank=True,
        default="",
    )
    status = models.CharField(
        max_length=20,
        choices=InvoiceDocumentStatus.choices,
        default=InvoiceDocumentStatus.ACTIVE,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_invoice_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "invoice_documents"
        constraints = [
            models.UniqueConstraint(
                fields=["feishu_file_token"],
                condition=~models.Q(feishu_file_token=""),
                name="invoice_document_feishu_token_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="invoice_doc_status_created",
            ),
        ]


class InvoiceSyncRun(models.Model):
    """One read-only synchronization run for the configured Feishu folder."""

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=_uuid,
        editable=False,
    )
    status = models.CharField(
        max_length=20,
        choices=InvoiceSyncStatus.choices,
        default=InvoiceSyncStatus.PENDING,
        db_index=True,
    )
    trigger = models.CharField(
        max_length=20,
        choices=InvoiceSyncTrigger.choices,
        default=InvoiceSyncTrigger.MANUAL,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_sync_runs",
    )
    discovered_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    reused_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    error_message = models.CharField(max_length=500, blank=True, default="")
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "invoice_sync_runs"
        ordering = ["-created_at", "-id"]


class InvoiceParseResult(models.Model):
    """Versioned normalized output and confidence data for one source file."""

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=_uuid,
        editable=False,
    )
    document = models.ForeignKey(
        InvoiceDocument,
        on_delete=models.CASCADE,
        related_name="parse_results",
    )
    parser_name = models.CharField(max_length=120)
    parser_version = models.CharField(max_length=40)
    content_hash = models.CharField(max_length=64)
    status = models.CharField(
        max_length=20,
        choices=InvoiceParseStatus.choices,
        default=InvoiceParseStatus.PENDING,
        db_index=True,
    )
    normalized_json = models.JSONField(default=dict)
    field_confidence_json = models.JSONField(default=dict)
    validation_errors_json = models.JSONField(default=list)
    validation_warnings_json = models.JSONField(default=list)
    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=0,
    )
    created_by_email = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "invoice_parse_results"
        constraints = [
            models.UniqueConstraint(
                fields=["document", "content_hash", "parser_version"],
                name="invoice_parse_content_version_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["document", "status"],
                name="invoice_parse_doc_status",
            ),
        ]
