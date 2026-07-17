from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from hyperbdr_dashboard.encryption import encryption_service


def _uuid() -> str:
    return str(uuid.uuid4())


class QuoteStatus(models.TextChoices):
    DRAFT = "draft", "draft"
    GENERATED = "generated", "generated"
    UPLOADED = "uploaded", "uploaded"
    SENT = "sent", "sent"
    ACCEPTED = "accepted", "accepted"
    REJECTED = "rejected", "rejected"
    EXPIRED = "expired", "expired"
    CANCELLED = "cancelled", "cancelled"


class ItemType(models.TextChoices):
    SOFTWARE = "Software", "Software"
    SERVICE = "Service", "Service"
    OTHER = "Other", "Other"


class DocumentType(models.TextChoices):
    EXCEL = "excel", "excel"
    PDF = "pdf", "pdf"
    SIGNATURE = "signature", "signature"


class SyncJobType(models.TextChoices):
    UPLOAD = "upload", "upload"
    PULL = "pull", "pull"
    PARSE = "parse", "parse"


class SyncJobStatus(models.TextChoices):
    PENDING = "pending", "pending"
    RUNNING = "running", "running"
    SUCCESS = "success", "success"
    FAILED = "failed", "failed"


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Quotation(TimeStampedModel):
    id = models.CharField(
        primary_key=True, max_length=36, default=_uuid, editable=False
    )
    quote_no = models.CharField(max_length=120, unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=QuoteStatus.choices,
        default=QuoteStatus.DRAFT,
        db_index=True,
    )
    version_current = models.IntegerField(default=0)

    product_line = models.CharField(max_length=40, default="BDR")
    project_name = models.CharField(max_length=255)
    currency = models.CharField(max_length=10, default="USD")
    payment_term_option = models.CharField(max_length=40, default="CIA")
    payment_terms = models.CharField(max_length=255, blank=True, default="")
    quote_date = models.DateField()
    expire_date = models.DateField()
    tax_label = models.CharField(max_length=40, default="VAT")
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    vat_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )
    software_subtotal = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )
    others_subtotal = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )
    subtotal_before_vat = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )
    grand_total = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )
    remarks_disclaimer = models.TextField(blank=True, default="")

    issuer_company_name = models.CharField(
        max_length=255, default="OnePro Cloud Limited"
    )
    issuer_contact_name = models.CharField(max_length=120)
    issuer_contact_email = models.CharField(max_length=255)
    issuer_contact_title = models.CharField(
        max_length=120, blank=True, default=""
    )
    issuer_signature = models.TextField(blank=True, default="")

    client_company = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=120)
    email = models.CharField(max_length=255)
    billing_company = models.CharField(max_length=255, blank=True, default="")
    billing_contact = models.CharField(max_length=120, blank=True, default="")
    billing_email = models.CharField(max_length=255, blank=True, default="")

    created_by_email = models.CharField(
        max_length=255, blank=True, null=True, db_index=True
    )

    class Meta:
        db_table = "quotations"
        ordering = ["-created_at"]


class QuotationItem(TimeStampedModel):
    id = models.CharField(
        primary_key=True, max_length=36, default=_uuid, editable=False
    )
    quotation = models.ForeignKey(
        Quotation, on_delete=models.CASCADE, related_name="items"
    )
    line_no = models.IntegerField()
    type = models.CharField(
        max_length=20, choices=ItemType.choices, default=ItemType.SOFTWARE
    )
    item_id = models.CharField(max_length=120, blank=True, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    qty = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    list_price = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    net_unit_price = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )
    extended_price = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )

    class Meta:
        db_table = "quotation_items"
        unique_together = [("quotation", "line_no")]
        ordering = ["line_no"]


class QuotationVersion(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=_uuid, editable=False
    )
    quotation = models.ForeignKey(
        Quotation, on_delete=models.CASCADE, related_name="versions"
    )
    version_no = models.IntegerField()
    status = models.CharField(max_length=20, choices=QuoteStatus.choices)
    notes = models.TextField(blank=True, default="")
    snapshot_json = models.JSONField()
    operator_email = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "quotation_versions"
        unique_together = [("quotation", "version_no")]
        ordering = ["version_no"]


class DocumentAsset(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=_uuid, editable=False
    )
    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.CASCADE,
        related_name="documents",
        null=True,
        blank=True,
    )
    doc_type = models.CharField(
        max_length=20, choices=DocumentType.choices, db_index=True
    )
    file_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=120)
    storage_key = models.CharField(max_length=512)
    size_bytes = models.IntegerField(default=0)
    source = models.CharField(max_length=20, default="local")
    feishu_file_token = models.CharField(max_length=255, blank=True, null=True)
    feishu_url = models.URLField(max_length=512, blank=True, null=True)
    created_by_email = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "document_assets"
        ordering = ["-created_at"]


class SyncJob(TimeStampedModel):
    id = models.CharField(
        primary_key=True, max_length=36, default=_uuid, editable=False
    )
    job_type = models.CharField(
        max_length=20, choices=SyncJobType.choices, db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=SyncJobStatus.choices,
        default=SyncJobStatus.PENDING,
        db_index=True,
    )
    quotation = models.ForeignKey(
        Quotation, on_delete=models.SET_NULL, null=True, blank=True
    )
    asset = models.ForeignKey(
        DocumentAsset, on_delete=models.SET_NULL, null=True, blank=True
    )
    payload_json = models.JSONField(null=True, blank=True)
    result_json = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "sync_jobs"


class DocumentParseResult(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=_uuid, editable=False
    )
    asset = models.OneToOneField(
        DocumentAsset, on_delete=models.CASCADE, related_name="parse_result"
    )
    parser_type = models.CharField(max_length=40)
    parse_status = models.CharField(max_length=20, default="success")
    parsed_json = models.JSONField()
    error_message = models.TextField(blank=True, null=True)
    parsed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "document_parse_results"


class FeishuConnection(TimeStampedModel):
    ENCRYPTED_TOKEN_PREFIX = "enc::"

    id = models.CharField(
        primary_key=True, max_length=36, default=_uuid, editable=False
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feishu_connection",
    )
    user_email = models.CharField(max_length=255, unique=True, db_index=True)
    feishu_open_id = models.CharField(max_length=128, blank=True, null=True)
    feishu_union_id = models.CharField(max_length=128, blank=True, null=True)
    feishu_user_name = models.CharField(max_length=255, blank=True, null=True)
    access_token = models.TextField(blank=True, default="")
    refresh_token = models.TextField(blank=True, default="")
    token_type = models.CharField(max_length=40, default="Bearer")
    expires_at = models.DateTimeField(null=True, blank=True)
    scope = models.TextField(blank=True, default="")
    preferred_folder_token = models.CharField(
        max_length=128, blank=True, null=True
    )
    preferred_folder_name = models.CharField(
        max_length=255, blank=True, null=True
    )
    shared_folder_bookmarks = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "feishu_connections"

    @classmethod
    def encrypt_token(cls, value: str) -> str:
        if not value or value.startswith(cls.ENCRYPTED_TOKEN_PREFIX):
            return value
        return (
            f"{cls.ENCRYPTED_TOKEN_PREFIX}{encryption_service.encrypt(value)}"
        )

    @classmethod
    def decrypt_token(cls, value: str) -> str:
        if not value:
            return ""
        if not value.startswith(cls.ENCRYPTED_TOKEN_PREFIX):
            return value
        encrypted = value[len(cls.ENCRYPTED_TOKEN_PREFIX) :]
        return encryption_service.decrypt(encrypted)

    def get_access_token(self) -> str:
        return self.decrypt_token(self.access_token)

    def get_refresh_token(self) -> str:
        return self.decrypt_token(self.refresh_token)

    def set_access_token(self, value: str) -> None:
        self.access_token = self.encrypt_token(value)

    def set_refresh_token(self, value: str) -> None:
        self.refresh_token = self.encrypt_token(value)

    def save(self, *args, **kwargs):
        self.set_access_token(self.access_token)
        self.set_refresh_token(self.refresh_token)
        super().save(*args, **kwargs)


class UserQuotationCatalog(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quotation_catalog",
    )
    catalog_version = models.CharField(max_length=120, blank=True, default="")
    initialized = models.BooleanField(default=False)
    products = models.JSONField(default=list, blank=True)
    services = models.JSONField(default=list, blank=True)
    discounts = models.JSONField(default=list, blank=True)
    product_lines = models.JSONField(default=list, blank=True)
    payment_terms = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "quotation_user_catalogs"
