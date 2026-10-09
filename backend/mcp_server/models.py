import uuid

from django.conf import settings
from django.db import models
from hyperbdr_dashboard.encryption import encryption_service


class McpDocumentPage(models.Model):
    """Cached searchable text for one page of an authorized source PDF."""

    quotation_asset = models.ForeignKey(
        "quotation.DocumentAsset",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="mcp_pages",
    )
    invoice_document = models.ForeignKey(
        "invoice.InvoiceDocument",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="mcp_pages",
    )
    content_hash = models.CharField(max_length=64)
    page_number = models.PositiveIntegerField(default=0)
    text = models.TextField()

    class Meta:
        db_table = "mcp_document_pages"
        indexes = [
            models.Index(
                fields=["quotation_asset", "content_hash"],
                name="mcp_page_quote_hash",
            ),
            models.Index(
                fields=["invoice_document", "content_hash"],
                name="mcp_page_invoice_hash",
            ),
        ]


class McpOAuthClient(models.Model):
    """OAuth client registered by an MCP consumer."""

    client_id = models.CharField(max_length=255, primary_key=True)
    metadata = models.JSONField(default=dict)
    client_secret_encrypted = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def set_client_secret(self, value):
        self.client_secret_encrypted = encryption_service.encrypt(value)

    def get_client_secret(self):
        return encryption_service.decrypt(self.client_secret_encrypted)


class McpOAuthAuthorization(models.Model):
    """Short-lived browser consent transaction."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_id = models.CharField(max_length=255)
    redirect_uri = models.TextField()
    state = models.TextField(blank=True)
    code_challenge = models.CharField(max_length=128)
    scopes = models.JSONField(default=list)
    resource = models.TextField()
    issuer = models.TextField(default="")
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)


class McpOAuthAuthorizationCode(models.Model):
    """One-time PKCE authorization code, stored by digest."""

    code_hash = models.CharField(max_length=64, unique=True)
    client_id = models.CharField(max_length=255)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    redirect_uri = models.TextField()
    redirect_uri_provided_explicitly = models.BooleanField(default=True)
    code_challenge = models.CharField(max_length=128)
    scopes = models.JSONField(default=list)
    resource = models.TextField()
    issuer = models.TextField(default="")
    expires_at = models.DateTimeField(db_index=True)


class McpOAuthToken(models.Model):
    """Opaque MCP access or refresh token, stored by digest."""

    ACCESS = "access"
    REFRESH = "refresh"
    TOKEN_TYPES = [(ACCESS, "Access"), (REFRESH, "Refresh")]

    token_hash = models.CharField(max_length=64, unique=True)
    family_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    token_type = models.CharField(max_length=8, choices=TOKEN_TYPES)
    client_id = models.CharField(max_length=255)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    scopes = models.JSONField(default=list)
    resource = models.TextField()
    issuer = models.TextField(default="")
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)


class McpRobotCredential(models.Model):
    """Revocable read-only MCP credential for a DevMind service identity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="mcp_robot_credentials",
    )
    token_hash = models.CharField(max_length=64, unique=True)
    scopes = models.JSONField(default=list)
    resource = models.TextField()
    issuer = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_mcp_robot_credentials",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "mcp_robot_credentials"
        ordering = ["-created_at"]
