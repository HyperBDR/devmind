from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models, router, transaction
from django.utils import timezone

from hyperbdr_dashboard.encryption import encryption_service


def _uuid() -> str:
    return str(uuid.uuid4())


class QuoteStatus(models.TextChoices):
    """Persisted quote lifecycle shared by manual and Feishu-imported quotes."""

    DRAFT = "draft", "draft"
    GENERATED = "generated", "generated"
    UPLOADED = "uploaded", "uploaded"
    SENT = "sent", "sent"
    ACCEPTED = "accepted", "accepted"
    REJECTED = "rejected", "rejected"
    EXPIRED = "expired", "expired"
    CANCELLED = "cancelled", "cancelled"


class QuotationSourceType(models.TextChoices):
    MANUAL = "manual", "Manual"
    DOCUMENT_IMPORT = "document_import", "Document import"


class ItemType(models.TextChoices):
    SOFTWARE = "Software", "Software"
    SERVICE = "Service", "Service"
    OTHER = "Other", "Other"


class DocumentType(models.TextChoices):
    EXCEL = "excel", "excel"
    PDF = "pdf", "pdf"
    SIGNATURE = "signature", "signature"


class DocumentLifecycleState(models.TextChoices):
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class SyncJobType(models.TextChoices):
    UPLOAD = "upload", "upload"
    PULL = "pull", "pull"
    PARSE = "parse", "parse"
    OCR = "ocr", "ocr"


class SyncJobStatus(models.TextChoices):
    PENDING = "pending", "pending"
    QUEUED = "queued", "queued"
    RUNNING = "running", "running"
    RETRYING = "retrying", "retrying"
    SUCCESS = "success", "success"
    FAILED = "failed", "failed"


EXPORT_ARCHIVE_SYNC_STAGE = "export_archive"


class DocumentParseStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    READY = "ready", "Ready"
    REVIEW_REQUIRED = "review_required", "Review required"
    CONFIRMED = "confirmed", "Confirmed"
    NOT_QUOTATION = "not_quotation", "Not quotation"
    FAILED = "failed", "Failed"
    SUPERSEDED = "superseded", "Superseded"


class StorageConnectionStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    DISABLED = "disabled", "Disabled"
    ERROR = "error", "Error"


class StorageAuthMode(models.TextChoices):
    TENANT_APP = "tenant_app", "Tenant application"
    MANAGED_ACCOUNT = "managed_account", "Managed service account"


class StorageMountPurpose(models.TextChoices):
    QUOTATION_ARCHIVE = "quotation_archive", "Quotation archive"
    QUOTATION_SHARE = "quotation_share", "Quotation share"


class ReplicaSyncStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SYNCING = "syncing", "Syncing"
    SYNCED = "synced", "Synced"
    FAILED = "failed", "Failed"
    REVOKED = "revoked", "Revoked"


class RemoteFileCleanupStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CANCELLED = "cancelled", "Cancelled"
    COMPLETED = "completed", "Completed"


class QuotationTemplateStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class ExportJobStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RENDERING_EXCEL = "rendering_excel", "Rendering Excel"
    CONVERTING_PDF = "converting_pdf", "Converting PDF"
    RENDERED = "rendered", "Rendered"
    UPLOAD_QUEUED = "upload_queued", "Upload queued"
    UPLOADING = "uploading", "Uploading"
    COMPLETED = "completed", "Completed"
    RENDER_FAILED = "render_failed", "Render failed"
    UPLOAD_FAILED = "upload_failed", "Upload failed"


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class QuotationMembershipRole(models.TextChoices):
    """Supported roles inside the quotation platform."""

    ADMIN = "quotation_admin", "Quotation administrator"
    USER = "quotation_user", "Quotation user"


class QuotationMembership(TimeStampedModel):
    """A user's role inside the quotation platform."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quotation_memberships",
    )
    role = models.CharField(
        max_length=40,
        choices=QuotationMembershipRole.choices,
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_quotation_memberships",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "quotation_memberships"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_active=True),
                name="quotation_membership_active_user_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "is_active"],
                name="quotation_member_user_active",
            ),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.role}"


class QuotationViewPermissionTarget(models.TextChoices):
    """Supported targets for administrator-granted view access."""

    FOLDER = "folder", "Feishu folder"
    DOCUMENT = "document", "Feishu document"


class QuotationViewPermission(TimeStampedModel):
    """Administrator-granted view access to a Feishu folder or file."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quotation_view_permissions",
    )
    target_type = models.CharField(
        max_length=20,
        choices=QuotationViewPermissionTarget.choices,
    )
    folder_token = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    folder_name = models.CharField(max_length=255, blank=True, default="")
    document = models.ForeignKey(
        "quotation.DocumentAsset",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="quotation_view_permissions",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="granted_quotation_view_permissions",
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "quotation_view_permissions"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "target_type", "folder_token"],
                condition=(
                    models.Q(
                        is_active=True,
                        target_type=QuotationViewPermissionTarget.FOLDER,
                    )
                    & ~models.Q(folder_token="")
                ),
                name="quotation_active_folder_view_unique",
            ),
            models.UniqueConstraint(
                fields=["user", "target_type", "document"],
                condition=(
                    models.Q(
                        is_active=True,
                        target_type=QuotationViewPermissionTarget.DOCUMENT,
                    )
                    & models.Q(document__isnull=False)
                ),
                name="quotation_active_document_view_unique",
            ),
        ]

    def __str__(self):
        target = self.folder_name or self.document_id or "unknown"
        return f"{self.user_id}:{self.target_type}:{target}"


class QuotationQuerySet(models.QuerySet):
    """Lock quotations before Django collects their cascade graph."""

    def delete(self):
        with transaction.atomic(using=self.db):
            list(self.select_for_update().values_list("pk", flat=True))
            return super().delete()


class Quotation(TimeStampedModel):
    objects = QuotationQuerySet.as_manager()

    id = models.CharField(
        primary_key=True, max_length=36, default=_uuid, editable=False
    )
    quote_no = models.CharField(max_length=120, unique=True, db_index=True)
    source_quote_no = models.CharField(
        max_length=120,
        blank=True,
        default="",
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=QuoteStatus.choices,
        default=QuoteStatus.DRAFT,
        db_index=True,
    )
    version_current = models.IntegerField(default=0)
    source_type = models.CharField(
        max_length=30,
        choices=QuotationSourceType.choices,
        default=QuotationSourceType.MANUAL,
        db_index=True,
    )

    product_line = models.CharField(max_length=40, default="BDR")
    product_line_name = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )
    project_name = models.CharField(max_length=255)
    currency = models.CharField(max_length=10, default="USD")
    payment_term_option = models.CharField(max_length=40, default="CIA")
    payment_terms = models.CharField(max_length=255, blank=True, default="")
    quote_date = models.DateField()
    expire_date = models.DateField()
    tax_label = models.CharField(max_length=40, default="VAT")
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    vat_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    software_subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    others_subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    subtotal_before_vat = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )
    grand_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    remarks_disclaimer = models.TextField(blank=True, default="")

    issuer_company_name = models.CharField(
        max_length=255, default="OnePro Cloud Limited"
    )
    issuer_contact_name = models.CharField(max_length=120)
    issuer_contact_email = models.CharField(max_length=255)
    issuer_contact_title = models.CharField(max_length=120, blank=True, default="")
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
    archived_at = models.DateTimeField(blank=True, null=True, db_index=True)
    archived_by_email = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    archive_reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "quotations"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["currency", "status", "created_at"],
                name="quote_dash_curr_stat_created",
            ),
            models.Index(
                fields=["created_by_email", "currency", "status"],
                name="quote_dash_owner_curr_stat",
            ),
            models.Index(
                fields=["-created_at", "-id"],
                name="quote_list_created_id",
            ),
            models.Index(
                fields=["created_by_email", "-created_at", "-id"],
                name="quote_list_owner_created",
            ),
            models.Index(
                fields=["product_line", "-created_at", "-id"],
                name="quote_list_product_created",
            ),
            models.Index(
                fields=["quote_date"],
                name="quote_list_quote_date",
            ),
            models.Index(
                fields=["product_line_name"],
                name="quote_list_product_name",
            ),
        ]

    def delete(self, using=None, keep_parents=False):
        """Lock this quotation before Django collects related artifacts."""
        database = (
            using
            or self._state.db
            or router.db_for_write(
                type(self),
                instance=self,
            )
        )
        with transaction.atomic(using=database):
            type(self).objects.using(database).select_for_update().get(
                pk=self.pk,
            )
            return super().delete(
                using=database,
                keep_parents=keep_parents,
            )


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
    list_price = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    net_unit_price = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    extended_price = models.DecimalField(max_digits=18, decimal_places=2, default=0)

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
        indexes = [
            models.Index(
                fields=["quotation", "status", "created_at"],
                name="quote_ver_quote_stat_created",
            ),
        ]


class QuotationTemplate(TimeStampedModel):
    """Immutable, backend-managed XLSX quotation template version."""

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=_uuid,
        editable=False,
    )
    name = models.CharField(max_length=120)
    version = models.PositiveIntegerField()
    storage_key = models.CharField(max_length=512)
    content_hash = models.CharField(max_length=64)
    status = models.CharField(
        max_length=20,
        choices=QuotationTemplateStatus.choices,
        default=QuotationTemplateStatus.DRAFT,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quotation_templates",
    )

    class Meta:
        db_table = "quotation_templates"
        ordering = ["name", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "version"],
                name="quotation_template_name_version_unique",
            ),
            models.UniqueConstraint(
                fields=["status"],
                condition=models.Q(status=QuotationTemplateStatus.ACTIVE),
                name="quotation_template_single_active",
            ),
        ]


class ExportJob(TimeStampedModel):
    """Pinned quotation export request and its observable state."""

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=_uuid,
        editable=False,
    )
    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.CASCADE,
        related_name="export_jobs",
    )
    quotation_version = models.ForeignKey(
        QuotationVersion,
        on_delete=models.RESTRICT,
        related_name="export_jobs",
    )
    template = models.ForeignKey(
        QuotationTemplate,
        on_delete=models.PROTECT,
        related_name="export_jobs",
    )
    quotation_version_no = models.PositiveIntegerField()
    template_version = models.PositiveIntegerField()
    renderer_version = models.CharField(max_length=80)
    formats = models.JSONField(default=list)
    archive_to_feishu = models.BooleanField(default=False)
    archive_folder_token = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    idempotency_key = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
    )
    status = models.CharField(
        max_length=30,
        choices=ExportJobStatus.choices,
        default=ExportJobStatus.QUEUED,
        db_index=True,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quotation_export_jobs",
    )
    request_id = models.CharField(max_length=100, blank=True, default="")
    trace_id = models.CharField(max_length=100, blank=True, default="")
    celery_task_id = models.CharField(max_length=255, blank=True, default="")
    error_code = models.CharField(max_length=100, blank=True, default="")
    error_message = models.CharField(max_length=500, blank=True, default="")
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "quotation_export_jobs"
        ordering = ["-created_at"]


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
    quotation_version = models.ForeignKey(
        QuotationVersion,
        on_delete=models.RESTRICT,
        related_name="document_assets",
        null=True,
        blank=True,
    )
    template = models.ForeignKey(
        QuotationTemplate,
        on_delete=models.PROTECT,
        related_name="document_assets",
        null=True,
        blank=True,
    )
    export_job = models.ForeignKey(
        ExportJob,
        on_delete=models.SET_NULL,
        related_name="assets",
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
    content_hash = models.CharField(max_length=64, blank=True, default="")
    template_version = models.PositiveIntegerField(default=0)
    renderer_version = models.CharField(max_length=80, blank=True, default="")
    source = models.CharField(max_length=20, default="local")
    feishu_file_token = models.CharField(max_length=255, blank=True, null=True)
    feishu_url = models.URLField(max_length=512, blank=True, null=True)
    feishu_folder_token = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
    )
    feishu_folder_path = models.JSONField(default=list, blank=True)
    created_by_email = models.CharField(max_length=255, blank=True, null=True)
    lifecycle_state = models.CharField(
        max_length=20,
        choices=DocumentLifecycleState.choices,
        default=DocumentLifecycleState.ACTIVE,
        db_index=True,
    )
    archived_at = models.DateTimeField(blank=True, null=True, db_index=True)
    archived_by_email = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    archive_reason = models.CharField(max_length=255, blank=True, default="")
    purge_after = models.DateTimeField(blank=True, null=True, db_index=True)
    legal_hold_at = models.DateTimeField(blank=True, null=True, db_index=True)
    legal_hold_reason = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "document_assets"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["quotation", "doc_type", "-created_at", "-id"],
                name="quote_doc_quote_type_created",
            ),
            models.Index(
                fields=["lifecycle_state", "purge_after", "created_at"],
                name="quote_doc_lifecycle_purge",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "feishu_file_token"],
                condition=(
                    models.Q(source="feishu")
                    & models.Q(feishu_file_token__isnull=False)
                    & ~models.Q(feishu_file_token="")
                ),
                name="quotation_feishu_asset_token_unique",
            ),
            models.UniqueConstraint(
                fields=["export_job", "doc_type"],
                condition=models.Q(export_job__isnull=False),
                name="quotation_export_asset_format_unique",
            ),
        ]


class StorageConnection(TimeStampedModel):
    """Managed provider connection without a user authorization boundary."""

    ENCRYPTED_PREFIX = "enc::"

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=_uuid,
        editable=False,
    )
    provider = models.CharField(max_length=40, default="feishu", db_index=True)
    display_name = models.CharField(max_length=255)
    external_tenant_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
    )
    auth_mode = models.CharField(
        max_length=40,
        choices=StorageAuthMode.choices,
        default=StorageAuthMode.TENANT_APP,
    )
    app_id = models.CharField(max_length=255, blank=True, default="")
    app_secret = models.TextField(blank=True, default="")
    access_token = models.TextField(blank=True, default="")
    refresh_token = models.TextField(blank=True, default="")
    token_expires_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=StorageConnectionStatus.choices,
        default=StorageConnectionStatus.ACTIVE,
        db_index=True,
    )
    is_default = models.BooleanField(default=False, db_index=True)
    last_health_checked_at = models.DateTimeField(blank=True, null=True)
    last_health_error_code = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )
    metadata = models.JSONField(blank=True, default=dict)

    class Meta:
        db_table = "quotation_storage_connections"
        ordering = ["display_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_tenant_id"],
                condition=~models.Q(external_tenant_id=""),
                name="quotation_storage_provider_tenant_unique",
            )
        ]

    @classmethod
    def _encrypt(cls, value: str) -> str:
        if not value or value.startswith(cls.ENCRYPTED_PREFIX):
            return value
        encrypted = encryption_service.encrypt(value)
        return f"{cls.ENCRYPTED_PREFIX}{encrypted}"

    @classmethod
    def _decrypt(cls, value: str) -> str:
        if not value:
            return ""
        if not value.startswith(cls.ENCRYPTED_PREFIX):
            return value
        encrypted = value[len(cls.ENCRYPTED_PREFIX) :]
        return encryption_service.decrypt(encrypted)

    def save(self, *args, **kwargs):
        self.app_secret = self._encrypt(self.app_secret)
        self.access_token = self._encrypt(self.access_token)
        self.refresh_token = self._encrypt(self.refresh_token)
        super().save(*args, **kwargs)

    def get_app_secret(self) -> str:
        return self._decrypt(self.app_secret)

    def get_access_token(self) -> str:
        return self._decrypt(self.access_token)

    def get_refresh_token(self) -> str:
        return self._decrypt(self.refresh_token)

    def rotate_credentials(
        self,
        *,
        app_id: str = "",
        app_secret: str = "",
        access_token: str = "",
        refresh_token: str = "",
    ) -> None:
        """Replace only credentials explicitly supplied by an operator."""
        if app_id:
            self.app_id = app_id
        if app_secret:
            self.app_secret = app_secret
        if access_token:
            self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token
        self.save()


class StorageMount(TimeStampedModel):
    """Backend-owned mapping from a routing scope to a provider folder."""

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=_uuid,
        editable=False,
    )
    connection = models.ForeignKey(
        StorageConnection,
        on_delete=models.PROTECT,
        related_name="mounts",
    )
    scope_key = models.CharField(max_length=100, blank=True, default="")
    purpose = models.CharField(
        max_length=50,
        choices=StorageMountPurpose.choices,
        default=StorageMountPurpose.QUOTATION_ARCHIVE,
        db_index=True,
    )
    document_type = models.CharField(max_length=40, blank=True, default="")
    root_folder_token = models.CharField(max_length=255)
    root_folder_name = models.CharField(max_length=255, blank=True, default="")
    path_template = models.CharField(
        max_length=500,
        blank=True,
        default="{year}/{product_line}/{quote_no}",
    )
    conflict_policy = models.CharField(
        max_length=20,
        default="rename",
        choices=[("rename", "Rename"), ("reuse", "Reuse")],
    )
    enabled = models.BooleanField(default=True, db_index=True)
    is_default = models.BooleanField(default=False, db_index=True)
    metadata = models.JSONField(blank=True, default=dict)

    class Meta:
        db_table = "quotation_storage_mounts"
        ordering = ["scope_key", "purpose", "document_type", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "scope_key",
                    "purpose",
                    "document_type",
                    "connection",
                ],
                name="quotation_storage_mount_route_unique",
            )
        ]


class DocumentReplica(TimeStampedModel):
    """Remote provider copy of one logical DevMind document version."""

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=_uuid,
        editable=False,
    )
    asset = models.ForeignKey(
        DocumentAsset,
        on_delete=models.CASCADE,
        related_name="replicas",
    )
    connection = models.ForeignKey(
        StorageConnection,
        on_delete=models.PROTECT,
        related_name="document_replicas",
    )
    mount = models.ForeignKey(
        StorageMount,
        on_delete=models.PROTECT,
        related_name="document_replicas",
    )
    remote_file_token = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    remote_url = models.URLField(max_length=512, blank=True, default="")
    folder_token = models.CharField(max_length=255, blank=True, default="")
    folder_path = models.JSONField(blank=True, default=list)
    version = models.PositiveIntegerField(default=1)
    content_hash = models.CharField(max_length=64, blank=True, default="")
    sync_status = models.CharField(
        max_length=20,
        choices=ReplicaSyncStatus.choices,
        default=ReplicaSyncStatus.PENDING,
        db_index=True,
    )
    last_synced_at = models.DateTimeField(blank=True, null=True)
    error_code = models.CharField(max_length=100, blank=True, default="")
    error_summary = models.CharField(max_length=500, blank=True, default="")
    revoked_at = models.DateTimeField(blank=True, null=True)
    metadata = models.JSONField(blank=True, default=dict)

    class Meta:
        db_table = "quotation_document_replicas"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=[
                    "asset",
                    "sync_status",
                    "revoked_at",
                    "-version",
                ],
                name="quote_replica_asset_status",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "connection", "version"],
                name="quotation_replica_version_unique",
            )
        ]


class RemoteFileCleanup(TimeStampedModel):
    """Durable cleanup intent and serialization point for a remote file."""

    id = models.CharField(
        primary_key=True,
        max_length=36,
        default=_uuid,
        editable=False,
    )
    connection = models.ForeignKey(
        StorageConnection,
        on_delete=models.PROTECT,
        related_name="remote_file_cleanups",
    )
    remote_file_token = models.CharField(max_length=255, unique=True)
    owned = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=RemoteFileCleanupStatus.choices,
        default=RemoteFileCleanupStatus.PENDING,
        db_index=True,
    )
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=255, blank=True, default="")
    next_dispatch_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )
    processed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "quotation_remote_file_cleanups"
        ordering = ["created_at", "id"]


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
    replica = models.ForeignKey(
        DocumentReplica,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sync_jobs",
    )
    storage_connection = models.ForeignKey(
        StorageConnection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sync_jobs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quotation_sync_jobs",
    )
    request_id = models.CharField(max_length=100, blank=True, default="")
    trace_id = models.CharField(max_length=100, blank=True, default="")
    scope_key = models.CharField(max_length=100, blank=True, default="")
    error_code = models.CharField(max_length=100, blank=True, default="")
    payload_json = models.JSONField(null=True, blank=True)
    result_json = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    celery_task_id = models.CharField(max_length=255, blank=True, default="")
    stage = models.CharField(max_length=40, blank=True, default="")
    attempt_count = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    heartbeat_at = models.DateTimeField(blank=True, null=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    duration_ms = models.PositiveBigIntegerField(default=0)

    class Meta:
        db_table = "sync_jobs"


class AuditEvent(models.Model):
    """Append-only audit event for Quote Desk user activity."""

    RESULT_SUCCEEDED = "succeeded"
    RESULT_DENIED = "denied"
    RESULT_FAILED = "failed"
    RESULT_CHOICES = (
        (RESULT_SUCCEEDED, "Succeeded"),
        (RESULT_DENIED, "Denied"),
        (RESULT_FAILED, "Failed"),
    )

    ACTOR_USER = "user"
    ACTOR_SYSTEM = "system"
    ACTOR_TASK = "task"
    ACTOR_TYPE_CHOICES = (
        (ACTOR_USER, "User"),
        (ACTOR_SYSTEM, "System"),
        (ACTOR_TASK, "Task"),
    )

    RISK_LOW = "low"
    RISK_MEDIUM = "medium"
    RISK_HIGH = "high"
    RISK_CRITICAL = "critical"
    RISK_CHOICES = (
        (RISK_LOW, "Low"),
        (RISK_MEDIUM, "Medium"),
        (RISK_HIGH, "High"),
        (RISK_CRITICAL, "Critical"),
    )

    id = models.BigAutoField(primary_key=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="quotation_audit_events",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    actor_email = models.CharField(max_length=255, blank=True, default="")
    actor_name = models.CharField(max_length=255, blank=True, default="")
    actor_type = models.CharField(
        max_length=20,
        choices=ACTOR_TYPE_CHOICES,
        default=ACTOR_USER,
        db_index=True,
    )
    actor_role_snapshot = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )
    impersonator_id = models.CharField(max_length=100, blank=True, default="")
    event_name = models.CharField(max_length=100, blank=True, db_index=True)
    module = models.CharField(max_length=50, db_index=True)
    action = models.CharField(max_length=50, db_index=True)
    result = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        db_index=True,
    )
    target_type = models.CharField(max_length=100, blank=True, default="")
    target_id = models.CharField(max_length=100, blank=True, default="")
    target_label = models.CharField(max_length=255, blank=True, default="")
    summary = models.CharField(max_length=500, blank=True, default="")
    before_summary = models.JSONField(blank=True, default=dict)
    after_summary = models.JSONField(blank=True, default=dict)
    changes = models.JSONField(blank=True, default=dict)
    metadata = models.JSONField(blank=True, default=dict)
    request_id = models.CharField(max_length=100, blank=True, default="")
    trace_id = models.CharField(max_length=100, blank=True, default="")
    reason_code = models.CharField(max_length=100, blank=True, default="")
    risk_level = models.CharField(
        max_length=20,
        choices=RISK_CHOICES,
        default=RISK_LOW,
        db_index=True,
    )
    workspace_id = models.CharField(max_length=100, blank=True, default="")
    quotation_id_snapshot = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
    )
    document_id_snapshot = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
    )
    storage_connection_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )
    source_organization_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )
    target_organization_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )
    sync_job_id = models.CharField(max_length=100, blank=True, default="")
    error_code = models.CharField(max_length=100, blank=True, default="")
    idempotency_key = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        unique=True,
    )
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "quotation_audit_events"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["module", "action", "created_at"]),
            models.Index(fields=["actor", "created_at"]),
            models.Index(fields=["target_type", "target_id"]),
            models.Index(
                fields=["request_id", "created_at"],
                name="quotation_a_request_80f6da_idx",
            ),
            models.Index(
                fields=["result", "risk_level", "created_at"],
                name="quotation_a_result_895550_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        """Prevent application code from mutating persisted audit events."""
        if not self._state.adding:
            raise TypeError("Audit events are append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Prevent application code from deleting persisted audit events."""
        raise TypeError("Audit events are append-only")


class DocumentParseResult(TimeStampedModel):
    """Versioned, reviewable extraction result for one document asset."""

    id = models.CharField(
        primary_key=True, max_length=36, default=_uuid, editable=False
    )
    asset = models.ForeignKey(
        DocumentAsset,
        on_delete=models.CASCADE,
        related_name="parse_results",
    )
    sync_job = models.OneToOneField(
        SyncJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parse_result",
    )
    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_parse_results",
    )
    status = models.CharField(
        max_length=30,
        choices=DocumentParseStatus.choices,
        default=DocumentParseStatus.PENDING,
        db_index=True,
    )
    parser_name = models.CharField(max_length=100)
    parser_version = models.CharField(max_length=40)
    content_hash = models.CharField(max_length=64, db_index=True)
    normalized_json = models.JSONField(blank=True, default=dict)
    source_totals_json = models.JSONField(blank=True, default=dict)
    field_confidence_json = models.JSONField(blank=True, default=dict)
    validation_errors_json = models.JSONField(blank=True, default=list)
    validation_warnings_json = models.JSONField(blank=True, default=list)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    created_by_email = models.CharField(
        max_length=255, blank=True, default="", db_index=True
    )
    error_message = models.TextField(blank=True, null=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "document_parse_results"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "content_hash", "parser_version"],
                name="quotation_document_parse_result_unique",
            )
        ]


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
    preferred_folder_token = models.CharField(max_length=128, blank=True, null=True)
    preferred_folder_name = models.CharField(max_length=255, blank=True, null=True)
    shared_folder_bookmarks = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "feishu_connections"

    @classmethod
    def encrypt_token(cls, value: str) -> str:
        if not value or value.startswith(cls.ENCRYPTED_TOKEN_PREFIX):
            return value
        return f"{cls.ENCRYPTED_TOKEN_PREFIX}{encryption_service.encrypt(value)}"

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
