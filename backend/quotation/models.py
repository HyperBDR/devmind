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
    feishu_folder_token = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
    )
    feishu_folder_path = models.JSONField(default=list, blank=True)
    created_by_email = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "document_assets"
        ordering = ["-created_at"]


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
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "connection", "version"],
                name="quotation_replica_version_unique",
            )
        ]


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


class SecurityAlert(models.Model):
    """Review state for a security signal derived from audit events."""

    SEVERITY_MEDIUM = "medium"
    SEVERITY_HIGH = "high"
    SEVERITY_CRITICAL = "critical"
    SEVERITY_CHOICES = (
        (SEVERITY_MEDIUM, "Medium"),
        (SEVERITY_HIGH, "High"),
        (SEVERITY_CRITICAL, "Critical"),
    )

    STATUS_OPEN = "open"
    STATUS_ACKNOWLEDGED = "acknowledged"
    STATUS_RESOLVED = "resolved"
    STATUS_FALSE_POSITIVE = "false_positive"
    STATUS_CHOICES = (
        (STATUS_OPEN, "Open"),
        (STATUS_ACKNOWLEDGED, "Acknowledged"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_FALSE_POSITIVE, "False positive"),
    )

    RESOLUTION_AUTHORIZED = "authorized_activity"
    RESOLUTION_POLICY_VIOLATION = "policy_violation"
    RESOLUTION_FALSE_POSITIVE = "false_positive"
    RESOLUTION_OTHER = "other"
    RESOLUTION_CHOICES = (
        (RESOLUTION_AUTHORIZED, "Authorized business activity"),
        (RESOLUTION_POLICY_VIOLATION, "Policy violation"),
        (RESOLUTION_FALSE_POSITIVE, "False positive"),
        (RESOLUTION_OTHER, "Other"),
    )

    id = models.BigAutoField(primary_key=True)
    rule = models.CharField(max_length=80, db_index=True)
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
        db_index=True,
    )
    title = models.CharField(max_length=255)
    reason = models.TextField()
    recommendation = models.TextField(blank=True, default="")
    runbook = models.TextField(blank=True, default="")
    owner = models.CharField(max_length=255, blank=True, default="")
    threshold = models.PositiveIntegerField(default=1)
    window_minutes = models.PositiveIntegerField(default=1)
    subject_key = models.CharField(max_length=255, db_index=True)
    subject_email = models.CharField(max_length=255, blank=True, default="")
    subject_name = models.CharField(max_length=255, blank=True, default="")
    source_ip = models.GenericIPAddressField(blank=True, null=True)
    subject_user_agent = models.CharField(
        max_length=500,
        blank=True,
        default="",
    )
    trigger_count = models.PositiveIntegerField(default=1)
    evidence_events = models.ManyToManyField(
        AuditEvent,
        related_name="security_alerts",
        blank=True,
    )
    first_detected_at = models.DateTimeField(db_index=True)
    last_detected_at = models.DateTimeField(db_index=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="acknowledged_quotation_security_alerts",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    acknowledged_at = models.DateTimeField(blank=True, null=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="resolved_quotation_security_alerts",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolution = models.CharField(
        max_length=40,
        choices=RESOLUTION_CHOICES,
        blank=True,
        default="",
    )
    resolution_note = models.TextField(blank=True, default="")
    notify_affected_user = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "quotation_security_alerts"
        ordering = ["-last_detected_at", "-id"]
        indexes = [
            models.Index(
                fields=["status", "severity"],
                name="quotation_s_status_17d6a6_idx",
            ),
            models.Index(
                fields=["rule", "subject_key", "status"],
                name="quotation_s_rule_345fce_idx",
            ),
        ]


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
